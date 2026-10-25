"""Strict request and atomic local proposal-state regressions; no Blender required."""
import copy
import concurrent.futures
import contextlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation'
sys.path.insert(0,str(HERE/'scripts'))
import component_spec as model
import component_state as state
import archimesh_components as bridge


def fixture():
    return json.loads((HERE/'references/example-components.json').read_text())


class ComponentRequestTests(unittest.TestCase):
    def test_all_catalog_recipes_are_explicit_valid_data(self):
        spec=fixture();self.assertEqual({i['kind'] for i in spec['components']},set(model.CATALOG))
        self.assertEqual(model.validate(spec),spec)
        self.assertEqual(model.digest(spec),model.digest(json.loads(model.encode(spec))))

    def test_untrusted_types_dimensions_identity_and_code_rejected(self):
        changes=[lambda s:s.pop('units'),lambda s:s.__setitem__('units','mm'),
            lambda s:s['components'][0]['parameters'].__setitem__('width',True),
            lambda s:s['components'][0]['parameters'].__setitem__('height',float('nan')),
            lambda s:s['components'][0]['parameters'].__setitem__('height',10**400),
            lambda s:s['components'][0]['parameters'].__setitem__('script','exec anything'),
            lambda s:s['components'][0].__setitem__('kind','room'),
            lambda s:s['components'][0].__setitem__('id','../../outside'),
            lambda s:s['components'][1].__setitem__('source_element_id',s['components'][0]['source_element_id']),
            lambda s:s['components'][0].__setitem__('position_m',[0,0]),
            lambda s:s['components'][0]['material'].__setitem__('metallic',-1)]
        for change in changes:
            spec=fixture();change(spec)
            with self.subTest(change=change),self.assertRaises(ValueError):model.validate(spec)

    def test_invalid_request_stops_before_host_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'request.json';source.write_text('{"units":"mm"}')
            with patch.object(bridge,'probe_host') as probe,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.main(['build',str(source),str(root/'out'),'--addon-source',str(root),'--approve-addon-sha256','bad']),1)
                probe.assert_not_called()
            self.assertFalse((root/'out').exists())

    def test_wrong_source_approval_stops_before_host_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'request.json';source.write_bytes(model.encode(fixture()))
            with patch.object(bridge,'probe_host') as probe,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.main(['build',str(source),str(root/'out'),'--addon-source',str(root),'--approve-addon-sha256','bad']),1)
                probe.assert_not_called()
            self.assertFalse((root/'out').exists())


    def test_hosted_requests_bind_exact_canonical_openings_levels_and_positions(self):
        base=json.loads((HERE/'references/example-house.components.json').read_text())
        model.validate(base)
        for change in (lambda s:s['components'][0].__setitem__('host_id','invented'),
                       lambda s:s['components'][0]['parameters'].__setitem__('width',1.1),
                       lambda s:s['components'][0]['position_m'].__setitem__(0,99),
                       lambda s:s['components'][0].__setitem__('rotation_deg',45),
                       lambda s:s['components'][2].pop('level_id'),
                       lambda s:s['components'][2].__setitem__('source_element_id','E1')):
            request=copy.deepcopy(base);change(request)
            with self.assertRaises(ValueError):model.validate(request)
        model.validate(json.loads((HERE/'references/example-two-level.components.json').read_text()))

    def test_secure_publication_rejects_unsafe_names_before_creating_directory(self):
        from blender_native import publish
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            for names in (('../outside',),('receipt.json',),('same','same'),(['not a basename'],)):
                with self.assertRaises(ValueError):publish(root,root/'out',{},names=names)
                self.assertFalse((root/'out').exists())

    def test_public_verify_snapshots_pinned_bytes_without_rewriting_bundle(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'bundle';out.mkdir()
            for name in bridge.OUTPUTS:
                (out/name).write_bytes(model.encode(fixture()) if name=='request.json' else b'trusted fixture bytes')
            hashes={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in bridge.OUTPUTS}
            receipt={'schema':'gridline-component-receipt.v1','state':'VERIFIED_VISUAL_COMPONENTS','files':hashes,
                'request_sha256':model.digest(fixture()),'runtime_sha256':{name:hashlib.sha256((bridge.HERE/name).read_bytes()).hexdigest() for name in bridge.RUNTIME_FILES}}
            (out/'receipt.json').write_bytes(model.encode(receipt));pin=hashlib.sha256((out/'receipt.json').read_bytes()).hexdigest()
            def run(blender,command,source,addon,snapshot,**kwargs):
                self.assertNotEqual(snapshot,out)
                for name in bridge.OUTPUTS:self.assertEqual(hashlib.sha256((snapshot/name).read_bytes()).hexdigest(),hashes[name])
                (snapshot/'verification.json').write_text('{"state":"PASS"}')
            with patch.object(bridge,'probe_host',return_value={'version':'5.2.3'}),patch.object(bridge,'run_host',side_effect=run) as host,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.main(['verify',str(out),'--expected-receipt-sha256',pin]),0);host.assert_called_once()
            self.assertEqual({name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in bridge.OUTPUTS},hashes)
            (out/'components.blend').write_bytes(b'changed')
            with patch.object(bridge,'probe_host') as probe,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(bridge.main(['verify',str(out),'--expected-receipt-sha256',pin]),1);probe.assert_not_called()



class ComponentStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('openssl'):raise unittest.SkipTest('OpenSSL required for real Ed25519 approval tests')
        cls.keys=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.keys.cleanup)
        cls.private=Path(cls.keys.name)/'test-only.pem'
        subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(cls.private)],check=True,capture_output=True)
        cls.public=subprocess.run(['openssl','pkey','-in',str(cls.private),'-pubout'],check=True,capture_output=True).stdout

    def sign(self,message):
        source=Path(self.temp.name)/'test-payload.json';signature=source.with_suffix('.sig')
        source.write_bytes(message)
        subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(self.private),'-rawin','-in',str(source),'-out',str(signature)],check=True,capture_output=True)
        return signature.read_bytes()

    def proof(self,proposal,action='APPROVE'):
        with state.transaction(self.path) as db:_,_,_,message=state.approval_context(db,proposal,action)
        return self.sign(message)

    def approve(self,proposal):
        return state.approve(self.path,proposal,'owner',self.proof(proposal))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'state.sqlite';self.spec=fixture()
        message=state.initialization_payload(self.spec,'owner',self.public)
        result=state.initialize(self.path,self.spec,'owner',public_key=self.public,signature=self.sign(message))
        self.base=result['revision'];self.fingerprint=result['owner_key_sha256']

    def proposal(self,index,width):
        item=copy.deepcopy(self.spec['components'][index]);item['parameters']['width']=width
        return state.propose(self.path,self.base,[item],'agent','measured change','synthetic test input')['proposal']

    def test_approval_rejection_and_idempotent_commit(self):
        prop=self.proposal(0,1.0)
        with self.assertRaises(ValueError):state.commit(self.path,prop)
        with self.assertRaises(ValueError):state.approve(self.path,prop,'agent',self.proof(prop))
        self.approve(prop);result=state.commit(self.path,prop)
        self.assertEqual(result,state.commit(self.path,prop))
        self.assertEqual(state.inspect(self.path)['document']['components'][0]['parameters']['width'],1.0)
        other=self.proposal(1,1.3);self.approve(other);state.reject(self.path,other,'owner',self.proof(other,'REJECT'))
        with self.assertRaises(ValueError):state.commit(self.path,other)

    def test_concurrent_same_target_accepts_one_and_rejects_stale(self):
        proposals=[self.proposal(0,1.0),self.proposal(0,1.1)]
        for prop in proposals:self.approve(prop)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda p:state.commit(self.path,p),proposals))
        self.assertEqual(sorted(r['state'] for r in results),['COMMITTED','CONFLICT'])
        self.assertEqual(sum(e['kind']=='COMMITTED' for e in state.inspect(self.path)['audit']),1)

    def test_disjoint_stale_edits_merge_with_validation(self):
        a=self.proposal(0,1.0);b=self.proposal(1,1.3)
        for prop in (a,b):self.approve(prop)
        state.commit(self.path,a);result=state.commit(self.path,b)
        self.assertTrue(result['rebased'])
        items=state.inspect(self.path)['document']['components']
        self.assertEqual([items[i]['parameters']['width'] for i in (0,1)],[1.0,1.3])

    def test_rollback_proposal_restores_exact_original_document(self):
        prop=self.proposal(0,1.0);self.approve(prop);state.commit(self.path,prop)
        rollback=state.restore_proposal(self.path,self.base,'owner','restore original','test evidence')['proposal']
        self.approve(rollback);state.commit(self.path,rollback)
        self.assertEqual(state.inspect(self.path)['document'],self.spec)

    def test_invalid_changes_and_failed_transaction_preserve_state(self):
        for field,value in (('id','invented'),('source_element_id','reused'),('host_id','invented-host'),('kind','window')):
            item=copy.deepcopy(self.spec['components'][0]);item[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                state.propose(self.path,self.base,[item],'agent','why','source')
        with self.assertRaises(RuntimeError):
            with state.transaction(self.path) as db:
                db.execute("UPDATE head SET owner='uncommitted-owner'")
                raise RuntimeError('simulated adapter failure')
        self.assertEqual(state.inspect(self.path)['revision'],self.base)
        self.assertEqual(state.inspect(self.path)['owner'],'owner')

    def test_unowned_database_is_rejected_without_modification(self):
        import hashlib
        other=Path(self.temp.name)/'other.sqlite'
        with sqlite3.connect(other) as db:db.execute('CREATE TABLE unrelated(value TEXT)')
        before=hashlib.sha256(other.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):state.inspect(other)
        self.assertEqual(hashlib.sha256(other.read_bytes()).hexdigest(),before)


    def test_approval_signature_binds_exact_proposal_action_and_owner(self):
        a=self.proposal(0,1.0);b=self.proposal(1,1.3)
        for signature in (b'',b'0'*64,self.proof(b),self.proof(a,'REJECT')):
            with self.subTest(signature=signature[:4]),self.assertRaises(ValueError):state.approve(self.path,a,'owner',signature)
        self.assertEqual(state.head_revision(self.path,self.fingerprint),self.base)
        with self.assertRaises(ValueError):state.head_revision(self.path,'0'*64)
        with state.transaction(self.path) as db:
            state.event(db,'APPROVED',a,'owner',{'signature_b64':'MA==','owner_key_sha256':self.fingerprint})
        with self.assertRaises(ValueError):state.commit(self.path,a)
        self.assertEqual(state.inspect(self.path)['revision'],self.base)

    def test_invalid_initial_signature_never_creates_database(self):
        destination=Path(self.temp.name)/'invalid.sqlite'
        with self.assertRaises(ValueError):
            state.initialize(destination,self.spec,'owner',public_key=self.public,signature=b'0'*64)
        self.assertFalse(destination.exists())
        with self.assertRaises(ValueError):
            state.initialization_payload(self.spec,'owner',self.private.read_bytes())

    def test_changed_canonical_head_blocks_preview_publication(self):
        import subprocess
        root=Path(self.temp.name);request=root/'request.json';request.write_bytes(model.encode(self.spec))
        reference=root/'pin.json';reference.write_text(json.dumps({'archive_sha256':'synthetic-test-pin','files':{}}))
        proposal=self.proposal(0,1.0);self.approve(proposal)
        def native(blender,command,source,addon,out,**kwargs):
            if command=='build':
                (out/'verification.json').write_text('{"state":"PASS"}')
                state.commit(self.path,proposal)
            return subprocess.CompletedProcess([],0,stdout='synthetic mocked host',stderr='')
        with patch.object(bridge,'REFERENCE',reference),patch.object(bridge,'inspect_source',return_value={'source_state':'SOURCE_VERIFIED','path':str(root)}),patch.object(bridge,'probe_host',return_value={'version':'5.2.3'}),patch.object(bridge,'run_host',side_effect=native),contextlib.redirect_stdout(io.StringIO()) as output:
            code=bridge.main(['build',str(request),str(root/'preview'),'--addon-source',str(root),'--approve-addon-sha256','synthetic-test-pin','--state-db',str(self.path),'--owner-key-sha256',self.fingerprint])
        self.assertEqual(code,1);self.assertIn('canonical state changed',output.getvalue())
        self.assertFalse((root/'preview').exists())

    def test_initialization_never_replaces_existing_database(self):
        import hashlib
        before=hashlib.sha256(self.path.read_bytes()).hexdigest()
        proof=self.sign(state.initialization_payload(self.spec,'owner',self.public))
        with self.assertRaises(ValueError):state.initialize(self.path,self.spec,'owner',public_key=self.public,signature=proof)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),before)

    def test_revision_and_audit_are_immutable(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with state.transaction(self.path) as db:db.execute('DELETE FROM revisions')
        with self.assertRaises(sqlite3.IntegrityError):
            with state.transaction(self.path) as db:db.execute("UPDATE events SET actor='forged'")
        self.assertEqual(state.inspect(self.path)['document'],self.spec)


if __name__=='__main__':unittest.main()
