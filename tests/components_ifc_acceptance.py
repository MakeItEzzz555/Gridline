"""Actual IFC schema/source/geometry adverse tests, using private owned copies only.

Run in the optional pinned IFC test environment, supplying a trusted native bundle,
project requirements, and separately retained source receipt/owner key pins.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/scripts'))
import component_ifc as exchange

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('bundle',type=Path);parser.add_argument('--requirements',type=Path,required=True)
parser.add_argument('--receipt-pin',required=True);parser.add_argument('--owner-key-pin',required=True)
parser.add_argument('--only',action='append',help='run selected supported fault labels')
args=parser.parse_args()
spec,meshes,_=exchange.bundle(args.bundle,args.receipt_pin,args.owner_key_pin)
req=exchange.requirements(args.requirements,spec['project_id']);api=exchange.engine()
model,mapping,checks=exchange.export_model(api,spec,meshes)
results=[]
def by_kind(file,kind):return file.by_guid(next(row['guid'] for row in mapping.values() if row['kind']==kind))
def property_set(obj,name):return next(rel.RelatingPropertyDefinition for rel in obj.IsDefinedBy if rel.RelatingPropertyDefinition.Name==name)
def setprop(obj,name,value):
 prop=next(p for p in property_set(obj,'GridlineProvenance').HasProperties if p.Name==name);prop.NominalValue.wrappedValue=value
faults=['length_units','area_units','source_id','source_units','source_data','kind','missing_property','material','surface_quantity','vertex','phantom','storey_datum','storey_placement','coordinate_context','duplicate_guid','winding','raw_normals','unused_vertex']
kind=next(row['kind'] for row in mapping.values() if row['kind'] not in ('wall','space','source_wall_segment'))
if spec.get('building'):faults+=['wrong_storey','wall_remap','opening_host','opening_filling','opening_width','missing_face','room_profile','room_height','room_quantity','room_name','room_storey','opening_winding']
if any(i['kind']=='stairs' for i in spec['components']):faults+=['stair_count']
if args.only:
 if set(args.only)-set(faults):raise ValueError('selected fault unsupported by this fixture')
 faults=[fault for fault in faults if fault in args.only]
with tempfile.TemporaryDirectory(prefix='gridline-ifc-adverse-') as temporary:
 root=Path(temporary);baseline=root/'baseline.ifc';model.write(str(baseline))
 exchange.verify_model(api,baseline,spec,mapping,checks,req)
 for fault in faults:
  f=api.open(str(baseline));obj=by_kind(f,kind)
  if fault in ('length_units','area_units'):
   unit=next(u for u in f.by_type('IfcSIUnit') if u.UnitType==('LENGTHUNIT' if fault=='length_units' else 'AREAUNIT'));unit.Prefix='MILLI'
  elif fault=='source_id':setprop(obj,'SourceElementId','INVENTED')
  elif fault=='source_units':setprop(obj,'SourceUnits','unknown')
  elif fault=='source_data':setprop(obj,'SourceData','{}')
  elif fault=='kind':setprop(obj,'Kind','invented')
  elif fault=='missing_property':
   pset=property_set(obj,'GridlineProvenance');pset.HasProperties=[p for p in pset.HasProperties if p.Name!='MaterialId']
  elif fault=='material':api.util.element.get_material(obj).Name='FORGED'
  elif fault=='surface_quantity':property_set(obj,'GridlineVisualQuantities').Quantities[0].AreaValue+=1
  elif fault=='vertex':
   coordinates=obj.Representation.Representations[0].Items[0].Coordinates;points=[list(p) for p in coordinates.CoordList];points[0][0]+=.05;coordinates.CoordList=points
  elif fault=='winding':
   mesh=obj.Representation.Representations[0].Items[0];faces=list(mesh.CoordIndex);faces[0]=tuple(reversed(faces[0]));mesh.CoordIndex=faces
  elif fault=='raw_normals':obj.Representation.Representations[0].Items[0].Normals=[(0.,0.,-1.)]
  elif fault=='unused_vertex':
   coordinates=obj.Representation.Representations[0].Items[0].Coordinates;coordinates.CoordList=[*coordinates.CoordList,(99.,99.,99.)]
  elif fault=='phantom':f.create_entity('IfcBuildingElementProxy',GlobalId=api.guid.new(),Name='Unrequested geometry')
  elif fault=='storey_datum':f.by_type('IfcBuildingStorey')[0].Elevation+=1
  elif fault=='storey_placement':f.by_type('IfcBuildingStorey')[0].ObjectPlacement.RelativePlacement.Location.Coordinates=(0.,0.,2.)
  elif fault=='coordinate_context':
   context=next(c for c in f.by_type('IfcGeometricRepresentationContext') if c.is_a()=='IfcGeometricRepresentationContext');context.WorldCoordinateSystem.Location.Coordinates=(1.,0.,0.)
  elif fault=='duplicate_guid':obj.GlobalId=f.by_type('IfcBuilding')[0].GlobalId
  elif fault=='wrong_storey':
   rel=obj.ContainedInStructure[0];rel.RelatingStructure=next(s for s in f.by_type('IfcBuildingStorey') if s!=rel.RelatingStructure)
  elif fault=='wall_remap':
   part=by_kind(f,'source_wall_segment');part.Decomposes[0].RelatingObject=next(w for w in f.by_type('IfcWall') if w!=part.Decomposes[0].RelatingObject)
  elif fault=='opening_host':
   rel=f.by_type('IfcRelVoidsElement')[0];rel.RelatingBuildingElement=next(w for w in f.by_type('IfcWall') if w!=rel.RelatingBuildingElement)
  elif fault=='opening_filling':
   relations=f.by_type('IfcRelFillsElement');relations[0].RelatedBuildingElement=relations[1].RelatedBuildingElement
  elif fault=='opening_winding':
   face=f.by_type('IfcOpeningElement')[0].Representation.Representations[0].Items[0].Faces[0];face.CoordIndex=tuple(reversed(face.CoordIndex))
  elif fault=='opening_width':f.by_type('IfcDoor')[0].OverallWidth+=.1
  elif fault=='missing_face':
   mesh=f.by_type('IfcWall')[0].Representation.Representations[0].Items[0];mesh.CoordIndex=mesh.CoordIndex[:-1]
  elif fault=='room_profile':
   profile=f.by_type('IfcSpace')[0].Representation.Representations[0].Items[0].SweptArea;point=profile.OuterCurve.Points[1];point.Coordinates=(point.Coordinates[0]+.1,point.Coordinates[1])
  elif fault=='room_height':f.by_type('IfcSpace')[0].Representation.Representations[0].Items[0].Depth+=.1
  elif fault=='room_quantity':property_set(f.by_type('IfcSpace')[0],'GridlineSourceSpaceQuantities').Quantities[0].AreaValue+=1
  elif fault=='room_name':f.by_type('IfcSpace')[0].Name='Unrelated room'
  elif fault=='room_storey':
   rel=f.by_type('IfcSpace')[0].Decomposes[0];rel.RelatingObject=next(s for s in f.by_type('IfcBuildingStorey') if s!=rel.RelatingObject)
  elif fault=='stair_count':by_kind(f,'stairs').NumberOfRisers+=1
  else:raise AssertionError('unimplemented fixture '+fault)
  target=root/(fault+'.ifc');f.write(str(target))
  try:exchange.verify_model(api,target,spec,mapping,checks,req)
  except ValueError as exc:results.append({'fault':fault,'state':'REJECTED','reason':str(exc)[:500]})
  else:raise AssertionError('critical IFC false PASS: '+fault)
print('GRIDLINE_IFC_ADVERSE_RESULTS='+json.dumps({'baseline':'PASS','engine':api.version,'source_sha256':exchange.digest(spec),'count':len(results),'faults':results},sort_keys=True))
