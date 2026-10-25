"""IFC trust-boundary tests only; actual engine/native acceptance is separate."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation'
sys.path.insert(0,str(HERE/'scripts'))
import component_ifc as exporter
from component_spec import digest,encode


class IFCInputTests(unittest.TestCase):
    def test_unknown_or_ambiguous_project_requirements_rejected(self):
        good={'schema':'gridline-ifc-requirements.v1','project_id':'test-project','required_properties':['SourceElementId','Kind'],'allow_unknown_materials':False}
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'requirements.json';path.write_bytes(encode(good))
            self.assertEqual(exporter.requirements(path,'test-project'),good)
            for change in ({'project_id':'other'},{'required_properties':[]},{'required_properties':['Invented']},{'allow_unknown_materials':1},{'guessed_crs':'unknown'}):
                path.write_bytes(encode({**good,**change}))
                with self.assertRaises(ValueError):exporter.requirements(path,'test-project')

    def test_bundle_requires_trusted_receipt_signed_source_and_owner_key(self):
        request=json.loads((HERE/'references/example-components.json').read_text());key='a'*64
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            content={'request.json':encode(request),'components.blend':b'fixture','components.glb':b'fixture',
                'meshes.json':encode({'request_sha256':digest(request)}),'verification.json':encode({'state':'PASS','request_sha256':digest(request)})}
            for name,data in content.items():(folder/name).write_bytes(data)
            receipt={'schema':'gridline-component-receipt.v1','state':'VERIFIED_VISUAL_COMPONENTS','request_sha256':digest(request),
                'files':{name:hashlib.sha256(data).hexdigest() for name,data in content.items()},'canonical_state_revision':None,'canonical_owner_key_sha256':None}
            def pin():
                data=encode(receipt);(folder/'receipt.json').write_bytes(data);return hashlib.sha256(data).hexdigest()
            with self.assertRaisesRegex(ValueError,'signed canonical-source'):exporter.bundle(folder,pin(),key)
            receipt.update(canonical_state_revision=digest(request),canonical_owner_key_sha256=key);trusted=pin()
            self.assertEqual(exporter.bundle(folder,trusted,key)[0],request)
            with self.assertRaises(ValueError):exporter.bundle(folder,'0'*64,key)
            with self.assertRaises(ValueError):exporter.bundle(folder,trusted,'b'*64)
            (folder/'meshes.json').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'bundle changed'):exporter.bundle(folder,trusted,key)

    def test_guid_source_namespace_is_stable_and_project_scoped(self):
        self.assertEqual(exporter.stable_uuid('P','element/E1'),exporter.stable_uuid('P','element/E1'))
        self.assertNotEqual(exporter.stable_uuid('P','element/E1'),exporter.stable_uuid('Q','element/E1'))
        self.assertNotEqual(exporter.stable_uuid('P','element/E1'),exporter.stable_uuid('P','opening/E1'))

    def test_native_geometry_buffers_are_materialized_only_once(self):
        class Geometry:
            def __init__(self):self.reads={'verts':0,'faces':0}
            @property
            def verts(self):self.reads['verts']+=1;return (0.,0.,0.,1.,0.,0.,0.,1.,0.)
            @property
            def faces(self):self.reads['faces']+=1;return (0,1,2)
        geometry=Geometry()
        self.assertEqual(exporter.geometry_mesh(geometry),([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]],[[0,1,2]]))
        self.assertEqual(geometry.reads,{'verts':1,'faces':1})
