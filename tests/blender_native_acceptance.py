"""Run inside a fresh Blender process on a generated sample, never on a client model.

Usage: Blender --background --factory-startup --disable-autoexec --python-exit-code 1
  --python tests/blender_native_acceptance.py -- /absolute/generated-package
Creates only private temporary corrupted copies, then deletes those owned test copies.
"""
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'skills/architectural-drawing-generation/scripts/blender_native_worker.py'
spec = importlib.util.spec_from_file_location('gridline_worker_acceptance', path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
source = Path(sys.argv[sys.argv.index('--') + 1]).resolve(strict=True)
scene = json.loads((source / 'scene.json').read_text())
expected = {x['name']: x for x in worker.geometry_entries(scene)}
results = []
for fault in ('rotation', 'parent_transform', 'glb_identity', 'material', 'duplicate_face', 'missing_face', 'normal', 'lintel', 'phantom', 'glb_duplicate_face', 'glb_lintel'):
    with tempfile.TemporaryDirectory(prefix='gridline-native-fault-') as tmp:
        out = Path(tmp)
        shutil.copyfile(source / 'model.blend', out / 'model.blend')
        shutil.copyfile(source / 'model.glb', out / 'model.glb')
        bpy.ops.wm.open_mainfile(filepath=str(out / 'model.blend'))
        obj = next(x for x in bpy.data.objects if x.type == 'MESH' and expected[x.name]['kind'] == 'wall')
        if fault.removeprefix('glb_') in ('duplicate_face','missing_face','normal'):
            vertices=[list(v.co) for v in obj.data.vertices]
            faces=[list(p.vertices) for p in obj.data.polygons]
            if fault.endswith('duplicate_face'): faces.append(faces[0])
            elif fault=='missing_face': faces.pop()
            else: faces[0].reverse()
            mesh=bpy.data.meshes.new('CorruptFaces');mesh.from_pydata(vertices,[],faces);mesh.update()
            for m in obj.data.materials:mesh.materials.append(m)
            obj.data=mesh
        elif fault in ('lintel','glb_lintel'):
            # E1/W01: lower the actual 2.4 m opening head, preserving exterior bounds.
            moved=[v for v in obj.data.vertices if 4.2-1e-4<=v.co.x<=6.2+1e-4 and abs(v.co.y)<=.151 and abs(v.co.z-2.4)<1e-4]
            assert moved, 'fixture must contain the E1/W01 aperture head'
            for vertex in moved:vertex.co.z-=.1
        elif fault=='phantom':
            extra=obj.copy();extra.data=obj.data.copy();extra.name='Phantom thin helper'
            extra.scale.x=.001;extra['gridline_role']='helper';bpy.context.scene.collection.objects.link(extra)
        elif fault == 'rotation':
            obj.rotation_euler.z += math.pi / 2
        elif fault == 'parent_transform':
            parent = bpy.data.objects.new('FaultParent', None)
            bpy.context.collection.objects.link(parent)
            obj.parent = parent
            parent.location.x = 2
        elif fault == 'material':
            obj.data.materials.clear()
        elif fault == 'glb_identity':
            del obj['gridline_id']
            bpy.ops.export_scene.gltf(filepath=str(out / 'model.glb'), export_format='GLB',
                                       export_extras=True, export_cameras=False, export_lights=False)
        if fault.startswith('glb_') and fault!='glb_identity':
            bpy.ops.export_scene.gltf(filepath=str(out / 'model.glb'), export_format='GLB',
                                       export_extras=True, export_cameras=False, export_lights=False)
        if fault=='glb_duplicate_face':
            # Seed the actual binary; Blender's exporter may sanitize duplicate bpy faces.
            from glb_qa import read_glb
            doc,_=read_glb(out/'model.glb')
            primitive=doc['meshes'][0]['primitives'][0]
            a=doc['accessors'][primitive['indices']];view=doc['bufferViews'][a['bufferView']]
            raw=bytearray((out/'model.glb').read_bytes())
            binary_start=12+8+struct.unpack_from('<I',raw,12)[0]+8
            size={5121:1,5123:2,5125:4}[a['componentType']]
            start=binary_start+view.get('byteOffset',0)+a.get('byteOffset',0)
            end=start+(a['count']-3)*size
            raw[end:end+3*size]=raw[start:start+3*size]
            (out/'model.glb').write_bytes(raw)
        if not fault.startswith('glb_'):
            bpy.ops.wm.save_as_mainfile(filepath=str(out / 'model.blend'), check_existing=False)
        try:
            worker.verify(scene, out)
        except ValueError as exc:
            results.append({'fault': fault, 'status': 'REJECTED', 'reason': str(exc)})
        else:
            raise AssertionError(f'critical false PASS: {fault}')
print('GRIDLINE_NATIVE_ADVERSE_RESULTS=' + json.dumps(results, sort_keys=True))
