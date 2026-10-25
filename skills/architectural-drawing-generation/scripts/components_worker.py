# SPDX-FileCopyrightText: 2026 Nicolas Savvides
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fixed Blender API worker. Original code; external ARCHIMESH is never bundled."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from component_spec import validate, digest
from glb_qa import check_glb
from component_mesh import compare_triangles
from blender_native import compile_scene
from wall_topology import geometry_entries
from mesh_qa import check_surface


def collection_item(operator, field, values):
    properties = operator.get_rna_type().properties[field].fixed_type.properties
    result = {}
    for prop in properties:
        if prop.is_readonly:
            continue
        if getattr(prop, 'is_array', False):
            result[prop.identifier] = tuple(prop.default_array)
        else:
            result[prop.identifier] = prop.default
    result.update(values)
    return [result]


def generate(item):
    p = item['parameters']; kind = item['kind']
    if kind in ('door', 'window', 'window_panel', 'venetian'):
        names = {'door': ('archimesh_door', 'DoorObjectGenerator'),
                 'window': ('archimesh_window', 'WindowObjectGenerator'),
                 'window_panel': ('archimesh_winpanel', 'WindowPanelGenerator'),
                 'venetian': ('archimesh_venetian', 'VenetianObjectGenerator')}
        operator, collection = names[kind]
        if getattr(bpy.ops.mesh, operator)() != {'FINISHED'}:
            raise ValueError(f'{kind} operator cancelled')
        main = bpy.context.object
        values = getattr(main, collection)[0]
        if hasattr(values, 'crt_mat'):
            values.crt_mat = False
        if kind == 'door':
            settings = dict(frame_width=p['width'], frame_height=p['height'], frame_thick=p['depth'],
                            frame_size=p['frame_size'], handle='0', model='1', openside='1', r=0)
        elif kind == 'window':
            settings = dict(width=p['width'], height=p['height'], depth=p['depth'], external=False,
                            sill=False, blind=False, handle=False, frame_L=p['frame_size'], r=0)
        elif kind == 'window_panel':
            settings = dict(gen=1, yuk=1, gnx0=p['pane_width_cm'], gny0=p['pane_height_cm'], mr=False)
        else:
            settings = dict(width=p['width'], height=p['height'], depth=p['depth'], angle=p['angle_deg'])
        for key, value in settings.items():
            setattr(values, key, value)
        return main
    if kind == 'cabinet':
        result = bpy.ops.mesh.archimesh_kitchen(cabinet_num=1, cabinets=collection_item(bpy.ops.mesh.archimesh_kitchen,'cabinets',{'name':'unit-1','sX':p['width'], 'dType':'1', 'sNum':0, 'hand':False}),
                    height=p['height'], depth=p['depth'], thickness=p['thickness'], baseboard=False, countertop=False, fitZ=False, crt_mat=False)
    elif kind == 'shelves':
        result = bpy.ops.mesh.archimesh_shelves(shelves_num=1, shelves=collection_item(bpy.ops.mesh.archimesh_shelves,'shelves',{'name':'unit-1','sX':p['width'], 'sNum':p['shelf_count']}),
                    height=p['height'], depth=p['depth'], thickness=p['side_thickness'], sthickness=p['shelf_thickness'], fitZ=False, crt_mat=False)
    elif kind == 'column':
        result = bpy.ops.mesh.archimesh_column(model='1', rad_top=p['radius'], rad_mid=p['radius'], rad_bottom=p['radius'],
                    col_height=p['height'], box_base=False, box_top=False, cir_base=False, cir_top=False, arc_top=False, crt_array=False, crt_mat=False)
    elif kind == 'stairs':
        result = bpy.ops.mesh.archimesh_stairs(model='1', step_num=p['step_count'], max_width=p['width'],
                    depth=p['tread_depth'], height=p['riser_height']-p['tread_thickness'], thickness=p['tread_thickness'], front_gap=0, side_gap=0, curve=False, sizev=False, crt_mat=False)
    elif kind == 'roof':
        result = bpy.ops.mesh.archimesh_roof(roof_width=p['tiles_x'], roof_height=p['tiles_y'], roof_scale=p['tile_scale'],
                    roof_angle=p['angle_deg'], roof_thick=p['thickness'], model='1', crt_mat=False)
    elif kind == 'books':
        result = bpy.ops.mesh.archimesh_books(width=p['width'], height=p['height'], depth=p['depth'], num=p['count'],
                    rX=0, rY=0, rZ=0, rot=0, rC=0, crt_mat=False)
    elif kind == 'lamp':
        result = bpy.ops.mesh.archimesh_light(base_height=p['base_height'], top_height=p['shade_height'],
                    base_segments=16, base_rings=4, top_segments=16, subdivide=False, crt_mat=False)
    elif kind == 'roller':
        result = bpy.ops.mesh.archimesh_roller(width=p['width'], height=p['height'], crt_mat=False)
    elif kind == 'curtain':
        result = bpy.ops.mesh.archimesh_japan(width=p['width'], height=p['height'], num=p['panels'], palnum=1, crt_mat=False)
    else:
        raise ValueError('unsupported recipe')
    if result != {'FINISHED'}:
        raise ValueError(f'{kind} operator cancelled')
    main = bpy.context.object
    if kind == 'column':
        for modifier in list(main.modifiers):
            if modifier.type == 'SUBSURF':
                main.modifiers.remove(modifier)
    return main


def material(item, out):
    data = item['material']
    name = 'Gridline_' + data['id']
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*data['base_color'], 1)
    shader.inputs['Roughness'].default_value = data['roughness']
    shader.inputs['Metallic'].default_value = data['metallic']
    mat.diffuse_color = (*data['base_color'], 1)
    if 'asset_plan_sha256' in data:
        for channel, socket in (('base_color','Base Color'),('roughness','Roughness'),('normal','Normal')):
            image=bpy.data.images.load(str(out/'assets'/data['asset_plan_sha256']/(channel+'.jpg')),check_existing=True)
            if max(image.size)>2048 or min(image.size)<=0: raise ValueError('image pixel budget exceeded')
            image.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
            image.pack()
            node=mat.node_tree.nodes.new('ShaderNodeTexImage');node.image=image
            if channel=='normal':
                normal=mat.node_tree.nodes.new('ShaderNodeNormalMap')
                mat.node_tree.links.new(node.outputs['Color'],normal.inputs['Color'])
                mat.node_tree.links.new(normal.outputs['Normal'],shader.inputs['Normal'])
            else:mat.node_tree.links.new(node.outputs['Color'],shader.inputs[socket])
    return mat


def surface_shader(mat):
    tree=mat.node_tree
    if mat.animation_data or tree is None or tree.animation_data:raise ValueError('animated/missing PBR material')
    shader=tree.nodes.get('Principled BSDF')
    outputs=[n for n in tree.nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output]
    if shader is None or len(outputs)!=1:raise ValueError('missing/ambiguous PBR surface')
    surface=outputs[0].inputs['Surface']
    if len(surface.links)!=1 or surface.links[0].from_node!=shader or surface.links[0].from_socket.name!='BSDF':raise ValueError('PBR surface output changed')
    if outputs[0].inputs['Volume'].is_linked or outputs[0].inputs['Displacement'].is_linked:raise ValueError('unsupported volume/displacement')
    allowed={'Base Color','Roughness','Metallic','Normal'}
    if any(socket.is_linked for socket in shader.inputs if socket.name not in allowed):raise ValueError('unsupported PBR shader connection')
    for name,value in (('Alpha',1),('Emission Strength',0),('Transmission Weight',0),('Coat Weight',0),('Subsurface Weight',0),('Specular IOR Level',.5),('IOR',1.5)):
        if abs(shader.inputs[name].default_value-value)>1e-6:raise ValueError('unsupported PBR shader parameter: '+name)
    return shader


def texture_signature(mat):
    shader=surface_shader(mat)
    def image_upstream(socket, depth=0):
        if depth>4 or not socket.is_linked or len(socket.links)!=1:
            raise ValueError('missing/ambiguous PBR texture connection')
        node=socket.links[0].from_node
        if node.type=='TEX_IMAGE':
            if node.inputs['Vector'].is_linked or node.projection!='FLAT' or node.extension!='REPEAT':raise ValueError('unsupported texture coordinate/projection mapping')
            if node.image is None or node.image.packed_file is None:
                raise ValueError('missing/unpacked PBR image')
            if socket.links[0].from_socket.name!='Color':raise ValueError('wrong texture image channel')
            return node.image
        if node.type=='NORMAL_MAP':
            if socket.links[0].from_socket.name!='Normal':raise ValueError('wrong normal-map output')
            if node.space!='TANGENT' or abs(node.inputs['Strength'].default_value-1)>1e-7:raise ValueError('normal-map space/strength changed')
            return image_upstream(node.inputs['Color'],depth+1)
        if node.type in ('SEPRGB','SEPARATE_COLOR'):return image_upstream(node.inputs[0],depth+1)
        raise ValueError('unsupported PBR texture graph')
    if shader.inputs['Alpha'].is_linked or abs(shader.inputs['Alpha'].default_value-1)>1e-7:raise ValueError('textured material alpha changed')
    result={}
    for channel,socket in (('base_color','Base Color'),('roughness','Roughness'),('normal','Normal')):
        connection=shader.inputs[socket]
        if channel=='roughness' and connection.is_linked and connection.links[0].from_node.type in ('SEPRGB','SEPARATE_COLOR') and connection.links[0].from_socket.name not in ('G','Green'):
            raise ValueError('wrong roughness packing channel')
        image=image_upstream(connection)
        if max(image.size)>2048:raise ValueError('PBR image pixel budget exceeded')
        pixels=image.pixels[:]
        values=(pixels[i] for i in range(1,len(pixels),4)) if channel=='roughness' else (pixels[i] for i in range(len(pixels)) if i%4!=3)
        result[channel]={'size':list(image.size),'pixel_sha256':hashlib.sha256(bytes(max(0,min(255,round(v*255))) for v in values)).hexdigest()}
    metal=shader.inputs['Metallic']
    factor=1
    if metal.is_linked and metal.links[0].from_node.type=='MATH':
        node=metal.links[0].from_node
        if node.operation!='MULTIPLY':raise ValueError('unsupported metallic graph')
        linked=[socket for socket in node.inputs[:2] if socket.is_linked]
        constants=[socket.default_value for socket in node.inputs[:2] if not socket.is_linked]
        if len(linked)!=1 or len(constants)!=1 or not 0<=constants[0]<=1:raise ValueError('invalid metallic factor')
        factor=constants[0];metal=linked[0]
    if metal.is_linked:
        connection=metal.links[0]
        if connection.from_node.type not in ('SEPRGB','SEPARATE_COLOR') or connection.from_socket.name not in ('B','Blue'):
            raise ValueError('wrong metallic packing channel')
        image=image_upstream(metal)
        value=max(image.pixels[2::4])*factor
    else:value=metal.default_value*factor
    if not math.isfinite(value) or abs(value)>1e-5:raise ValueError('nonmetal material has effective metallic values')
    result['metallic']=0
    return result


def signatures(obj):
    if obj.type != 'MESH' or obj.hide_render or obj.hide_viewport or obj.hide_get() or obj.modifiers or obj.constraints or obj.data.shape_keys:
        raise ValueError(f'unsupported mesh/visibility/modifier state: {obj.name}')
    obj.data.calc_loop_triangles()
    if len(obj.data.loop_triangles)>100000:raise ValueError('component triangle budget exceeded')
    vertices = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
    if not vertices or len(vertices) > 300000 or any(not math.isfinite(v) for p in vertices for v in p):
        raise ValueError('invalid or oversized mesh')
    triangles = []
    normal_matrix = obj.matrix_world.to_3x3().inverted().transposed()
    uv = obj.data.uv_layers.active
    if uv is None:
        raise ValueError('missing UV coordinates')
    for tri in obj.data.loop_triangles:
        points = [Vector(vertices[i]) for i in tri.vertices]
        if (points[1]-points[0]).cross(points[2]-points[0]).length < 1e-10:
            raise ValueError(f'degenerate triangle: {obj.name}')
        record = []
        for vertex, loop in zip(tri.vertices, tri.loops):
            tex = uv.data[loop].uv
            normal = normal_matrix @ obj.data.corner_normals[loop].vector
            normal.normalize()
            record.append(tuple(float(v) for v in (*vertices[vertex], *tex, *normal)))
        # Cyclic rotations preserve winding, unlike sorting all corners.
        triangles.append(min(tuple(record[i:]+record[:i]) for i in range(3)))
    if len(set(triangles)) != len(triangles):
        raise ValueError('duplicate mesh triangles')
    slots = [m.name if m else None for m in obj.data.materials]
    if len(slots) != 1 or None in slots or any(p.material_index != 0 for p in obj.data.polygons):
        raise ValueError('missing/ambiguous material slots')
    shader=surface_shader(obj.data.materials[0])
    pbr=list(shader.inputs['Base Color'].default_value)+[shader.inputs[k].default_value for k in ('Roughness','Metallic')]
    return {'triangle_sha256':digest(sorted(triangles)), 'triangles':len(triangles), 'pbr':None if any(shader.inputs[k].is_linked for k in ('Base Color','Roughness','Metallic','Normal')) else [round(v,5) for v in pbr],
            'bounds_m':[[min(v[i] for v in vertices) for i in range(3)], [max(v[i] for v in vertices) for i in range(3)]],
            'reference_triangles':triangles, 'materials':slots, 'parent':obj.parent.name if obj.parent else None,
            'id':obj.get('gridline_id'), 'source_element_id':obj.get('gridline_source_element_id'),
            'host_id':obj.get('gridline_host_id'), 'role':obj.get('gridline_role')}


def freeze(item, main, original, out):
    """Freeze evaluated upstream assemblies; controls never become building geometry."""
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    payload, excluded = [], []
    removed_degenerate = {}
    anchor = None
    anchor_name = main.name if main else None
    if main and main.type == 'MESH':
        anchor = [list(v.co) for v in main.data.vertices]
    for obj in sorted(original, key=lambda o:o.name):
        if obj.get('archimesh.ctrl_hole') or obj.get('archimesh.ctrl_base'):
            excluded.append(obj.name); continue
        if obj.type not in ('MESH', 'CURVE'):
            continue
        if obj.hide_render or obj.hide_viewport:
            raise ValueError(f'upstream contains unexplained hidden geometry: {obj.name}')
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
        if not mesh.polygons:
            bpy.data.meshes.remove(mesh); continue
        mesh.transform(obj.matrix_world)
        mesh.calc_loop_triangles()
        triangles = []
        removed = 0
        for triangle in mesh.loop_triangles:
            a,b,c = (mesh.vertices[i].co for i in triangle.vertices)
            if (b-a).cross(c-a).length <= 1e-10:
                removed += 1
            else:
                triangles.append(tuple(triangle.vertices))
        # Upstream emits zero-area faces in some defaults; no nonzero surface is removed.
        frozen = bpy.data.meshes.new(obj.name + '_triangles')
        frozen.from_pydata([list(v.co) for v in mesh.vertices], [], triangles)
        frozen.update()
        bpy.data.meshes.remove(mesh)
        if removed:
            removed_degenerate[obj.name] = removed
        payload.append((obj.name, obj.parent.name if obj.parent else '', frozen))
    if not payload:
        raise ValueError('generator produced no visible mesh')
    # Generator callbacks are no longer run after this point.
    for obj in original:
        bpy.data.objects.remove(obj, do_unlink=True)
    root = bpy.data.objects.new(item['id'], None)
    bpy.context.scene.collection.objects.link(root)
    root['gridline_role'] = 'component'
    root['gridline_request_sha256'] = digest(item)
    root['gridline_id'] = item['id']
    root['gridline_source_element_id'] = item['source_element_id']
    root['gridline_host_id'] = item['host_id']
    root['gridline_kind'] = item['kind']
    asset_provenance=None
    if 'asset_plan_sha256' in item['material']:
        ident=item['material']['asset_plan_sha256']
        manifest=json.loads((out/'assets'/ident/'asset.json').read_text())
        asset_provenance={'plan':manifest['plan'],'files':manifest['files'],'evidence_scope':manifest.get('evidence_scope','USER_APPROVED_PLAN_AND_HASH_VERIFIED_BYTES')}
        root['gridline_asset_plan_sha256']=ident
        root['gridline_asset_provenance']=json.dumps(asset_provenance,sort_keys=True)
    root.location = item['position_m']
    root.rotation_euler.z = math.radians(item['rotation_deg'])
    mat = material(item, out)
    members = []
    for index, (old_name, old_parent, mesh) in enumerate(payload):
        obj = bpy.data.objects.new(f"{item['id']}__{index:03}", mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = root
        for key in ('id', 'source_element_id', 'host_id'):
            obj['gridline_'+key] = item[key]
        obj['gridline_role'] = 'component_mesh'
        obj['gridline_anchor'] = old_name == anchor_name
        obj['gridline_upstream_name'] = old_name
        obj['gridline_upstream_parent'] = old_parent
        mesh.materials.clear(); mesh.materials.append(mat)
        for face in mesh.polygons:
            face.material_index = 0
        # Explicit metre-scale planar UV projection, independent of upstream renderer shaders.
        uv = mesh.uv_layers.new(name='Gridline_Planar') if not mesh.uv_layers else mesh.uv_layers.active
        for face in mesh.polygons:
            axis = max(range(3), key=lambda i:abs(face.normal[i]))
            plane = [i for i in range(3) if i != axis]
            for loop in face.loop_indices:
                co = mesh.vertices[mesh.loops[loop].vertex_index].co
                tile=item['material'].get('uv_tile_size_m',[1,1])
                uv.data[loop].uv = (co[plane[0]]/tile[0], co[plane[1]]/tile[1])
        members.append(obj)
    bpy.context.view_layer.update()
    anchor_dims = None if not anchor else [max(p[i] for p in anchor)-min(p[i] for p in anchor) for i in range(3)]
    return root, members, {'asset_provenance':asset_provenance, 'excluded_controls':excluded, 'removed_zero_area_triangles':removed_degenerate, 'recipe_surface':'12-sided faceted, size-changing subdivision disabled' if item['kind']=='column' else 'evaluated triangles', 'upstream_anchor_dimensions_m':anchor_dims}


def building_entries(spec):
    if 'building' not in spec:return []
    substituted={item['source_element_id'] for item in spec['components'] if item['host_id']}
    return [e for e in geometry_entries(compile_scene(spec['building'])) if e['kind']=='wall' or e['gridline_id'] not in substituted]


def shell_geometry(entry):
    if 'vertices' in entry:return entry['vertices'],entry['faces']
    center=entry['center_m'];dims=entry['dimensions_m'];angle=entry['rotation_z']
    c,s=math.cos(angle),math.sin(angle)
    vertices=[(center[0]+c*x-s*y,center[1]+s*x+c*y,center[2]+z)
              for x,y,z in ((-dims[0]/2,-dims[1]/2,-dims[2]/2),(dims[0]/2,-dims[1]/2,-dims[2]/2),
                            (dims[0]/2,dims[1]/2,-dims[2]/2),(-dims[0]/2,dims[1]/2,-dims[2]/2),
                            (-dims[0]/2,-dims[1]/2,dims[2]/2),(dims[0]/2,-dims[1]/2,dims[2]/2),
                            (dims[0]/2,dims[1]/2,dims[2]/2),(-dims[0]/2,dims[1]/2,dims[2]/2))]
    return vertices,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]


def make_shell(spec, out):
    entries=building_entries(spec)
    if not entries:return []
    root=bpy.data.objects.new('Gridline_Building',None)
    bpy.context.scene.collection.objects.link(root)
    root['gridline_role']='building'
    root['gridline_building_sha256']=digest(spec['building'])
    objects=[]
    for entry in entries:
        vertices,faces=shell_geometry(entry)
        check_surface(vertices,faces,entry.get('source_boxes',[entry]),1e-5,entry.get('void_boxes',()))
        mesh=bpy.data.meshes.new('building_'+entry['name'])
        mesh.from_pydata(vertices,[],faces);mesh.update()
        obj=bpy.data.objects.new('building__'+entry['name'],mesh)
        bpy.context.scene.collection.objects.link(obj);obj.parent=root
        for key,value in {'id':entry['gridline_id'],'source_element_id':entry['gridline_id'],'host_id':entry['host'],'role':'building_mesh',
                          'source_ids':json.dumps(entry.get('source_ids',[entry['gridline_id']])),'source_role':entry['role']}.items():obj['gridline_'+key]=value
        style={'id':'shell_'+entry['kind'],'base_color':{'wall':[.69,.73,.77],'door':[.34,.41,.47],'glass':[.26,.56,.69]}[entry['kind']],
               'roughness':.66,'metallic':0}
        mesh.materials.append(material({'material':style},out))
        uv=mesh.uv_layers.new(name='Gridline_Planar')
        for face in mesh.polygons:
            axis=max(range(3),key=lambda i:abs(face.normal[i]));plane=[i for i in range(3) if i!=axis]
            for loop in face.loop_indices:
                co=mesh.vertices[mesh.loops[loop].vertex_index].co;uv.data[loop].uv=(co[plane[0]],co[plane[1]])
        objects.append(obj)
    return objects


def build(spec, addon_path, out):
    module_spec = importlib.util.spec_from_file_location('gridline_external_archimesh', addon_path/'__init__.py', submodule_search_locations=[str(addon_path)])
    addon = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = addon
    module_spec.loader.exec_module(addon)
    addon.register()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.context.scene.unit_settings.scale_length = 1
    manifest = {'schema':'gridline-component-meshes.v1', 'request_sha256':digest(spec), 'components':{}, 'meshes':{}, 'textures':{}}
    for obj in make_shell(spec,out):manifest['meshes'][obj.name]=signatures(obj)
    for item in spec['components']:
        random.seed(hashlib.sha256(item['id'].encode()).hexdigest())
        before = set(bpy.data.objects)
        bpy.context.scene.cursor.location = (0, 0, 0)
        main = generate(item)
        original = set(bpy.data.objects)-before
        root, members, info = freeze(item, main, original, out)
        manifest['components'][item['id']] = {**info, 'members':[m.name for m in members], 'kind':item['kind']}
        for obj in members:
            manifest['meshes'][obj.name] = signatures(obj)
        if 'asset_plan_sha256' in item['material']:
            manifest['textures'][item['material']['id']] = texture_signature(members[0].data.materials[0])
    if sum(record['triangles'] for record in manifest['meshes'].values())>100000:raise ValueError('scene triangle budget exceeded')
    bpy.context.scene['gridline_request_sha256'] = digest(spec)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'components.blend'), check_existing=False)
    bpy.ops.export_scene.gltf(filepath=str(out/'components.glb'), export_format='GLB', export_extras=True,
                             export_cameras=False, export_lights=False, export_apply=False)
    (out/'meshes.json').write_text(json.dumps(manifest, indent=2)+'\n')


def verify(spec, out):
    expected = json.loads((out/'meshes.json').read_text())
    if sum(record['triangles'] for record in expected['meshes'].values())>100000:raise ValueError('scene triangle budget exceeded')
    if expected['request_sha256'] != digest(spec):
        raise ValueError('request/mesh source binding changed')
    raw = check_glb(out/'components.glb')
    reports = {}
    for mode in ('blend', 'glb'):
        if mode == 'blend':
            bpy.ops.wm.open_mainfile(filepath=str(out/'components.blend'))
            units = bpy.context.scene.unit_settings
            if units.system != 'METRIC' or units.scale_length != 1:
                raise ValueError('native unit scale changed')
        else:
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.import_scene.gltf(filepath=str(out/'components.glb'))
        bpy.context.view_layer.update()
        allowed_names=set(expected['meshes'])|{c['id'] for c in spec['components']}
        if spec.get('building'):allowed_names.add('Gridline_Building')
        if {o.name for o in bpy.data.objects}!=allowed_names:raise ValueError('unexpected/missing scene objects')
        for obj in bpy.data.objects:
            if obj.type not in ('MESH','EMPTY') or obj.hide_render or obj.hide_viewport or obj.hide_get() or obj.constraints or obj.modifiers or obj.animation_data:
                raise ValueError('unsupported object visibility/modifier/animation: '+obj.name)
            if obj.data is not None and obj.data.animation_data:raise ValueError('animated geometry')
        meshes = {obj.name:obj for obj in bpy.data.objects if obj.type == 'MESH'}
        if set(meshes) != set(expected['meshes']):
            raise ValueError(f'{mode}: missing/duplicate/extra mesh inventory')
        for name, obj in meshes.items():
            got = signatures(obj); want = expected['meshes'][name]
            try:
                compare_triangles(want['reference_triangles'],got['reference_triangles'])
            except ValueError as exc:
                (out/'mismatch.json').write_text(json.dumps({'name':name,'mode':mode,'expected':want['reference_triangles'],'actual':got['reference_triangles']}))
                raise ValueError(f'{mode}: {name}: {exc}') from exc
            for key in ('triangles','materials','pbr','parent','id','source_element_id','host_id','role'):
                if got[key] != want[key]:
                    raise ValueError(f'{mode}: changed {name} {key}')
        shell_entries=building_entries(spec)
        expected_shell={'building__'+e['name']:e for e in shell_entries}
        actual_shell={name:obj for name,obj in meshes.items() if obj.get('gridline_role')=='building_mesh'}
        if set(actual_shell)!=set(expected_shell):raise ValueError('building shell inventory changed')
        for name,obj in actual_shell.items():
            entry=expected_shell[name]
            check_surface([list(obj.matrix_world @ v.co) for v in obj.data.vertices], [list(face.vertices) for face in obj.data.polygons],
                          entry.get('source_boxes',[entry]),1e-5,entry.get('void_boxes',()))
            if obj.get('gridline_source_ids')!=json.dumps(entry.get('source_ids',[entry['gridline_id']])) or obj.get('gridline_source_role')!=entry['role']:
                raise ValueError('building source role/provenance changed')
        if shell_entries:
            building=bpy.data.objects.get('Gridline_Building')
            if building is None or building.get('gridline_building_sha256')!=digest(spec['building']):raise ValueError('building source binding lost')
        roots = {o.name:o for o in bpy.data.objects if o.get('gridline_role') == 'component'}
        if set(roots) != {c['id'] for c in spec['components']}:
            raise ValueError('missing/duplicate component roots')
        for item in spec['components']:
            root = roots[item['id']]
            if (root.get('gridline_id')!=item['id'] or root.get('gridline_kind')!=item['kind'] or root.get('gridline_request_sha256') != digest(item) or root.get('gridline_source_element_id') != item['source_element_id']
                    or root.get('gridline_host_id') != item['host_id']):
                raise ValueError('component identity/provenance lost')
            if 'asset_plan_sha256' in item['material']:
                wanted_provenance=expected['components'][item['id']]['asset_provenance']
                if root.get('gridline_asset_plan_sha256')!=item['material']['asset_plan_sha256'] or root.get('gridline_asset_provenance')!=json.dumps(wanted_provenance,sort_keys=True):
                    raise ValueError('asset provider/license/source/hash provenance lost')
            expected_transform = Matrix.Translation(Vector(item['position_m'])) @ Matrix.Rotation(math.radians(item['rotation_deg']),4,'Z')
            if any(abs(root.matrix_world[i][j]-expected_transform[i][j]) > 1e-5 for i in range(4) for j in range(4)):
                raise ValueError('component placement/scale changed')
            if item['kind'] in ('door','window','cabinet'):
                anchors = [obj for obj in meshes.values() if obj.parent == root and obj.get('gridline_anchor')]
                if len(anchors) != 1:
                    raise ValueError('missing/duplicate dimension anchor')
                anchor = anchors[0]
                points = [root.matrix_world.inverted() @ anchor.matrix_world @ v.co for v in anchor.data.vertices]
                measured = [max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
                wanted = [item['parameters'][key] for key in ('width','depth','height')]
                if any(abs(a-b)>1e-5 for a,b in zip(measured,wanted)):
                    raise ValueError('component anchor dimensions do not match request')
            if item['kind'] in ('column','stairs'):
                points = [root.matrix_world.inverted() @ obj.matrix_world @ v.co for obj in meshes.values() if obj.parent == root for v in obj.data.vertices]
                dims = [max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)]
                p = item['parameters']
                if item['kind']=='stairs':
                    target = [p['width'],p['step_count']*p['tread_depth'],p['step_count']*p['riser_height']]
                    if any(abs(a-b)>1e-5 for a,b in zip(dims,target)):
                        raise ValueError('stair width/run/rise changed')
                elif abs(dims[2]-p['height'])>1e-5 or abs(max(math.hypot(v[0],v[1]) for v in points)-p['radius'])>1e-5:
                    raise ValueError('column height/radius changed')
            for obj in (o for o in meshes.values() if o.parent == root):
                mat = obj.data.materials[0]
                shader = mat.node_tree.nodes.get('Principled BSDF')
                if shader is None:
                    raise ValueError('PBR shader missing')
                channels = list(shader.inputs['Base Color'].default_value[:3]) + [shader.inputs[k].default_value for k in ('Roughness','Metallic')]
                target = item['material']['base_color'] + [item['material']['roughness'],item['material']['metallic']]
                if 'asset_plan_sha256' not in item['material'] and any(abs(a-b)>1e-5 for a,b in zip(channels,target)):
                    raise ValueError('PBR material values changed')
                if 'asset_plan_sha256' in item['material'] and texture_signature(mat)!=expected['textures'][item['material']['id']]:
                    raise ValueError('packed PBR texture pixels/links changed')
        reports[mode] = {'state':'PASS', 'meshes':len(meshes), 'components':len(roots)}
    (out/'verification.json').write_text(json.dumps({'state':'PASS', 'request_sha256':digest(spec), 'raw_glb':raw, 'formats':reports,
        'scope':'Frozen visual components; no regulatory, manufacturing or live-host approval'},indent=2)+'\n')


def main():
    args = sys.argv[sys.argv.index('--')+1:]
    if len(args) != 4 or args[0] not in ('build', 'verify'):
        raise SystemExit('expected build|verify request.json trusted-addon-directory new-output-directory')
    mode, source, addon, out = args
    spec = validate(json.loads(Path(source).read_text()))
    if mode == 'build': build(spec, Path(addon), Path(out))
    else: verify(spec, Path(out))


if __name__ == '__main__':
    main()
