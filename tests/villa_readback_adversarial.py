"""Blender-only faults in disposable copies of a generated villa package.

Blender --background --factory-startup --disable-autoexec --python-exit-code 1
 --python tests/villa_readback_adversarial.py -- GENERATED_PACKAGE [FAULT ...]
"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import bpy

path=Path(__file__).with_name('villa_topology_acceptance.py')
spec=importlib.util.spec_from_file_location('villa_acceptance',path)
reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
args=sys.argv[sys.argv.index('--')+1:];source=Path(args[0]).resolve(strict=True)
faults=args[1:] or ['modifier','shape_key','hidden_render','excluded_collection',
                   'extra_cutaway_fragment','missing_cutaway_member','cutaway_modifier']
results=[]
for fault in faults:
    with tempfile.TemporaryDirectory(prefix='gridline-villa-readback-fault-') as tmp:
        out=Path(tmp)
        for name in ('Villa.blend','Villa.glb','villa.scene.json'):shutil.copyfile(source/name,out/name)
        bpy.ops.wm.open_mainfile(filepath=str(out/'Villa.blend'),load_ui=False)
        full=bpy.data.scenes['01 Exterior - complete villa']
        cut=bpy.data.scenes['02 Ground floor - ceiling removed']
        obj=next(o for o in full.objects if o.get('gridline_role')=='wall')
        if fault in ('modifier','cutaway_modifier'):
            if fault=='cutaway_modifier':obj=next(o for o in cut.objects if o.get('gridline_role')=='wall')
            obj.modifiers.new('Adverse displacement','DISPLACE').strength=.2
        elif fault=='shape_key':
            obj.shape_key_add(name='Basis');key=obj.shape_key_add(name='Adverse');key.data[0].co.x+=.2;key.value=1
        elif fault=='hidden_render':obj.hide_render=True
        elif fault=='excluded_collection':
            collection=bpy.data.collections.new('Adverse excluded');full.collection.children.link(collection)
            for current in list(obj.users_collection):current.objects.unlink(obj)
            collection.objects.link(obj)
            full.view_layers[0].layer_collection.children[collection.name].exclude=True
        elif fault=='extra_cutaway_fragment':
            extra=next(o for o in cut.objects if o.type=='MESH').copy()
            extra.data=extra.data.copy();extra.name='Adverse leftover wall fragment';cut.collection.objects.link(extra)
        elif fault=='missing_cutaway_member':
            victim=next(o for o in cut.objects if o.type=='MESH' and not o.name.startswith('Cutaway Ground joined_'))
            bpy.data.objects.remove(victim,do_unlink=True)
        else:raise ValueError('unsupported fault')
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'Villa.blend'),check_existing=False)
        try:reader.verify(source,out)
        except ValueError as exc:results.append(dict(fault=fault,status='REJECTED',reason=str(exc)))
        else:results.append(dict(fault=fault,status='FALSE_PASS'))
print('VILLA_ADVERSE_RESULTS='+json.dumps(results))
assert all(r['status']=='REJECTED' for r in results),'critical villa readback false PASS'
