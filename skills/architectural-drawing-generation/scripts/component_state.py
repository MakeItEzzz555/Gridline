#!/usr/bin/env python3
"""Local component proposal ledger. SQLite commits are atomic; no native-host writes."""
import argparse
import base64
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from component_spec import validate, encode, digest, load
from archimesh_doctor import read_file, absolute_path
from component_approval import payload, public_key_fingerprint, verify as verify_signature


@contextmanager
def transaction(path, *, new=False):
    path = absolute_path(Path(path).expanduser())
    if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('state must be a regular existing database')
    connection = sqlite3.connect(path.as_uri()+'?mode=rw', uri=True, timeout=5)
    try:
        if new:
            connection.execute('PRAGMA application_id=1196573489')
            connection.execute('PRAGMA user_version=2')
        elif connection.execute('PRAGMA application_id').fetchone()[0]!=1196573489 or connection.execute('PRAGMA user_version').fetchone()[0]!=2:
            raise ValueError('not a supported Gridline component-state database')
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN IMMEDIATE')
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def event(db, kind, ident, actor, detail):
    db.execute('INSERT INTO events(kind,object_hash,actor,detail) VALUES(?,?,?,?)',
               (kind, ident, actor, encode(detail).decode()))


def initialization_payload(document, owner, public_key):
    validate(document)
    if not isinstance(owner,str) or not owner or len(owner)>100:raise ValueError('explicit owner label required')
    return payload('INITIALIZE',document['project_id'],digest(document),public_key_fingerprint(public_key),owner)


def initialize(path, document, owner, *, public_key, signature):
    validate(document)
    if not owner or len(owner) > 100:
        raise ValueError('explicit owner required')
    message=initialization_payload(document,owner,public_key)
    key_sha256=verify_signature(public_key,signature,message)
    path = absolute_path(Path(path).expanduser())
    if path.exists() or path.is_symlink():raise ValueError('state initialization requires a new database')
    if any(p.is_symlink() for p in path.parents):raise ValueError('symlink state directory unsupported')
    fd,name=tempfile.mkstemp(prefix='.gridline-state-',dir=path.parent)
    os.close(fd);temporary=Path(name)
    try:
        with transaction(temporary,new=True) as db:
            db.executescript('''
            CREATE TABLE revisions(hash TEXT PRIMARY KEY,seq INTEGER UNIQUE NOT NULL,parent TEXT,document TEXT NOT NULL);
            CREATE TABLE head(id INTEGER PRIMARY KEY CHECK(id=1),hash TEXT NOT NULL REFERENCES revisions(hash),owner TEXT NOT NULL,public_key BLOB NOT NULL,key_sha256 TEXT NOT NULL,root_hash TEXT NOT NULL,initial_signature BLOB NOT NULL);
            CREATE TABLE proposals(hash TEXT PRIMARY KEY,base TEXT NOT NULL REFERENCES revisions(hash),patch TEXT NOT NULL,rationale TEXT NOT NULL,evidence TEXT NOT NULL,actor TEXT NOT NULL);
            CREATE TABLE events(seq INTEGER PRIMARY KEY,kind TEXT NOT NULL,object_hash TEXT NOT NULL,actor TEXT NOT NULL,detail TEXT NOT NULL,at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions BEGIN SELECT RAISE(ABORT,'immutable revision'); END;
            CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions BEGIN SELECT RAISE(ABORT,'immutable revision'); END;
            CREATE TRIGGER proposals_no_update BEFORE UPDATE ON proposals BEGIN SELECT RAISE(ABORT,'immutable proposal'); END;
            CREATE TRIGGER proposals_no_delete BEFORE DELETE ON proposals BEGIN SELECT RAISE(ABORT,'immutable proposal'); END;
            CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append-only audit'); END;
            CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append-only audit'); END;
            ''')
            revision = digest(document)
            db.execute('INSERT INTO revisions VALUES(?,?,?,?)',(revision,1,None,encode(document).decode()))
            db.execute('INSERT INTO head VALUES(1,?,?,?,?,?,?)',(revision,owner,public_key,key_sha256,revision,signature))
            event(db,'INITIALIZED',revision,owner,{'scope':'key-holder-approved local source state; no native authorization','owner_key_sha256':key_sha256,'signature_b64':base64.b64encode(signature).decode()})
        os.link(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
    return {'state':'INITIALIZED_SIGNED_SOURCE','revision':revision,'owner_key_sha256':key_sha256}


def document_at(db, revision):
    row = db.execute('SELECT document FROM revisions WHERE hash=?',(revision,)).fetchone()
    if row is None:
        raise ValueError('unknown base revision')
    document = json.loads(row[0]); validate(document)
    if digest(document) != revision:
        raise ValueError('revision content/hash mismatch')
    return document


def replace(document, patch):
    if not isinstance(patch,list) or not 1 <= len(patch) <= 32:
        raise ValueError('patch requires 1..32 whole-component replacements')
    by_id = {item['id']:item for item in document['components']}
    ids = set()
    for item in patch:
        if not isinstance(item,dict) or item.get('id') not in by_id or item['id'] in ids:
            raise ValueError('unknown/duplicate target; additions and deletions require a separate reviewed intake')
        before = by_id[item['id']]
        if any(item.get(k) != before[k] for k in ('source_element_id','host_id','kind')):
            raise ValueError('identity reuse or host/type reassignment forbidden')
        by_id[item['id']] = item; ids.add(item['id'])
    result = {**document, 'components':[by_id[item['id']] for item in document['components']]}
    return validate(result)


def propose(path, base, patch, actor, rationale, evidence):
    if not all(isinstance(s,str) and 0 < len(s) <= 2000 for s in (actor,rationale,evidence)):
        raise ValueError('actor, rationale and source evidence are required')
    with transaction(path) as db:
        original = document_at(db,base)
        proposed = replace(original,patch)
        if proposed == original:
            raise ValueError('empty change')
        ident = digest({'base':base,'patch':patch,'actor':actor,'rationale':rationale,'evidence':evidence})
        if db.execute('SELECT 1 FROM proposals WHERE hash=?',(ident,)).fetchone() is None:
            db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',(ident,base,encode(patch).decode(),rationale,evidence,actor))
            event(db,'PROPOSED',ident,actor,{'base':base,'affected_ids':[i['id'] for i in patch]})
        owner,key,key_sha256,message=approval_context(db,ident,'APPROVE')
    return {'state':'PROPOSED','proposal':ident,'base':base,'patch':patch,'proposed_document_sha256':digest(proposed),
            'drawing_impact':'UNKNOWN_UNLESS_EXPLICITLY_INDEXED','approval_payload':message.decode(),'owner_key_sha256':key_sha256}


def approval_context(db, proposal, action):
    owner,public_key,key_sha256=db.execute('SELECT owner,public_key,key_sha256 FROM head WHERE id=1').fetchone()
    row=db.execute('SELECT base,patch,rationale,evidence,actor FROM proposals WHERE hash=?',(proposal,)).fetchone()
    if row is None:raise ValueError('unknown proposal')
    base,raw_patch,rationale,evidence,actor=row
    if digest({'base':base,'patch':json.loads(raw_patch),'actor':actor,'rationale':rationale,'evidence':evidence})!=proposal:
        raise ValueError('proposal content/hash mismatch')
    project=document_at(db,base)['project_id']
    return owner,public_key,key_sha256,payload(action,project,proposal,key_sha256,owner)


def approve(path, proposal, actor, signature):
    with transaction(path) as db:
        owner,key,key_sha256,message=approval_context(db,proposal,'APPROVE')
        if actor!=owner or verify_signature(key,signature,message)!=key_sha256:
            raise ValueError('owner key/signature does not match')
        detail={'approval_payload_sha256':__import__('hashlib').sha256(message).hexdigest(),'signature_b64':base64.b64encode(signature).decode(),
                'owner_key_sha256':key_sha256}
        previous=db.execute("SELECT detail FROM events WHERE kind='APPROVED' AND object_hash=? ORDER BY seq DESC LIMIT 1",(proposal,)).fetchone()
        if previous is None or json.loads(previous[0])!=detail:event(db,'APPROVED',proposal,actor,detail)
    return {'state':'APPROVED_SIGNED_PROPOSAL','proposal':proposal,'owner_key_sha256':key_sha256,'native_host_authorization':False}


def commit(path, proposal):
    with transaction(path) as db:
        previous = db.execute("SELECT detail FROM events WHERE kind='COMMITTED' AND object_hash=?",(proposal,)).fetchone()
        if previous:
            return json.loads(previous[0])
        if db.execute("SELECT 1 FROM events WHERE kind='REJECTED_OWNER' AND object_hash=?",(proposal,)).fetchone():
            raise ValueError('proposal was rejected by owner')
        approved = db.execute("SELECT actor,detail FROM events WHERE kind='APPROVED' AND object_hash=? ORDER BY seq DESC LIMIT 1",(proposal,)).fetchone()
        if approved is None:
            raise ValueError('exact proposal has no recorded owner approval')
        owner,key,key_sha256,message=approval_context(db,proposal,'APPROVE')
        proof=json.loads(approved[1])
        try: signature=base64.b64decode(proof['signature_b64'],validate=True)
        except (KeyError,ValueError,TypeError): raise ValueError('malformed approval proof') from None
        if approved[0]!=owner or verify_signature(key,signature,message)!=key_sha256:raise ValueError('invalid stored approval signature')
        base, raw_patch = db.execute('SELECT base,patch FROM proposals WHERE hash=?',(proposal,)).fetchone()
        patch = json.loads(raw_patch)
        current = db.execute('SELECT hash FROM head WHERE id=1').fetchone()[0]
        original = document_at(db,base); head = document_at(db,current)
        original_ids = {i['id']:i for i in original['components']}
        current_ids = {i['id']:i for i in head['components']}
        conflicts = [i['id'] for i in patch if current_ids.get(i['id']) != original_ids.get(i['id'])]
        if conflicts:
            result={'state':'CONFLICT','proposal':proposal,'head':current,'conflicting_ids':conflicts}
            event(db,'REJECTED_CONFLICT',proposal,approved[0],result)
            return result
        merged = replace(head,patch)
        revision = digest(merged)
        seq = db.execute('SELECT MAX(seq)+1 FROM revisions').fetchone()[0]
        db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?)',(revision,seq,current,encode(merged).decode()))
        db.execute('UPDATE head SET hash=? WHERE id=1',(revision,))
        result={'state':'COMMITTED','proposal':proposal,'revision':revision,'previous':current,'rebased':base != current}
        event(db,'COMMITTED',proposal,approved[0],result)
    return result


def reject(path, proposal, actor, signature):
    with transaction(path) as db:
        owner,key,key_sha256,message=approval_context(db,proposal,'REJECT')
        if actor!=owner or verify_signature(key,signature,message)!=key_sha256:raise ValueError('owner rejection signature required')
        if db.execute("SELECT 1 FROM events WHERE kind='COMMITTED' AND object_hash=?",(proposal,)).fetchone():
            raise ValueError('already committed; use a restore proposal')
        event(db,'REJECTED_OWNER',proposal,actor,{'signature_b64':base64.b64encode(signature).decode(),'owner_key_sha256':key_sha256})
    return {'state':'REJECTED','proposal':proposal}


def restore_proposal(path, target, actor, rationale, evidence):
    with transaction(path) as db:
        head = db.execute('SELECT hash FROM head WHERE id=1').fetchone()[0]
        target_document = document_at(db,target)
    return propose(path,head,target_document['components'],actor,rationale,evidence)


def head_revision(path, expected_key):
    with transaction(path) as db:
        current,owner,key,key_sha256,root,signature=db.execute('SELECT hash,owner,public_key,key_sha256,root_hash,initial_signature FROM head WHERE id=1').fetchone()
        initial=document_at(db,root)
        if key_sha256!=expected_key or verify_signature(key,signature,payload('INITIALIZE',initial['project_id'],root,key_sha256,owner))!=key_sha256:
            raise ValueError('canonical owner key/initialization signature mismatch')
        document_at(db,current)
    return current


def inspect(path, audit_limit=100):
    with transaction(path) as db:
        head, owner = db.execute('SELECT hash,owner FROM head WHERE id=1').fetchone()
        document = document_at(db,head)
        if type(audit_limit)!=int or not 1<=audit_limit<=1000:raise ValueError('audit limit must be 1..1000')
        key_sha256=db.execute('SELECT key_sha256 FROM head WHERE id=1').fetchone()[0]
        audit = [dict(zip(('seq','kind','hash','actor','detail','at'),r)) for r in reversed(list(db.execute('SELECT * FROM events ORDER BY seq DESC LIMIT ?',(audit_limit,))))]
        total=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    return {'state':'LOCAL_STATE_ONLY','revision':head,'owner':owner,'document':document,'audit':audit,'audit_total':total,'audit_truncated':total>len(audit),'owner_key_sha256':key_sha256,
            'trust_boundary':'Detached owner-key signatures and trusted OS/file storage; no human-presence/professional/native-host authorization claim'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('request',type=Path);init.add_argument('--owner',required=True);init.add_argument('--public-key',type=Path,required=True);init.add_argument('--signature',type=Path,required=True)
    prep=sub.add_parser('prepare-init');prep.add_argument('request',type=Path);prep.add_argument('--owner',required=True);prep.add_argument('--public-key',type=Path,required=True);prep.add_argument('--payload-out',type=Path,required=True)
    prop=sub.add_parser('propose');prop.add_argument('base');prop.add_argument('patch',type=Path);prop.add_argument('--actor',required=True);prop.add_argument('--rationale',required=True);prop.add_argument('--evidence',required=True);prop.add_argument('--payload-out',type=Path)
    app=sub.add_parser('approve');app.add_argument('proposal');app.add_argument('--owner',required=True);app.add_argument('--signature',type=Path,required=True)
    com=sub.add_parser('commit');com.add_argument('proposal')
    rej=sub.add_parser('reject');rej.add_argument('proposal');rej.add_argument('--owner',required=True);rej.add_argument('--signature',type=Path,required=True)
    rest=sub.add_parser('restore');rest.add_argument('revision');rest.add_argument('--actor',required=True);rest.add_argument('--rationale',required=True);rest.add_argument('--evidence',required=True)
    sub.add_parser('inspect')
    rejection=sub.add_parser('prepare-rejection');rejection.add_argument('proposal');rejection.add_argument('--payload-out',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='init': result=initialize(args.database,load(args.request),args.owner,public_key=read_file(args.public_key,max_bytes=4096),signature=read_file(args.signature,max_bytes=64))
        elif args.command=='prepare-init':
            message=initialization_payload(load(args.request),args.owner,read_file(args.public_key,max_bytes=4096))
            with args.payload_out.open('xb') as output:output.write(message)
            result={'state':'INITIALIZATION_PAYLOAD_ONLY','payload':message.decode()}
        elif args.command=='propose': result=propose(args.database,args.base,json.loads(read_file(args.patch)),args.actor,args.rationale,args.evidence)
        elif args.command=='approve': result=approve(args.database,args.proposal,args.owner,read_file(args.signature,max_bytes=64))
        elif args.command=='commit': result=commit(args.database,args.proposal)
        elif args.command=='reject': result=reject(args.database,args.proposal,args.owner,read_file(args.signature,max_bytes=64))
        elif args.command=='restore': result=restore_proposal(args.database,args.revision,args.actor,args.rationale,args.evidence)
        elif args.command=='prepare-rejection':
            with transaction(args.database) as db:_,_,_,message=approval_context(db,args.proposal,'REJECT')
            with args.payload_out.open('xb') as output:output.write(message)
            result={'state':'REJECTION_PAYLOAD_ONLY','payload':message.decode()}
        else: result=inspect(args.database)
        if args.command=='propose' and args.payload_out is not None:
            with args.payload_out.open('xb') as output:output.write(result['approval_payload'].encode())
        print(json.dumps(result,indent=2));return 2 if result['state']=='CONFLICT' else 0
    except (ValueError,OSError,sqlite3.Error) as exc:
        print(json.dumps({'state':'BLOCKED','error':str(exc)}));return 1


if __name__=='__main__':
    raise SystemExit(main())
