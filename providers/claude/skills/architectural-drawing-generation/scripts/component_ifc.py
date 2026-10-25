#!/usr/bin/env python3
"""Optional local IFC4 export/readback from verified component/source bundles."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parent))
from archimesh_components import load, OUTPUTS
from archimesh_doctor import read_file
from component_spec import digest, encode, validate
from component_mesh import compare_triangles
from blender_native import compile_scene, publish
from wall_topology import geometry_entries
from mesh_qa import check_surface

CLASSES={'door':'IfcDoor','window':'IfcWindow','window_panel':'IfcWindow','cabinet':'IfcFurniture','shelves':'IfcFurniture',
         'column':'IfcColumn','stairs':'IfcStairFlight','roof':'IfcCovering','books':'IfcBuildingElementProxy',
         'lamp':'IfcLightFixture','roller':'IfcShadingDevice','venetian':'IfcShadingDevice','curtain':'IfcCovering'}


def stable_uuid(project, key):
    return uuid.uuid5(uuid.NAMESPACE_URL,'https://gridline.local/ifc/'+project+'/'+key).hex


def engine():
    try:
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.geom
        import ifcopenshell.validate
        import ifcopenshell.util.element
        import ifcopenshell.util.placement
    except ImportError as exc:
        raise ValueError('IfcOpenShell is not installed; no IFC acceptance possible') from exc
    return ifcopenshell


def bundle(folder, expected_receipt, expected_owner_key):
    folder=Path(folder).resolve(strict=True)
    receipt_bytes=read_file(folder/'receipt.json')
    if hashlib.sha256(receipt_bytes).hexdigest()!=expected_receipt:raise ValueError('bundle receipt differs from trusted pin')
    receipt=json.loads(receipt_bytes)
    if receipt.get('schema')!='gridline-component-receipt.v1' or receipt.get('state')!='VERIFIED_VISUAL_COMPONENTS' or set(receipt.get('files',{}))!=set(OUTPUTS):
        raise ValueError('not a complete component bundle')
    consumed={}
    for name,expected in receipt['files'].items():
        consumed[name]=read_file(folder/name,max_bytes=64*1024*1024)
        if hashlib.sha256(consumed[name]).hexdigest()!=expected:raise ValueError('component bundle changed')
    spec=validate(json.loads(consumed['request.json']))
    if receipt.get('canonical_state_revision')!=digest(spec) or receipt.get('canonical_owner_key_sha256')!=expected_owner_key or not isinstance(expected_owner_key,str) or len(expected_owner_key)!=64:
        raise ValueError('IFC requires a signed canonical-source bundle and separately trusted owner key fingerprint')
    meshes=json.loads(consumed['meshes.json'])
    if digest(spec)!=receipt['request_sha256'] or meshes['request_sha256']!=digest(spec):raise ValueError('source binding mismatch')
    verification=json.loads(consumed['verification.json'])
    if verification.get('state')!='PASS' or verification.get('request_sha256')!=digest(spec):raise ValueError('bundle has no passing native/GLB verification')
    return spec,meshes,receipt


def requirements(path, project):
    value=json.loads(read_file(path))
    if (not isinstance(value,dict) or set(value)!= {'schema','project_id','required_properties','allow_unknown_materials'}
            or value['schema']!='gridline-ifc-requirements.v1' or value['project_id']!=project
            or type(value['allow_unknown_materials'])!=bool or not isinstance(value['required_properties'],list)
            or not value['required_properties'] or any(p not in ('SourceElementId','RequestSHA256','Kind','MaterialId') for p in value['required_properties'])):
        raise ValueError('explicit matching project IFC requirements required')
    return value


def raw_triangles(records):
    return [tri for record in records for tri in record['reference_triangles']]


def export_model(api, spec, meshes):
    import numpy as np
    from ifcopenshell.api.root import create_entity
    from ifcopenshell.api.context import add_context
    from ifcopenshell.api.aggregate import assign_object
    from ifcopenshell.api.spatial import assign_container
    from ifcopenshell.api.geometry import add_mesh_representation, assign_representation, edit_object_placement
    from ifcopenshell.api.pset import add_pset, edit_pset
    from ifcopenshell.api.feature import add_feature, add_filling
    f=api.file(schema='IFC4');mapping={};checks={}
    def entity(cls,key,name):
        obj=create_entity(f,ifc_class=cls,name=name)
        obj.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],key))
        return obj
    def aggregate(parent,children):
        rel=assign_object(f,products=children,relating_object=parent)
        rel.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'aggregate/'+parent.GlobalId))
    project=entity('IfcProject','project',spec['project_id'])
    project.Description=encode({'scope':'Local source coordinate model; CRS/true north not inferred', 'source_project':spec.get('building',{}).get('project')}).decode()
    project.UnitsInContext=f.create_entity('IfcUnitAssignment',Units=[f.create_entity('IfcSIUnit',UnitType=kind,Name=name)
        for kind,name in (('LENGTHUNIT','METRE'),('AREAUNIT','SQUARE_METRE'),('VOLUMEUNIT','CUBIC_METRE'),('PLANEANGLEUNIT','RADIAN'))])
    site=entity('IfcSite','site','Local source coordinate system')
    building=entity('IfcBuilding','building',spec.get('building',{}).get('project',{}).get('name','Component staging collection'))
    aggregate(project,[site]);aggregate(site,[building])
    levels=spec.get('building',{}).get('levels',[{'id':'staging-origin','name':'Component staging origin (not a real floor)','elevation':0}])
    storeys={}
    for level in levels:
        obj=entity('IfcBuildingStorey','level/'+level['id'],level['name']);obj.Elevation=level['elevation']/1000
        storeys[level['id']]=obj
    aggregate(building,list(storeys.values()))
    context=add_context(f,context_type='Model')
    body=add_context(f,context_type='Model',context_identifier='Body',target_view='MODEL_VIEW',parent=context)
    materials={}
    def provenance(obj,source_id,kind,material,source_data=None,source_units='m'):
        pset=add_pset(f,product=obj,name='GridlineProvenance')
        pset.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'provenance/'+obj.GlobalId))
        edit_pset(f,pset=pset,properties={'SourceElementId':source_id,'RequestSHA256':digest(spec),'Kind':kind,
            'MaterialId':material,'SourceData':encode(source_data or {}).decode(),'OutputUnits':'m',
            'SourceUnits':source_units,
            'Scope':'Visual geometry and source mapping; not professional approval'})
        for rel in f.get_inverse(pset):
            if rel.is_a('IfcRelDefinesByProperties'):
                rel.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'defines/'+obj.GlobalId))
        if material not in materials:materials[material]=f.create_entity('IfcMaterial',Name=material)
        f.create_entity('IfcRelAssociatesMaterial',GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'material/'+obj.GlobalId)),
                        RelatedObjects=[obj],RelatingMaterial=materials[material])
    def shape(obj,triangles,position=(0,0,0),angle=0):
        c,s=math.cos(angle),math.sin(angle);vertices=[];faces=[]
        for triangle in triangles:
            face=[]
            for point in triangle:
                x,y,z=(point[i]-position[i] for i in range(3))
                face.append(len(vertices));vertices.append((c*x+s*y,-s*x+c*y,z))
            faces.append(face)
        rep=add_mesh_representation(f,context=body,vertices=[vertices],faces=[faces],unit_scale=1)
        assign_representation(f,product=obj,representation=rep)
        matrix=np.eye(4);matrix[0:3,3]=position;matrix[0:2,0:2]=[[c,-s],[s,c]]
        edit_object_placement(f,product=obj,matrix=matrix,is_si=True)
    def contain(obj,level):
        rel=assign_container(f,products=[obj],relating_structure=storeys[level])
        # API may combine relationships per storey; its GUID is tied to that storey.
        rel.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'containment/'+level))
    def add_element(source_id,kind,records,level,position=(0,0,0),angle=0,material='UNKNOWN',source_data=None,source_units='m'):
        if kind not in CLASSES and kind!='wall':raise ValueError('unsupported IFC semantic kind')
        obj=entity(CLASSES[kind] if kind in CLASSES else 'IfcWall','element/'+source_id,source_id)
        if hasattr(obj,'PredefinedType'):obj.PredefinedType='NOTDEFINED'
        if hasattr(obj,'ObjectType'):obj.ObjectType=kind
        provenance(obj,source_id,kind,material,source_data,source_units);contain(obj,level)
        triangles=raw_triangles(records);shape(obj,triangles,position,angle)
        area=0
        for triangle in triangles:
            a,b,c=(point[:3] for point in triangle)
            u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            area+=math.sqrt(sum(n*n for n in normal))/2
        quantity=f.create_entity('IfcElementQuantity',GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'quantities/'+obj.GlobalId)),
            Name='GridlineVisualQuantities',Description='Triangulated surface sum, including contacts; not net exposed/usable area',
            Quantities=[f.create_entity('IfcQuantityArea',Name='TriangulatedSurfaceArea',AreaValue=area)])
        f.create_entity('IfcRelDefinesByProperties',GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'defines-quantities/'+obj.GlobalId)),
                        RelatedObjects=[obj],RelatingPropertyDefinition=quantity)
        mapping[source_id]={'guid':obj.GlobalId,'class':obj.is_a(),'kind':kind,'level':level}
        checks[source_id]={'triangles':triangles,'guid':obj.GlobalId,'kind':kind,'surface_area_m2':area}
        return obj
    source=spec.get('building');walls_by_id={};groups={};openings={}
    if source:
        entries=geometry_entries(compile_scene(source));wall_entries=[e for e in entries if e['kind']=='wall']
        for entry in wall_entries:
            record=meshes['meshes']['building__'+entry['name']]
            obj=add_element(entry['gridline_id'],'wall',[record],entry['metadata']['level'],source_data={'source_ids':entry['source_ids'],'role':entry['role']},source_units='mm')
            checks[entry['gridline_id']]['wall_entry']=entry
            groups[entry['gridline_id']]=obj
            for ident in entry['source_ids']:
                part=entity('IfcBuildingElementPart','source-wall/'+ident,ident)
                provenance(part,ident,'source_wall_segment','UNKNOWN',next(w for w in source['walls'] if w['id']==ident),source_units='mm')
                aggregate(obj,[part])
                walls_by_id[ident]=obj
                mapping[ident]={'guid':part.GlobalId,'geometry_wall_guid':obj.GlobalId,'class':part.is_a(),'kind':'source_wall_segment','level':entry['metadata']['level']}
        wall_data={w['id']:w for w in source['walls']};level_data={l['id']:l for l in source['levels']}
        for opening in source['openings']:
            wall=wall_data[opening['wall']];level=level_data[wall['level']]
            dx=wall['end'][0]-wall['start'][0];dy=wall['end'][1]-wall['start'][1];length=math.hypot(dx,dy);offset=opening['offset']+opening['width']/2
            position=((wall['start'][0]+dx/length*offset)/1000,(wall['start'][1]+dy/length*offset)/1000,
                      (level['elevation']+opening.get('sill',0))/1000)
            angle=math.atan2(dy,dx)
            feature=entity('IfcOpeningElement','opening/'+opening['id'],'Opening '+opening['id']);feature.PredefinedType='OPENING'
            provenance(feature,opening['id'],'opening','UNKNOWN',opening,source_units='mm')
            # Explicit aperture solid, independent of display leaf/glass geometry.
            w,d,h=opening['width']/1000,wall['thickness']/1000,opening['height']/1000
            points=[(-w/2,-d/2,0),(w/2,-d/2,0),(w/2,d/2,0),(-w/2,d/2,0),(-w/2,-d/2,h),(w/2,-d/2,h),(w/2,d/2,h),(-w/2,d/2,h)]
            faces=((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
            rep=add_mesh_representation(f,context=body,vertices=[points],faces=[faces],unit_scale=1)
            assign_representation(f,product=feature,representation=rep)
            matrix=np.eye(4);matrix[0:3,3]=position;matrix[0:2,0:2]=[[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]]
            edit_object_placement(f,product=feature,matrix=matrix,is_si=True)
            relationship=add_feature(f,feature=feature,element=walls_by_id[opening['wall']])
            relationship.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'void/'+opening['id']))
            openings[opening['id']]=feature
            checks['opening/'+opening['id']]={'guid':feature.GlobalId,'kind':'opening','opening_box':{'center_m':[position[0],position[1],position[2]+h/2],'dimensions_m':[w,d,h],'rotation_z':angle}}
        substituted={i['source_element_id'] for i in spec['components'] if i['host_id']}
        for entry in entries:
            if entry['kind']=='wall' or entry['gridline_id'] in substituted:continue
            opening=next(o for o in source['openings'] if o['id']==entry['gridline_id'])
            kind=opening['kind'];wall=wall_data[opening['wall']]
            obj=add_element(opening['id'],kind,[meshes['meshes']['building__'+entry['name']]],wall['level'],source_data=opening,source_units='mm')
            obj.OverallWidth=opening['width']/1000;obj.OverallHeight=opening['height']/1000
            relationship=add_filling(f,opening=openings[opening['id']],element=obj)
            relationship.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'fills/'+opening['id']))
    for item in spec['components']:
        kind=item['kind'];source_id=item['source_element_id'];records=[meshes['meshes'][name] for name in meshes['components'][item['id']]['members']]
        level=item.get('level_id')
        if level is None:
            level=next(w['level'] for w in source['walls'] if w['id']==item['host_id']) if source and item['host_id'] else 'staging-origin'
        obj=add_element(source_id,kind,records,level,item['position_m'],math.radians(item['rotation_deg']),item['material']['id'],source_data={'component_request':item,'canonical_opening':next((o for o in source['openings'] if o['id']==source_id),None) if source else None,'units':{'component_request':'m','canonical_building':'mm'}})
        if kind in ('door','window'):
            obj.OverallWidth=item['parameters']['width'];obj.OverallHeight=item['parameters']['height']
        if item['host_id']:
            relationship=add_filling(f,opening=openings[source_id],element=obj)
            relationship.GlobalId=api.guid.compress(stable_uuid(spec['project_id'],'fills/'+source_id))
        if kind=='stairs':
            obj.NumberOfRisers=item['parameters']['step_count'];obj.NumberOfTreads=item['parameters']['step_count']
            obj.RiserHeight=item['parameters']['riser_height'];obj.TreadLength=item['parameters']['tread_depth']
    return f,mapping,checks


def verify_model(api, path, spec, mapping, checks, req):
    f=api.open(str(path))
    if f.schema!='IFC4':raise ValueError('IFC schema changed')
    logger=api.validate.json_logger();api.validate.validate(f,logger,express_rules=True)
    if logger.statements:raise ValueError('IFC schema/EXPRESS validation failed: '+str(logger.statements[:3]))
    roots=f.by_type('IfcRoot');guids=[o.GlobalId for o in roots]
    if len(guids)!=len(set(guids)):raise ValueError('duplicate IFC GUIDs')
    units=f.by_type('IfcProject')[0].UnitsInContext.Units
    length=[u for u in units if u.is_a('IfcSIUnit') and u.UnitType=='LENGTHUNIT']
    if len(length)!=1 or length[0].Name!='METRE' or length[0].Prefix is not None:raise ValueError('IFC length units changed')
    for source_id,record in mapping.items():
        obj=f.by_guid(record['guid'])
        if obj.is_a()!=record['class']:raise ValueError('IFC semantic class changed')
        props=api.util.element.get_psets(obj).get('GridlineProvenance',{})
        if props.get('SourceElementId')!=source_id or props.get('RequestSHA256')!=digest(spec):raise ValueError('IFC source provenance lost')
        if any(key not in props for key in req['required_properties']):raise ValueError('mandatory IFC property missing')
        if not req['allow_unknown_materials'] and props.get('MaterialId')=='UNKNOWN':raise ValueError('project disallows unknown material information')
    settings=api.geom.settings();settings.set(settings.USE_WORLD_COORDS,True)
    for source_id,record in checks.items():
        obj=f.by_guid(record['guid'])
        if 'opening_box' in record:
            shape=api.geom.create_shape(settings,obj)
            vertices=[list(shape.geometry.verts[i:i+3]) for i in range(0,len(shape.geometry.verts),3)]
            faces=[list(shape.geometry.faces[i:i+3]) for i in range(0,len(shape.geometry.faces),3)]
            check_surface(vertices,faces,[record['opening_box']],1e-5)
            continue
        q=api.util.element.get_psets(obj).get('GridlineVisualQuantities',{})
        if abs(q.get('TriangulatedSurfaceArea',-1)-record['surface_area_m2'])>1e-5:raise ValueError('IFC mesh quantity changed')
        shape=api.geom.create_shape(settings,obj)
        vertices=[list(shape.geometry.verts[i:i+3]) for i in range(0,len(shape.geometry.verts),3)]
        faces=[list(shape.geometry.faces[i:i+3]) for i in range(0,len(shape.geometry.faces),3)]
        if 'wall_entry' in record:
            entry=record['wall_entry'];check_surface(vertices,faces,entry['source_boxes'],1e-5,entry['void_boxes'])
        else:
            actual=[[[*vertices[index],0,0,0,0,0] for index in face] for face in faces]
            expected=[[[*point[:3],0,0,0,0,0] for point in triangle] for triangle in record['triangles']]
            compare_triangles(expected,actual)
    if source:=spec.get('building'):
        if len(f.by_type('IfcOpeningElement'))!=len(source['openings']) or len(f.by_type('IfcRelVoidsElement'))!=len(source['openings']):
            raise ValueError('IFC opening/host relationships lost')
        if len(f.by_type('IfcRelFillsElement'))!=len(source['openings']):raise ValueError('IFC opening filling relationships lost')
        for item in source['openings']:
            opening=f.by_guid(api.guid.compress(stable_uuid(spec['project_id'],'opening/'+item['id'])))
            if len(opening.VoidsElements)!=1 or opening.VoidsElements[0].RelatingBuildingElement.GlobalId!=mapping[item['wall']]['geometry_wall_guid']:
                raise ValueError('IFC opening attached to wrong host')
            if len(opening.HasFillings)!=1 or opening.HasFillings[0].RelatedBuildingElement.GlobalId!=mapping[item['id']]['guid']:
                raise ValueError('IFC opening attached to wrong filling')
            props=api.util.element.get_psets(opening).get('GridlineProvenance',{})
            if props.get('SourceUnits')!='mm' or json.loads(props.get('SourceData','null'))!=item:
                raise ValueError('IFC canonical opening data lost')
    return {'state':'SCHEMA_SOURCE_GEOMETRY_VERIFIED','schema':'IFC4','ifcopenshell_version':api.version,'source_sha256':digest(spec),
            'mapped_elements':len(mapping),'geometry_elements':len(checks),'requirements_sha256':digest(req),
            'not_checked':['Client-app interoperability','Project IDS unless separately supplied/validated','Regulatory/structural/manufacturing compliance',
                           'IFC PBR textures; material identities are metadata only']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path);parser.add_argument('out',type=Path);parser.add_argument('--requirements',type=Path,required=True);parser.add_argument('--expected-bundle-receipt-sha256',required=True);parser.add_argument('--expected-owner-key-sha256',required=True)
    args=parser.parse_args()
    try:
        spec,meshes,source_receipt=bundle(args.bundle,args.expected_bundle_receipt_sha256,args.expected_owner_key_sha256);req=requirements(args.requirements,spec['project_id']);api=engine()
        out=args.out.expanduser().absolute();parent=out.parent.resolve(strict=True);out=parent/out.name
        if out.exists() or out.is_symlink() or parent==Path('/'):raise ValueError('IFC output must be a new directory')
        with tempfile.TemporaryDirectory(prefix='.gridline-ifc-',dir=parent) as temporary:
            tmp=Path(temporary);model,mapping,checks=export_model(api,spec,meshes);model.write(str(tmp/'model.ifc'))
            report=verify_model(api,tmp/'model.ifc',spec,mapping,checks,req)
            (tmp/'mapping.json').write_bytes(encode(mapping));(tmp/'verification.json').write_bytes(encode(report))
            names=('model.ifc','mapping.json','verification.json')
            receipt={'schema':'gridline-ifc-receipt.v1','state':report['state'],'request_sha256':digest(spec),
                     'source_bundle_receipt_sha256':args.expected_bundle_receipt_sha256,'canonical_owner_key_sha256':args.expected_owner_key_sha256,
                     'files':{name:hashlib.sha256((tmp/name).read_bytes()).hexdigest() for name in names}}
            publish(tmp,out,receipt,names=names)
        print(json.dumps({'output':str(out),**report},indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as exc:
        print(json.dumps({'state':'BLOCKED','error':str(exc)}));return 1


if __name__=='__main__':raise SystemExit(main())
