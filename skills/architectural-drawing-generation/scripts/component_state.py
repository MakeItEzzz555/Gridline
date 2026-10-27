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
            connection.execute('PRAGMA user_version=3')
        elif connection.execute('PRAGMA application_id').fetchone()[0]!=1196573489 or connection.execute('PRAGMA user_version').fetchone()[0]!=3:
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
            CREATE TABLE revisions(hash TEXT PRIMARY KEY,seq INTEGER UNIQUE NOT NULL,parent TEXT,document TEXT NOT NULL,proposal TEXT,signature BLOB);
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
            db.execute('INSERT INTO revisions VALUES(?,?,?,?,?,?)',(revision,1,None,encode(document).decode(),None,None))
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


BUILDING_GROUPS=('levels','walls','openings','rooms')


def patch_groups(patch):
    groups={'components':patch} if isinstance(patch,list) else patch
    if not isinstance(groups,dict) or not groups or set(groups)-{'components',*BUILDING_GROUPS}:
        raise ValueError('typed patch must contain components/levels/walls/openings/rooms only')
    if any(not isinstance(items,list) or not 1<=len(items)<=32 for items in groups.values()) or sum(map(len,groups.values()))>32:
        raise ValueError('patch requires1..32 whole-element replacements')
    return groups


def elements(document,group):
    if group=='components':return document['components']
    if 'building' not in document:raise ValueError('building patches require an explicit canonical building')
    return document['building'][group]


def replace(document, patch):
    result=json.loads(encode(document))
    for group,items in patch_groups(patch).items():
        target=elements(result,group);by_id={item['id']:i for i,item in enumerate(target)};seen=set()
        for item in items:
            if not isinstance(item,dict) or item.get('id') not in by_id or item['id'] in seen:
                raise ValueError('unknown/duplicate target; additions and deletions require reviewed intake')
            before=target[by_id[item['id']]]
            fixed=('source_element_id','host_id','kind') if group=='components' else ('wall','kind') if group=='openings' else ('level',) if group in ('walls','rooms') else ()
            if set(item)!=set(before) or any(item.get(k)!=before.get(k) for k in fixed):
                raise ValueError('required attributes/identity/host/type/level reassignment forbidden')
            target[by_id[item['id']]]=item;seen.add(item['id'])
    return validate(result)


def impact(before,after,patch):
    from revision_impact import analyze
    changes=[]
    for group,items in patch_groups(patch).items():
        old={i['id']:i for i in elements(before,group)}
        changes.extend({'group':group,'id':i['id'],'before':old[i['id']],'after':i} for i in items if i!=old[i['id']])
    indexed=analyze(before['building'],after['building']) if 'building' in before else {'affected_indexed_sheets':[],'schedules_to_recheck':[]}
    sheets=set(indexed['affected_indexed_sheets']);schedules=set(indexed['schedules_to_recheck'])
    if 'building' in before:
        walls={i['id']:i for i in before['building']['walls']}
        changed_levels={c['id'] for c in changes if c['group']=='levels'}
        changed_walls={c['id'] for c in changes if c['group']=='walls'}|{w['id'] for w in walls.values() if w['level'] in changed_levels}
        dependent_openings={o['id'] for o in before['building']['openings'] if o['wall'] in changed_walls}
        if changed_walls:schedules.update(('door-schedule.csv','window-schedule.csv','room-schedule.csv'))
        for sheet in before['building']['sheets']:
            refs=sheet.get('references',{})
            if changed_levels.intersection(refs.get('levels',[])) or changed_walls.intersection(refs.get('walls',[])) or dependent_openings.intersection(refs.get('openings',[])):sheets.add(sheet['number'])
        for change in changes:
            if change['group']!='components':continue
            for item in (change['before'],change['after']):
                level=walls[item['host_id']]['level'] if item['host_id'] else item['level_id']
                for sheet in before['building']['sheets']:
                    refs=sheet.get('references',{})
                    if sheet.get('level')==level or item['source_element_id'] in refs.get('openings',[]) or item['host_id'] in refs.get('walls',[]):sheets.add(sheet['number'])
    return {'changes':changes,'affected_indexed_sheets':sorted(sheets),'schedules_to_recheck':sorted(schedules),
            'unindexed_drawings_and_host_families':'UNKNOWN; separate review required','native_host_authorization':False}


def propose(path, base, patch, actor, rationale, evidence):
    if not all(isinstance(s,str) and 0 < len(s) <= 2000 for s in (actor,rationale,evidence)):
        raise ValueError('actor, rationale and source evidence are required')
    with transaction(path) as db:
        authenticated_revision(db,db.execute('SELECT key_sha256 FROM head WHERE id=1').fetchone()[0],base)
        original = document_at(db,base)
        proposed = replace(original,patch)
        if proposed == original:
            raise ValueError('empty change')
        ident = digest({'base':base,'patch':patch,'actor':actor,'rationale':rationale,'evidence':evidence})
        affected=impact(original,proposed,patch)
        if db.execute('SELECT 1 FROM proposals WHERE hash=?',(ident,)).fetchone() is None:
            db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',(ident,base,encode(patch).decode(),rationale,evidence,actor))
            event(db,'PROPOSED',ident,actor,{'base':base,'proposed_document_sha256':digest(proposed),'impact':affected})
        owner,key,key_sha256,message=approval_context(db,ident,'APPROVE')
    return {'state':'PROPOSED','proposal':ident,'base':base,'patch':patch,'proposed_document_sha256':digest(proposed),
            'drawing_impact':affected,'approval_payload':message.decode(),'owner_key_sha256':key_sha256}


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
        authenticated_revision(db,db.execute('SELECT key_sha256 FROM head WHERE id=1').fetchone()[0])
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
        conflicts=[]
        for group,items in patch_groups(patch).items():
            original_ids={i['id']:i for i in elements(original,group)};current_ids={i['id']:i for i in elements(head,group)}
            conflicts.extend(group+'/'+i['id'] for i in items if current_ids.get(i['id'])!=original_ids.get(i['id']))
        if conflicts:
            result={'state':'CONFLICT','proposal':proposal,'head':current,'conflicting_ids':conflicts}
            event(db,'REJECTED_CONFLICT',proposal,approved[0],result)
            return result
        merged = replace(head,patch)
        revision = digest(merged)
        seq = db.execute('SELECT MAX(seq)+1 FROM revisions').fetchone()[0]
        db.execute('INSERT OR IGNORE INTO revisions VALUES(?,?,?,?,?,?)',(revision,seq,current,encode(merged).decode(),proposal,signature))
        db.execute('UPDATE head SET hash=? WHERE id=1',(revision,))
        result={'state':'COMMITTED','proposal':proposal,'revision':revision,'previous':current,'rebased':base != current,'impact':impact(head,merged,patch)}
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
        authenticated_revision(db,db.execute('SELECT key_sha256 FROM head WHERE id=1').fetchone()[0],target)
        target_document = document_at(db,target);current_document=document_at(db,head)
    patch={}
    for group in ('components',*(BUILDING_GROUPS if 'building' in target_document else ())):
        current={i['id']:i for i in elements(current_document,group)}
        changed=[i for i in elements(target_document,group) if i!=current.get(i['id'])]
        if changed:patch[group]=changed
    return propose(path,head,patch,actor,rationale,evidence)


def authenticated_revision(db, expected_key, revision=None):
    header=db.execute('SELECT hash,owner,public_key,key_sha256,root_hash,initial_signature FROM head WHERE id=1').fetchone()
    if header is None:raise ValueError('canonical state header is missing')
    current,owner,key,key_sha256,root,signature=header
    initial=document_at(db,root)
    if key_sha256!=expected_key or verify_signature(key,signature,payload('INITIALIZE',initial['project_id'],root,key_sha256,owner))!=key_sha256:
        raise ValueError('canonical owner key/initialization signature mismatch')
    # Content hashes are identities, not transition counters. A legitimate
    # restore may reuse the root hash, so the signed revision DAG alone cannot
    # detect a head pointer silently rewound to previously approved content.
    latest=db.execute("SELECT object_hash,actor,detail FROM events WHERE kind='COMMITTED' ORDER BY seq DESC LIMIT 1").fetchone()
    previous=None
    if latest is not None:
        try: receipt=json.loads(latest[2])
        except (TypeError,ValueError):raise ValueError('latest committed event is malformed') from None
        if (not isinstance(receipt,dict) or receipt.get('state')!='COMMITTED'
                or receipt.get('proposal')!=latest[0] or receipt.get('revision')!=current
                or not isinstance(receipt.get('previous'),str)
                or receipt['previous']==current):
            raise ValueError('canonical head does not match latest committed event')
        previous=receipt['previous']
        prior=db.execute("SELECT detail FROM events WHERE kind='COMMITTED' AND seq < (SELECT MAX(seq) FROM events WHERE kind='COMMITTED') ORDER BY seq DESC LIMIT 1").fetchone()
        try: expected_previous=json.loads(prior[0])['revision'] if prior else root
        except (TypeError,ValueError,KeyError):raise ValueError('prior committed event is malformed') from None
        if previous!=expected_previous:
            raise ValueError('latest committed event previous state does not follow audit history')
    latest_base=db.execute('SELECT base FROM proposals WHERE hash=?',(latest[0],)).fetchone() if latest else None
    if latest and latest_base is None:raise ValueError('latest committed event has no recorded proposal')
    target=current if revision is None else revision
    verified={root:initial}
    pending=[(ident,False) for ident in {target,current,previous,latest_base[0] if latest_base else None} if ident is not None]
    active=set()
    while pending:
        ident,ready=pending.pop()
        if ident in verified:continue
        row=db.execute('SELECT parent,proposal,signature FROM revisions WHERE hash=?',(ident,)).fetchone()
        if row is None or not all(row):raise ValueError('canonical revision lacks signed transition proof')
        parent,proposal,proof=row
        approver,public,fingerprint,message=approval_context(db,proposal,'APPROVE')
        base,patch=db.execute('SELECT base,patch FROM proposals WHERE hash=?',(proposal,)).fetchone();patch=json.loads(patch)
        if not ready:
            if ident in active:raise ValueError('canonical revision cycle')
            active.add(ident);pending.append((ident,True))
            pending.extend((dependency,False) for dependency in {parent,base} if dependency not in verified)
            continue
        if approver!=owner or fingerprint!=expected_key or verify_signature(public,proof,message)!=expected_key:raise ValueError('canonical revision signature mismatch')
        if db.execute("SELECT 1 FROM events WHERE kind='REJECTED_OWNER' AND object_hash=?",(proposal,)).fetchone():raise ValueError('canonical revision uses a rejected proposal')
        before,original=verified[parent],verified[base]
        for group,items in patch_groups(patch).items():
            old={i['id']:i for i in elements(original,group)};head={i['id']:i for i in elements(before,group)}
            if any(head.get(i['id'])!=old.get(i['id']) for i in items):raise ValueError('canonical revision bypassed a stale conflict')
        document=document_at(db,ident)
        if document!=replace(before,patch) or document['project_id']!=initial['project_id']:raise ValueError('canonical revision differs from approved patch')
        verified[ident]=document;active.remove(ident)
    if latest is None and current!=root:
        raise ValueError('canonical head has no latest committed event')
    if latest:
        proposal=latest[0]
        approved=db.execute("SELECT actor,detail FROM events WHERE kind='APPROVED' AND object_hash=? ORDER BY seq DESC LIMIT 1",(proposal,)).fetchone()
        if latest[1]!=owner or approved is None or approved[0]!=owner:
            raise ValueError('latest committed event lacks owner approval')
        if db.execute("SELECT 1 FROM events WHERE kind='REJECTED_OWNER' AND object_hash=?",(proposal,)).fetchone():
            raise ValueError('latest committed event uses a rejected proposal')
        approver,public,fingerprint,message=approval_context(db,proposal,'APPROVE')
        try: proof=base64.b64decode(json.loads(approved[1])['signature_b64'],validate=True)
        except (TypeError,ValueError,KeyError):raise ValueError('latest committed event has malformed approval') from None
        if approver!=owner or fingerprint!=key_sha256 or verify_signature(public,proof,message)!=key_sha256:
            raise ValueError('latest committed event has invalid approval signature')
        base,raw_patch=db.execute('SELECT base,patch FROM proposals WHERE hash=?',(proposal,)).fetchone()
        patch=json.loads(raw_patch)
        for group,items in patch_groups(patch).items():
            original={i['id']:i for i in elements(verified[base],group)}
            prior={i['id']:i for i in elements(verified[previous],group)}
            if any(prior.get(i['id'])!=original.get(i['id']) for i in items):
                raise ValueError('latest committed event bypassed a stale conflict')
        if (replace(verified[previous],patch)!=verified[current]
                or receipt.get('rebased')!=(base!=previous)):
            raise ValueError('latest committed event does not match approved transition')
    return target


def head_revision(path, expected_key, revision=None):
    with transaction(path) as db:return authenticated_revision(db,expected_key,revision)


def inspect(path, audit_limit=100):
    with transaction(path) as db:
        row=db.execute('SELECT hash,owner,key_sha256 FROM head WHERE id=1').fetchone()
        if row is None:raise ValueError('canonical state header is missing')
        head,owner,key_sha256=row
        authenticated_revision(db,key_sha256)
        document = document_at(db,head)
        if type(audit_limit)!=int or not 1<=audit_limit<=1000:raise ValueError('audit limit must be 1..1000')
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
