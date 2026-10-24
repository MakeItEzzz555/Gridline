"""Raw binary adversarial fixtures, independent of Blender import repair."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/scripts'))
from glb_qa import check_glb


def fixture():
    positions=struct.pack('<9f',0,0,0,1,0,0,0,1,0)
    normals=struct.pack('<9f',0,0,1,0,0,1,0,0,1)
    binary=positions+normals+struct.pack('<6H',0,1,2,0,1,2)
    doc=dict(asset={'version':'2.0'},buffers=[dict(byteLength=len(binary))],
             bufferViews=[dict(buffer=0,byteOffset=0,byteLength=36),dict(buffer=0,byteOffset=36,byteLength=36),dict(buffer=0,byteOffset=72,byteLength=12)],
             accessors=[dict(bufferView=0,componentType=5126,count=3,type='VEC3'),dict(bufferView=1,componentType=5126,count=3,type='VEC3'),dict(bufferView=2,componentType=5123,count=3,type='SCALAR')],
             meshes=[dict(primitives=[dict(attributes=dict(POSITION=0,NORMAL=1),indices=2)])],nodes=[dict(mesh=0)])
    return doc,binary


def pack(doc,binary):
    data=json.dumps(doc).encode();data+=b' '*(-len(data)%4);binary+=b'\0'*(-len(binary)%4)
    payload=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary
    return struct.pack('<4sII',b'glTF',2,len(payload)+12)+payload


class RawGlbTests(unittest.TestCase):
    def check(self,doc,binary):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'model.glb';p.write_bytes(pack(doc,binary));return check_glb(p)

    def test_valid_and_raw_duplicate_that_importers_can_drop(self):
        doc,binary=fixture();self.assertEqual(self.check(doc,binary)['raw_triangles'],1)
        doc['accessors'][2]['count']=6
        with self.assertRaisesRegex(ValueError,'duplicate'):self.check(doc,binary)

    def test_bad_normals_indices_and_nonfinite_positions(self):
        doc,binary=fixture()
        for corrupted in (binary[:36]+struct.pack('<9f',0,0,-1,0,0,-1,0,0,-1)+binary[72:],
                          binary[:72]+struct.pack('<6H',0,1,999,0,1,2),
                          struct.pack('<f',float('nan'))+binary[4:]):
            with self.assertRaises(ValueError):self.check(doc,corrupted)

    def test_unsupported_external_sparse_extensions_and_budgets(self):
        doc,binary=fixture()
        for mutation in (lambda d:d['buffers'][0].update(uri='../../secret'),
                         lambda d:d['accessors'][0].update(sparse={}),
                         lambda d:d.update(extensionsUsed=['KHR_draco_mesh_compression']),
                         lambda d:d['accessors'][0].update(count=10**12),
                         lambda d:d['accessors'][0].update(byteOffset=-1),
                         lambda d:d['accessors'][0].update(bufferView=-1),
                         lambda d:d['meshes'][0]['primitives'][0].update(indices=-1)):
            bad=copy.deepcopy(doc);mutation(bad)
            with self.assertRaises(ValueError):self.check(bad,binary)
