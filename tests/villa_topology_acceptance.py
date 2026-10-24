"""Blender-only reproduction on a NEW output path; never saves the input file.

Blender --background --factory-startup --disable-autoexec --python-exit-code 1
 --python tests/villa_topology_acceptance.py -- build|verify ORIGINAL_DIR NEW_DIR
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/architectural-drawing-generation/scripts'))
from wall_topology import geometry_entries
from mesh_qa import check_surface
from glb_qa import check_glb


def read_object(obj,entry):
    if obj.get('gridline_id')!=entry['gridline_id'] or obj.get('gridline_role')!=entry['role']:
        raise ValueError(f'identity/role mismatch: {obj.name}')
    if obj.get('gridline_host')!=entry['host']:raise ValueError(f'host lost: {obj.name}')
    if len(obj.data.materials)!=1 or obj.data.materials[0].name!=entry['material'] or any(p.material_index for p in obj.data.polygons):
        raise ValueError(f'material mismatch: {obj.name}')
    if 'source_ids' in entry and obj.get('gridline_source_ids')!=json.dumps(entry['source_ids']):
        raise ValueError('source mapping lost')
    points=[list(obj.matrix_world@v.co) for v in obj.data.vertices]
    faces=[list(p.vertices) for p in obj.data.polygons]
    return check_surface(points,faces,entry.get('source_boxes',[entry]),1e-5,entry.get('void_boxes',()))


def add_mesh(entry,scene,prefix=''):
    mesh=bpy.data.meshes.new(prefix+entry['name'])
    mesh.from_pydata(entry['vertices'],[],entry['faces']);mesh.update()
    obj=bpy.data.objects.new(prefix+entry['name'],mesh);scene.collection.objects.link(obj)
    obj.data.materials.append(bpy.data.materials[entry['material']])
    for key in ('gridline_id','kind','host','role'):
        obj['gridline_'+('id' if key=='gridline_id' else key)]=entry[key]
    obj['gridline_source_ids']=json.dumps(entry['source_ids'])
    obj['gridline_source_units']='mm'
    obj['gridline_schema']='villa-topology.v1'
    return obj


def clipped_entries(source,group,top):
    boxes=[]
    for raw in source['boxes']:
        if raw['group']!=group or not (raw['kind'] in ('wall','door','glass') or raw.get('join_group')):continue
        b=copy.deepcopy(raw);low=b['center_m'][2]-b['dimensions_m'][2]/2;high=b['center_m'][2]+b['dimensions_m'][2]/2
        if low>=top:continue
        b['dimensions_m'][2]=min(high,top)-low;b['center_m'][2]=(min(high,top)+low)/2
        boxes.append(b)
    return [e for e in geometry_entries(dict(boxes=boxes)) if 'vertices' in e]


def build(original,out):
    out.mkdir(exist_ok=False)
    source=json.loads((original/'villa.scene.json').read_text())
    roof=next(b for b in source['boxes'] if b['name']=='Flat roof slab' and b['kind']=='roof')
    roof_top=roof['center_m'][2]+roof['dimensions_m'][2]/2
    decisions=[]
    for b in source['boxes']:
        if b['kind']=='parapet':
            top=b['center_m'][2]+b['dimensions_m'][2]/2
            if b['center_m'][2]-b['dimensions_m'][2]/2<roof_top:
                decisions.append(dict(id=b['gridline_id'],reason='trim buried base to roof top; preserve parapet top',before=copy.deepcopy(b)))
                b['center_m'][2]=(roof_top+top)/2;b['dimensions_m'][2]=top-roof_top
            b['join_group']='roof-parapet'
        if b['name'].startswith('Balcony') and b['kind']=='railing':b['join_group']='balcony-guard';b['role']='balcony_guard'
    (out/'source-decisions.json').write_text(json.dumps(decisions,indent=2)+'\n')
    entries=geometry_entries(source)
    bpy.ops.wm.open_mainfile(filepath=str(original/'Villa.blend'),load_ui=False)
    full=bpy.data.scenes['01 Exterior - complete villa'];bpy.context.window.scene=full
    original_meshes={o.name:o for o in full.objects if o.type=='MESH'}
    if set(original_meshes)!={b['name'] for b in source['boxes']}:raise ValueError('original source/native inventory mismatch')
    baseline={}
    for group in ('Ground','Upper','Roof','balcony-guard'):
        selected=[e for e in entries if 'source_boxes' in e and (e.get('group')==group or e.get('join_group')==group)]
        for e in selected:
            vertices=[];faces=[]
            for b in e['source_boxes']:
                o=original_meshes[b['name']];offset=len(vertices)
                vertices.extend([list(o.matrix_world@v.co) for v in o.data.vertices])
                faces.extend([[i+offset for i in p.vertices] for p in o.data.polygons])
            try:check_surface(vertices,faces,e['source_boxes'],1e-5,e.get('void_boxes',()))
            except ValueError as exc:baseline[e['name']]=dict(status='REJECTED',reason=str(exc),source_ids=e['source_ids'])
            else:raise AssertionError('original defective group falsely passed')
    (out/'baseline-rejections.json').write_text(json.dumps(baseline,indent=2)+'\n')
    for e in entries:
        if 'vertices' in e:
            for b in e['source_boxes']:bpy.data.objects.remove(original_meshes[b['name']],do_unlink=True)
            add_mesh(e,full)
        else:original_meshes[e['name']]['gridline_role']=e['role']
    for scene,group,top in [(bpy.data.scenes['02 Ground floor - ceiling removed'],'Ground',1.2),(bpy.data.scenes['03 First floor - roof removed'],'Upper',4.5)]:
        replacing={b['gridline_id'] for b in source['boxes'] if b['group']==group and (b['kind']=='wall' or b.get('join_group'))}
        for o in list(scene.objects):
            if o.type=='MESH' and o.get('gridline_id') in replacing:bpy.data.objects.remove(o,do_unlink=True)
        for e in clipped_entries(source,group,top):add_mesh(e,scene,'Cutaway '+group+' ')
    bpy.context.window.scene=full
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'Villa.blend'),check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(out/'Villa.glb'),export_format='GLB',export_extras=True,use_active_scene=True,export_cameras=False,export_lights=False)
    (out/'villa.scene.json').write_text(json.dumps(source,indent=2)+'\n')
    (out/'source-provenance.json').write_text(json.dumps({n:hashlib.sha256((original/n).read_bytes()).hexdigest() for n in ('Villa.blend','Villa.glb','villa.scene.json','villa.building.json','prepare.py','build_blender.py')},indent=2)+'\n')
    print('REPAIRED',len(entries),'meshes; baseline rejected',len(baseline),'groups')


def verify(original,out):
    raw_glb=check_glb(out/'Villa.glb')
    source=json.loads((out/'villa.scene.json').read_text())
    entries=geometry_entries(source);expected={e['name']:e for e in entries};report={}
    for fmt in ('blend','glb'):
        if fmt=='blend':bpy.ops.wm.open_mainfile(filepath=str(out/'Villa.blend'),load_ui=False)
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=str(out/'Villa.glb'))
        if fmt=='blend':
            for name,group,top in [('02 Ground floor - ceiling removed','Ground',1.2),('03 First floor - roof removed','Upper',4.5)]:
                cut=bpy.data.scenes[name]
                for e in clipped_entries(source,group,top):
                    o=cut.objects.get('Cutaway '+group+' '+e['name'])
                    if o is None:raise ValueError('missing repaired cutaway')
                    read_object(o,e)
            full=bpy.data.scenes['01 Exterior - complete villa']
        else:full=bpy.context.scene
        objs={o.name:o for o in full.objects if o.type=='MESH'}
        if set(objs)!=set(expected):raise ValueError('extra/orphan/missing mesh inventory')
        report[fmt]={n:read_object(o,expected[n]) for n,o in objs.items()}
        roof=next(o for o in objs.values() if o.get('gridline_role')=='roof_slab')
        parapet=next(o for o in objs.values() if o.get('gridline_role')=='parapet')
        roof_top=max((roof.matrix_world@v.co).z for v in roof.data.vertices)
        parapet_bottom=min((parapet.matrix_world@v.co).z for v in parapet.data.vertices)
        if parapet_bottom<roof_top-1e-5:raise ValueError('roof/parapet buried-base overlap')
    (out/'topology-readback.json').write_text(json.dumps(dict(status='PASS',raw_glb=raw_glb,scope='declared box union boundaries and source roles; construction design unverified',readback=report),indent=2)+'\n')
    hashes={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ('Villa.blend','Villa.glb','villa.scene.json','topology-readback.json')}
    (out/'sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print('VILLA_TOPOLOGY_READBACK_PASS',len(expected),json.dumps(hashes))


if __name__=='__main__':
    mode,src,dst=sys.argv[sys.argv.index('--')+1:]
    if mode not in ('build','verify'):raise ValueError('unsupported mode')
    globals()[mode](Path(src).resolve(strict=True),Path(dst).absolute())
