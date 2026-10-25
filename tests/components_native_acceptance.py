# SPDX-License-Identifier: GPL-2.0-or-later
"""Disposable adverse native fixtures; run in private factory-startup Blender.

Usage: Blender --background --factory-startup --disable-autoexec --offline-mode
  --python-exit-code 1 --python tests/components_native_acceptance.py -- BUNDLE
Never opens a client scene or changes the source bundle.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile

import bpy

ROOT=Path(__file__).resolve().parents[1]
scripts=ROOT/'skills/architectural-drawing-generation/scripts'
sys.path.insert(0,str(scripts))
module=importlib.util.spec_from_file_location('components_acceptance_worker',scripts/'components_worker.py')
worker=importlib.util.module_from_spec(module);module.loader.exec_module(worker)
from component_spec import load
from glb_qa import read_glb

source=Path(sys.argv[sys.argv.index('--')+1]).resolve(strict=True)
request=load(source/'request.json')
results=[]
faults=['vertex','normal','uv','material','surface_output','emission','hidden','modifier','shape_key',
        'root_id','root_host','root_pose','root_constraint','root_animation','extra_object','extra_mesh','missing_mesh','units',
        'glb_identity','glb_material','glb_external_image','triangle_budget']
if any('asset_plan_sha256' in i['material'] for i in request['components']):
    faults+=['texture_provenance','texture_unpacked','texture_mapping','normal_strength']
with tempfile.TemporaryDirectory(prefix='gridline-components-adverse-') as temporary:
    baseline=Path(temporary)/'baseline';baseline.mkdir()
    for name in ('components.blend','components.glb','meshes.json'):
        shutil.copyfile(source/name,baseline/name)
    worker.verify(request,baseline)
    for fault in faults:
        out=Path(temporary)/fault;out.mkdir()
        for name in ('components.blend','components.glb','meshes.json'):
            shutil.copyfile(source/name,out/name)
        bpy.ops.wm.open_mainfile(filepath=str(out/'components.blend'))
        root=bpy.data.objects[request['components'][0]['id']]
        obj=next(o for o in bpy.data.objects if o.type=='MESH' and o.parent==root)
        mat=obj.data.materials[0];shader=mat.node_tree.nodes.get('Principled BSDF')
        if fault=='triangle_budget':
            manifest=json.loads((out/'meshes.json').read_text());next(iter(manifest['meshes'].values()))['triangles']=100001
            (out/'meshes.json').write_text(json.dumps(manifest))
        elif fault=='vertex':obj.data.vertices[0].co.x+=.01
        elif fault=='normal':
            obj.data.polygons[0].flip();obj.data.update()
        elif fault=='uv':obj.data.uv_layers.active.data[0].uv.x+=.25
        elif fault in ('material','glb_material'):shader.inputs['Metallic'].default_value=.8
        elif fault=='surface_output':
            output=next(n for n in mat.node_tree.nodes if n.type=='OUTPUT_MATERIAL')
            emission=mat.node_tree.nodes.new('ShaderNodeEmission')
            mat.node_tree.links.new(emission.outputs[0],output.inputs['Surface'])
        elif fault=='emission':shader.inputs['Emission Strength'].default_value=1
        elif fault=='hidden':obj.hide_render=True
        elif fault=='modifier':obj.modifiers.new('Adverse modifier','BEVEL')
        elif fault=='shape_key':obj.shape_key_add(name='Adverse shape key')
        elif fault in ('root_id','glb_identity'):root['gridline_id']='forged'
        elif fault=='root_host':root['gridline_host_id']='forged'
        elif fault=='root_pose':root.location.x+=1
        elif fault=='root_constraint':root.constraints.new('COPY_LOCATION')
        elif fault=='root_animation':root.keyframe_insert('location',frame=2)
        elif fault=='extra_object':bpy.context.collection.objects.link(bpy.data.objects.new('Unrequested object',None))
        elif fault=='extra_mesh':
            extra=obj.copy();extra.data=obj.data.copy();bpy.context.collection.objects.link(extra)
        elif fault=='missing_mesh':bpy.data.objects.remove(obj,do_unlink=True)
        elif fault=='units':bpy.context.scene.unit_settings.scale_length=.001
        elif fault=='texture_provenance':root['gridline_asset_provenance']='{}'
        elif fault=='texture_unpacked':
            image=next(n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE')
            image.filepath=str(out/'intentionally-missing.jpg');image.unpack(method='REMOVE')
        elif fault=='texture_mapping':next(n for n in mat.node_tree.nodes if n.type=='TEX_IMAGE').projection='BOX'
        elif fault=='normal_strength':next(n for n in mat.node_tree.nodes if n.type=='NORMAL_MAP').inputs['Strength'].default_value=.25
        elif fault=='glb_external_image':
            import struct
            doc,binary=read_glb(out/'components.glb')
            doc['images']=[{'uri':'file:///private/not-allowed.jpg','mimeType':'image/jpeg'}]
            data=json.dumps(doc).encode();data+=b' '*(-len(data)%4)
            payload=struct.pack('<II',len(data),0x4e4f534a)+data+struct.pack('<II',len(binary),0x004e4942)+binary
            (out/'components.glb').write_bytes(struct.pack('<4sII',b'glTF',2,len(payload)+12)+payload)
        else:raise AssertionError('unimplemented adverse fixture '+fault)
        if fault.startswith('glb_') and fault!='glb_external_image':
            bpy.ops.export_scene.gltf(filepath=str(out/'components.glb'),export_format='GLB',export_extras=True,export_cameras=False,export_lights=False)
        elif not fault.startswith('glb_'):
            bpy.ops.wm.save_as_mainfile(filepath=str(out/'components.blend'),check_existing=False)
        try:worker.verify(request,out)
        except ValueError as exc:results.append({'fault':fault,'state':'REJECTED','reason':str(exc)})
        else:raise AssertionError('critical false PASS: '+fault)
print('GRIDLINE_COMPONENT_ADVERSE_RESULTS='+json.dumps(results,sort_keys=True))
