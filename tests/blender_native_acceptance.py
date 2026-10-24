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
expected = {x['name']: x for x in scene['boxes']}
results = []
for fault in ('rotation', 'parent_transform', 'glb_identity', 'material'):
    with tempfile.TemporaryDirectory(prefix='gridline-native-fault-') as tmp:
        out = Path(tmp)
        shutil.copyfile(source / 'model.blend', out / 'model.blend')
        shutil.copyfile(source / 'model.glb', out / 'model.glb')
        bpy.ops.wm.open_mainfile(filepath=str(out / 'model.blend'))
        obj = next(x for x in bpy.data.objects if x.type == 'MESH' and expected[x.name]['kind'] == 'wall')
        if fault == 'rotation':
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
        if fault != 'glb_identity':
            bpy.ops.wm.save_as_mainfile(filepath=str(out / 'model.blend'), check_existing=False)
        try:
            worker.verify(scene, out)
        except ValueError as exc:
            results.append({'fault': fault, 'status': 'REJECTED', 'reason': str(exc)})
        else:
            raise AssertionError(f'critical false PASS: {fault}')
print('GRIDLINE_NATIVE_ADVERSE_RESULTS=' + json.dumps(results, sort_keys=True))
