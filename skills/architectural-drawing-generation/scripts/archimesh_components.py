#!/usr/bin/env python3
"""Typed external ARCHIMESH components: offline, disposable, new-output-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from archimesh_doctor import inspect_source, REFERENCE, read_file, probe_host
from component_spec import validate, encode, digest, CATALOG, load
from blender_native import publish
from cc0_assets import verify_cache, verify_glb_textures, glb_texture_facts

RUNTIME_FILES = ('components_worker.py','component_spec.py','component_mesh.py','blender_native.py',
                 'building_spec.py','wall_topology.py','mesh_qa.py','glb_qa.py',
                 'archimesh_components.py','archimesh_doctor.py','cc0_assets.py','component_state.py','component_approval.py')
DRIVER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
OUTPUTS = ('request.json', 'components.blend', 'components.glb', 'meshes.json', 'verification.json')


def run_host(blender, command, spec_path, addon, out, *, worker_dir=HERE):
    with tempfile.TemporaryDirectory(prefix='gridline-component-profile-') as profile:
        env = {k:v for k,v in os.environ.items() if not k.startswith(('BLENDER_', 'PYTHON'))}
        for key in ('BLENDER_USER_RESOURCES','BLENDER_USER_CONFIG','BLENDER_USER_SCRIPTS',
                    'BLENDER_USER_EXTENSIONS','BLENDER_USER_DATAFILES','BLENDER_SYSTEM_SCRIPTS','BLENDER_SYSTEM_EXTENSIONS'):
            folder = Path(profile)/key; folder.mkdir(); env[key] = str(folder)
        return subprocess.run([str(blender), '--background', '--factory-startup', '--disable-autoexec', '--offline-mode',
             '--python-exit-code','1','--python',str(worker_dir/'components_worker.py'),'--',command,str(spec_path),str(addon),str(out)],
             cwd=profile, env=env, capture_output=True, text=True, timeout=180, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', type=Path, default=Path('/Applications/Blender.app/Contents/MacOS/Blender'))
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('catalog')
    check = sub.add_parser('validate'); check.add_argument('request', type=Path)
    build = sub.add_parser('build'); build.add_argument('request',type=Path); build.add_argument('out',type=Path)
    build.add_argument('--addon-source',type=Path,required=True)
    build.add_argument('--asset-cache',type=Path,help='verified local CC0 cache; build never downloads')
    build.add_argument('--approve-addon-sha256',required=True,help='explicit consent to execute exactly this official external ZIP source')
    build.add_argument('--owner-key-sha256',help='trusted owner public-key fingerprint retained from initialization')
    build.add_argument('--state-db',type=Path,help='require request to match current local committed state; blocks stale publication')
    verify = sub.add_parser('verify'); verify.add_argument('out',type=Path)
    verify.add_argument('--expected-receipt-sha256',required=True,help='pin retained from the trusted build result, not recomputed after an untrusted change')
    args = parser.parse_args(argv)
    try:
        if args.command == 'catalog':
            print(json.dumps({'schema':'gridline-components.v1','units':'m','parameters':CATALOG,
                'scope':'Visual component recipes; no rooms, host cuts, IFC or regulatory approval'},indent=2)); return 0
        if args.command == 'validate':
            spec = load(args.request); print(json.dumps({'state':'VALID_REQUEST','sha256':digest(spec),'components':len(spec['components'])})); return 0
        if os.name != 'posix':
            raise ValueError('native component publication currently requires POSIX secure directory operations')
        if args.command == 'verify':
            out = args.out.expanduser().resolve(strict=True)
            receipt_bytes=read_file(out/'receipt.json')
            if hashlib.sha256(receipt_bytes).hexdigest()!=args.expected_receipt_sha256:raise ValueError('receipt differs from the trusted build pin')
            receipt = json.loads(receipt_bytes)
            if (receipt.get('schema')!='gridline-component-receipt.v1' or receipt.get('state')!='VERIFIED_VISUAL_COMPONENTS'
                    or set(receipt.get('files',{}))!=set(OUTPUTS) or set(receipt.get('runtime_sha256',{}))!=set(RUNTIME_FILES)):
                raise ValueError('incomplete or unsupported receipt')
            with tempfile.TemporaryDirectory(prefix='gridline-component-readback-') as temporary:
                snapshot=Path(temporary);runtime=snapshot/'runtime';runtime.mkdir()
                # Reopen only the bytes validated here, without mutating the published bundle.
                for name, expected in receipt['files'].items():
                    data=read_file(out/name,max_bytes=64*1024*1024)
                    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('published artifact changed')
                    (snapshot/name).write_bytes(data)
                if receipt['request_sha256']!=digest(load(snapshot/'request.json')):raise ValueError('mismatched request receipt')
                for ident, expected in receipt.get('texture_verification',{}).items():
                    if glb_texture_facts(snapshot/'components.glb',ident)!=expected:raise ValueError('embedded texture readback changed')
                for name, expected in receipt['runtime_sha256'].items():
                    data=read_file(HERE/name)
                    if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('installed validator/runtime differs from the consumed build snapshot')
                    (runtime/name).write_bytes(data)
                if probe_host(args.blender)['version']!='5.2.3':raise ValueError('component verification is qualified only on Blender 5.2.3')
                run_host(args.blender,'verify',snapshot/'request.json',runtime,snapshot,worker_dir=runtime)
                print((snapshot/'verification.json').read_text())
            return 0
        spec = load(args.request)
        state_revision = None
        if args.state_db is not None:
            from component_state import head_revision
            if args.owner_key_sha256 is None:raise ValueError('canonical source requires the trusted owner key fingerprint')
            state_revision=head_revision(args.state_db,args.owner_key_sha256)
            if digest(spec)!=state_revision: raise ValueError('request does not match committed canonical state')
        reference = json.loads(REFERENCE.read_text())
        if args.approve_addon_sha256 != reference['archive_sha256']:
            raise ValueError('explicit exact official source execution approval required')
        report = inspect_source(args.addon_source, reference)
        if report['source_state'] != 'SOURCE_VERIFIED':
            raise ValueError('external add-on does not match the official source pin')
        out = args.out.expanduser().absolute()
        if out.exists() or out.is_symlink():
            raise ValueError('output must be new; no existing data may be overwritten')
        parent = out.parent.resolve(strict=True)
        out = parent/out.name
        if parent == Path('/') or out.name in ('', '.', '..'):
            raise ValueError('unsafe output directory')
        assets = {i['material']['asset_plan_sha256'] for i in spec['components'] if 'asset_plan_sha256' in i['material']}
        if len(assets)>4: raise ValueError('at most four distinct material asset plans per scene')
        asset_manifests = {}
        for ident in assets:
            if args.asset_cache is None: raise ValueError('textured material needs an explicit verified local asset cache')
            asset_manifests[ident] = verify_cache(args.asset_cache/ident,ident)
        host = probe_host(args.blender)
        if host['version']!='5.2.3': raise ValueError('component generation is qualified only on Blender 5.2.3')
        with tempfile.TemporaryDirectory(prefix='.gridline-components-',dir=parent) as temporary:
            tmp=Path(temporary); addon=tmp/'external'; addon.mkdir(); generated=tmp/'generated';generated.mkdir()
            runtime=tmp/'runtime';runtime.mkdir();runtime_sha256={}
            for name in RUNTIME_FILES:
                data=(HERE/name).read_bytes();(runtime/name).write_bytes(data)
                runtime_sha256[name]=hashlib.sha256(data).hexdigest()
            # Copy only pinned bytes; rehash each read to close source-swap execution races.
            for name, expected in reference['files'].items():
                data = read_file(Path(report['path'])/name)
                if hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError('source changed while taking execution snapshot')
                path=addon/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            if assets:
                (generated/'assets').mkdir()
                for ident, manifest in asset_manifests.items():
                    target=generated/'assets'/ident;target.mkdir()
                    (target/'asset.json').write_bytes(encode(manifest))
                    for record in manifest['files'].values():
                        data=read_file(args.asset_cache/ident/record['file'],max_bytes=8*1024*1024)
                        if hashlib.sha256(data).hexdigest()!=record['sha256']: raise ValueError('asset changed during build snapshot')
                        (target/record['file']).write_bytes(data)
            (generated/'request.json').write_bytes(encode(spec))
            build_result=run_host(args.blender,'build',generated/'request.json',addon,generated,worker_dir=runtime)
            run_host(args.blender,'verify',generated/'request.json',addon,generated,worker_dir=runtime)
            texture_verification = {}
            for item in spec['components']:
                ident=item['material'].get('asset_plan_sha256')
                if ident: texture_verification[item['material']['id']] = verify_glb_textures(generated/'components.glb',generated/'assets'/ident,item['material']['id'])
            if digest(load(args.request)) != digest(spec):
                raise ValueError('request changed during generation')
            verification=json.loads((generated/'verification.json').read_text())
            if args.state_db is not None and head_revision(args.state_db,args.owner_key_sha256)!=state_revision:
                raise ValueError('canonical state changed during generation; publication refused')
            if verification.get('state') != 'PASS':
                raise ValueError('component verification did not pass')
            if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=DRIVER_SHA256 or any(hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=value for name,value in runtime_sha256.items()):
                raise ValueError('Gridline source changed during build')
            files={name:hashlib.sha256(read_file(generated/name,max_bytes=64*1024*1024)).hexdigest() for name in OUTPUTS}
            receipt={'schema':'gridline-component-receipt.v1','state':'VERIFIED_VISUAL_COMPONENTS',
                'request_sha256':digest(spec),'addon_archive_sha256':reference['archive_sha256'],'host':host,
                'asset_plans':sorted(assets),'asset_provenance':{ident:{'plan':value['plan'],'files':value['files'],'evidence_scope':value.get('evidence_scope','USER_APPROVED_PLAN_AND_HASH_VERIFIED_BYTES')} for ident,value in asset_manifests.items()},'texture_verification':texture_verification,
                'worker_sha256':runtime_sha256['components_worker.py'],'runtime_sha256':runtime_sha256,'driver_sha256':DRIVER_SHA256,
                'files':files,'outputs_are_authoritative_project_state':False,'canonical_state_revision':state_revision,'canonical_owner_key_sha256':args.owner_key_sha256 if args.state_db else None,
                'unverified':['Regulatory/manufacturing acceptance','Live-host edits','IFC semantics'],
                'build_log_sha256':hashlib.sha256(build_result.stdout.encode()).hexdigest()}
            if args.state_db is None:
                publish(generated,out,receipt,names=OUTPUTS)
            else:
                from component_state import transaction, event
                with transaction(args.state_db) as database:
                    if database.execute('SELECT hash FROM head WHERE id=1').fetchone()[0]!=state_revision:
                        raise ValueError('canonical state changed before publication')
                    publish(generated,out,receipt,names=OUTPUTS)
                    event(database,'PREVIEW_PUBLISHED',digest(receipt),'gridline-component-pipeline',{'revision':state_revision,'output':str(out)})
        print(json.dumps({'output':str(out),'receipt_sha256':hashlib.sha256(read_file(out/'receipt.json')).hexdigest(),**receipt},indent=2)); return 0
    except subprocess.CalledProcessError as exc:
        print(json.dumps({'state':'BLOCKED','error':(exc.stderr+'\n'+exc.stdout)[-4000:]})); return 1
    except (OSError, ValueError, RuntimeError, ImportError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'state':'BLOCKED','error':str(exc)})); return 1


if __name__ == '__main__':
    raise SystemExit(main())
