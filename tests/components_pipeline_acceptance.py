"""Explicit offline, synthetic source→drawings→Blender→IFC acceptance.

Requires approved external ARCHIMESH, installed Blender, CAD+IFC dependencies.
Uses a new output directory and a disposable test-owner key; no client/live-host
state, global installation, model calls or network requests.
"""
import argparse
import contextlib
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/architectural-drawing-generation'
sys.path.insert(0,str(SKILL/'scripts'))
import archimesh_components as bridge
import component_ifc as exchange
import component_state as ledger
from component_spec import encode,validate,digest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('out',type=Path);parser.add_argument('--addon-source',type=Path,required=True)
parser.add_argument('--approve-addon-sha256',required=True)
args=parser.parse_args();out=args.out.resolve();out.mkdir(mode=0o700)
api=exchange.engine();results={}
def invoke(function,arguments,name):
 with (out/(name+'.log')).open('w') as log,contextlib.redirect_stdout(log):code=function(arguments)
 if code:raise RuntimeError(name+' failed; inspect owned log')
 return json.loads((out/(name+'.log')).read_text())
def command(arguments,name):
 with (out/(name+'.log')).open('w') as log:subprocess.run(arguments,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=180)
def hashes(folder,names):return {name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in names}
def artifacts(spec,label,database,keypin,drawings):
 source=out/(label+'.json');source.write_bytes(encode(spec));native=out/(label+'-native');ifc=out/(label+'-ifc')
 build=invoke(bridge.main,['build',str(source),str(native),'--addon-source',str(args.addon_source),'--approve-addon-sha256',args.approve_addon_sha256,'--state-db',str(database),'--owner-key-sha256',keypin],label+'-native-build')
 req={'schema':'gridline-ifc-requirements.v1','project_id':spec['project_id'],'required_properties':['SourceElementId','RequestSHA256','Kind','MaterialId'],'allow_unknown_materials':True}
 requirements=out/(label+'-requirements.json');requirements.write_bytes(encode(req))
 ifc_args=[str(native),str(ifc),'--state-db',str(database),'--requirements',str(requirements),'--expected-bundle-receipt-sha256',build['receipt_sha256'],'--expected-owner-key-sha256',keypin]
 exported=invoke(exchange.main,ifc_args,label+'-ifc-build')
 before=hashes(ifc,(*exchange.IFC_OUTPUTS,'receipt.json'))
 invoke(exchange.main,[*ifc_args,'--verify','--expected-ifc-receipt-sha256',exported['receipt_sha256']],label+'-ifc-reopen')
 assert before==hashes(ifc,before),'IFC public verifier mutated published bytes'
 if drawings:
  building=out/(label+'.building.json');building.write_bytes(encode(spec['building']))
  cad=out/(label+'-drawings')
  command([sys.executable,str(SKILL/'scripts/aec_cad.py'),'build',str(building),str(cad)],label+'-cad-build')
  command([sys.executable,str(SKILL/'scripts/aec_cad.py'),'check',str(building),str(cad)],label+'-cad-check')
 return {'source_sha256':digest(spec),'native':build,'ifc':exported,'ifc_public_verify':'PASS; bytes unchanged'}

with tempfile.TemporaryDirectory(prefix='gridline-synthetic-owner-') as temporary:
 signing=Path(temporary);key=signing/'test-owner.pem';payload=signing/'payload';signature=signing/'signature'
 subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(key)],check=True,capture_output=True)
 public=subprocess.run(['openssl','pkey','-in',str(key),'-pubout'],check=True,capture_output=True).stdout
 def sign(message):
  payload.write_bytes(message);subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(key),'-rawin','-in',str(payload),'-out',str(signature)],check=True,capture_output=True);return signature.read_bytes()
 def initialize(database,spec):
  message=ledger.initialization_payload(spec,'synthetic-test-owner',public)
  return ledger.initialize(database,spec,'synthetic-test-owner',public_key=public,signature=sign(message))
 spec=json.loads((SKILL/'references/example-two-level.components.json').read_text())
 spec['building']['sheets'].append({'number':'A-201','title':'Synthetic upper floor plan','level':'L01','scale':100,'size':'A3'})
 validate(spec);database=out/'project.sqlite';binding=initialize(database,spec)
 results['before']=artifacts(spec,'before',database,binding['owner_key_sha256'],True)
 component=copy.deepcopy(spec['components'][0]);opening=copy.deepcopy(next(o for o in spec['building']['openings'] if o['id']==component['source_element_id']))
 opening['width']+=100;component['parameters']['width']+=.1;component['position_m'][0]+=.05
 proposal=ledger.propose(database,binding['revision'],{'openings':[opening],'components':[component]},'synthetic-test-agent','Explicit100mm wider test opening; not a client design','Controlled before/after source fixture')
 ledger.approve(database,proposal['proposal'],'synthetic-test-owner',sign(proposal['approval_payload'].encode()))
 committed=ledger.commit(database,proposal['proposal']);after=ledger.inspect(database)['document']
 results['after']=artifacts(after,'after',database,binding['owner_key_sha256'],True)
 before_map=json.loads((out/'before-ifc/mapping.json').read_text());after_map=json.loads((out/'after-ifc/mapping.json').read_text())
 assert before_map.keys()==after_map.keys()
 assert all(before_map[i]['guid']==after_map[i]['guid'] for i in before_map),'source element GUID instability'
 first=api.open(str(out/'before-ifc/model.ifc'));second=api.open(str(out/'after-ifc/model.ifc'))
 assert {e.GlobalId for e in first.by_type('IfcRoot')}=={e.GlobalId for e in second.by_type('IfcRoot')},'IFC root GUID instability'
 ident=component['source_element_id'];old=first.by_guid(before_map[ident]['guid']);new=second.by_guid(after_map[ident]['guid'])
 import ezdxf
 measured=[]
 for label in ('before','after'):
  doc=ezdxf.readfile(out/(label+'-drawings')/'A-101.dxf')
  arcs=[e for e in doc.modelspace().query('ARC') if e.has_xdata('GRIDLINE') and any(t.value==ident for t in e.get_xdata('GRIDLINE'))]
  assert len(arcs)==1,'ambiguous actual DXF door geometry';measured.append(arcs[0].dxf.radius/1000)
 assert abs(old.OverallWidth-measured[0])<1e-7 and abs(new.OverallWidth-measured[1])<1e-7
 assert abs(new.OverallWidth-old.OverallWidth-.1)<1e-7
 settings=api.geom.settings();settings.set(settings.USE_WORLD_COORDS,True)
 host=before_map[component['host_id']]['geometry_wall_guid']
 volumes=[api.util.shape.get_volume(api.geom.create_shape(settings,f.by_guid(host)).geometry) for f in (first,second)]
 thickness=next(w['thickness'] for w in spec['building']['walls'] if w['id']==component['host_id'])/1000
 assert abs(volumes[0]-volumes[1]-.1*opening['height']/1000*thickness)<1e-5,'IFC opening/wall quantity mismatch'
 results['revision']={'proposal':proposal,'commit':committed,'mapped_elements':len(before_map),'all_source_and_relationship_guids_stable':True,'actual_dxf_door_width_m':measured,'actual_ifc_door_width_m':[old.OverallWidth,new.OverallWidth],'actual_host_wall_volumes_m3':volumes,'scope':'Explicit synthetic100mm revision; professional clearance/IDS/client interoperability not claimed'}
 all_spec=json.loads((SKILL/'references/example-components.json').read_text());all_db=out/'all-kinds.sqlite';all_binding=initialize(all_db,all_spec)
 results['all_kinds']=artifacts(all_spec,'all-kinds',all_db,all_binding['owner_key_sha256'],False)
results.update(state='PASS_SYNTHETIC_OFFLINE_PIPELINE',network_requests=0,real_owner_approval=False,test_private_key_discarded=True,not_checked=['Professional/client IDS acceptance','Revit/AutoCAD live transactions','Interactive upstream ARCHIMESH panels'])
(out/'pipeline-acceptance.json').write_bytes(encode(results))
print(json.dumps({'state':results['state'],'output':str(out),'mapped_before_after':results['revision']['mapped_elements'],'all_kinds':len(all_spec['components']),'guids_stable':True,'dxf_ifc_door_widths_m':measured},indent=2))
