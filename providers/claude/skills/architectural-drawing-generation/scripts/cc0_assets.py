#!/usr/bin/env python3
"""Opt-in Poly Haven 1K PBR plans/cache. No automatic network, archives or installs."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from component_spec import encode, digest
from archimesh_doctor import read_file

USER_AGENT='Gridline-CC0-Assets/1.0 (Poly Haven integration)'
CATALOG_URL='https://api.polyhaven.com/assets?t=textures'
CHANNELS={'base_color':'Diffuse','roughness':'Rough','normal':'nor_gl'}
MAX_ASSET_BYTES=8*1024*1024


def valid_url(url, hosts):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in hosts or parts.username or parts.password or parts.port not in (None,443) or parts.fragment:
        raise ValueError('untrusted asset/API URL')
    return url


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        valid_url(newurl,{'api.polyhaven.com','dl.polyhaven.org'})
        return super().redirect_request(request,fp,code,message,headers,newurl)


def fetch(url, maximum):
    valid_url(url,{'api.polyhaven.com','dl.polyhaven.org'})
    opener=build_opener(Redirects)
    with opener.open(Request(url,headers={'User-Agent':USER_AGENT}),timeout=30) as response:
        valid_url(response.url,{'api.polyhaven.com','dl.polyhaven.org'})
        length=response.headers.get('Content-Length')
        if length is not None and (not length.isdigit() or int(length)>maximum):
            raise ValueError('response exceeds byte budget')
        data=response.read(maximum+1)
        if len(data)>maximum:
            raise ValueError('response exceeds byte budget')
        return data


def plan(asset_id, metadata):
    if not isinstance(asset_id,str) or not re.fullmatch(r'[a-z0-9_]{1,80}',asset_id):
        raise ValueError('invalid Poly Haven asset ID')
    files={}
    total=0
    for channel, upstream in CHANNELS.items():
        try: entry=metadata[upstream]['1k']['jpg']
        except (KeyError,TypeError):raise ValueError('asset does not expose all supported 1K JPG PBR channels') from None
        if not isinstance(entry,dict) or type(entry.get('size'))!=int or not 0<entry['size']<=MAX_ASSET_BYTES:
            raise ValueError('invalid asset byte size')
        if not isinstance(entry.get('md5'),str) or not re.fullmatch(r'[a-f0-9]{32}',entry['md5']):
            raise ValueError('missing upstream integrity metadata')
        url=valid_url(entry['url'],{'dl.polyhaven.org'})
        if not urlsplit(url).path.endswith('.jpg'):
            raise ValueError('only direct JPG textures are supported; no archive extraction')
        files[channel]={'url':url,'bytes':entry['size'],'upstream_md5':entry['md5']}
        total+=entry['size']
    if total>MAX_ASSET_BYTES:
        raise ValueError('asset total exceeds 8 MiB budget')
    return {'schema':'gridline-cc0-plan.v1','provider':'Poly Haven','asset_id':asset_id,'license':'CC0-1.0',
            'source_url':'https://polyhaven.com/a/'+asset_id,'api_url':'https://api.polyhaven.com/files/'+asset_id,
            'resolution':'1k','files':files,'bytes':total,'attribution':'Textures from Poly Haven',
            'integrity_note':'Upstream MD5 is transport metadata, not an authenticity signature; cache records SHA256 of consumed bytes'}


def check_plan(value):
    if not isinstance(value,dict) or value.get('schema')!='gridline-cc0-plan.v1':
        raise ValueError('invalid asset plan')
    metadata={upstream:{'1k':{'jpg':{'url':entry['url'],'size':entry['bytes'],'md5':entry['upstream_md5']}}}
              for channel,upstream in CHANNELS.items() for entry in [value['files'][channel]]}
    if plan(value['asset_id'],metadata)!=value:
        raise ValueError('asset plan fields changed')
    return value


def validate_image(data):
    from PIL import Image
    try:
        with Image.open(io.BytesIO(data)) as bitmap:
            if bitmap.format!='JPEG' or max(bitmap.size)!=1024 or min(bitmap.size)<=0:
                raise ValueError('unexpected image format or pixel budget')
            bitmap.load()
    except (OSError,Image.DecompressionBombError) as exc:
        raise ValueError('invalid/oversized JPEG texture') from exc


def download(value, cache, approval):
    value=check_plan(value)
    ident=digest(value)
    if approval!=ident:
        raise ValueError('explicit approval of exact plan SHA256 required before any download')
    cache=Path(cache).expanduser().absolute()
    if cache.is_symlink() or any(p.is_symlink() for p in cache.parents if str(p) not in ('/tmp','/var')):
        raise ValueError('cache symlinks unsupported')
    cache.mkdir(parents=True,exist_ok=True,mode=0o700)
    dest=cache/ident
    if dest.exists():
        return verify_cache(dest,ident)
    with tempfile.TemporaryDirectory(prefix='.gridline-asset-',dir=cache) as temporary:
        tmp=Path(temporary); records={}
        for channel,entry in value['files'].items():
            data=fetch(entry['url'],entry['bytes'])
            if len(data)!=entry['bytes'] or hashlib.md5(data,usedforsecurity=False).hexdigest()!=entry['upstream_md5']:
                raise ValueError('download integrity mismatch')
            validate_image(data)
            (tmp/(channel+'.jpg')).write_bytes(data)
            records[channel]={'file':channel+'.jpg','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
        manifest={'schema':'gridline-cc0-cache.v1','plan_sha256':ident,'plan':value,'files':records}
        (tmp/'asset.json').write_bytes(encode(manifest))
        # Only a previously absent directory is published; partial downloads stay temporary.
        dest.mkdir(mode=0o700)
        for item in tmp.iterdir():
            with (dest/item.name).open('xb') as target:target.write(item.read_bytes())
    return verify_cache(dest,ident)


def verify_cache(folder, expected_plan):
    folder=Path(folder).resolve(strict=True)
    manifest=json.loads(read_file(folder/'asset.json'))
    value=check_plan(manifest['plan'])
    if manifest.get('schema')!='gridline-cc0-cache.v1' or digest(value)!=expected_plan or manifest.get('plan_sha256')!=expected_plan:
        raise ValueError('cache provenance mismatch')
    if set(manifest['files'])!=set(CHANNELS):raise ValueError('cache channel inventory changed')
    for channel,record in manifest['files'].items():
        if record['file']!=channel+'.jpg':raise ValueError('cache path injection')
        # All approved channels are bounded by the plan, including corruption after download.
        p=folder/record['file']
        if p.stat().st_size!=value['files'][channel]['bytes'] or p.is_symlink():raise ValueError('cached size/path changed')
        data=read_file(p,max_bytes=MAX_ASSET_BYTES)
        if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('cache SHA256 mismatch')
        if hashlib.md5(data,usedforsecurity=False).hexdigest()!=value['files'][channel]['upstream_md5']:raise ValueError('cached bytes differ from approved upstream metadata')
        validate_image(data)
    return manifest


def catalog(index, query='', refresh=False, allow_network=False):
    index=Path(index)
    if refresh:
        if not allow_network:raise ValueError('catalog refresh requires explicit network permission')
        if index.exists() or index.is_symlink():raise ValueError('catalog snapshots are immutable; select a new index path')
        assets=json.loads(fetch(CATALOG_URL,2*1024*1024))
        if not isinstance(assets,dict):raise ValueError('invalid provider catalog')
        snapshot={'schema':'gridline-cc0-catalog.v1','source':CATALOG_URL,'assets':assets}
        index.parent.mkdir(parents=True,exist_ok=True)
        with index.open('xb') as handle:handle.write(encode(snapshot))
    else:
        snapshot=json.loads(read_file(index,max_bytes=2*1024*1024))
        if snapshot.get('schema')!='gridline-cc0-catalog.v1' or snapshot.get('source')!=CATALOG_URL:
            raise ValueError('invalid local catalog')
        assets=snapshot['assets']
    selected=[]
    for ident,entry in sorted(assets.items()):
        if not isinstance(entry,dict) or entry.get('type')!=1:continue
        if query.casefold() not in (ident+' '+str(entry.get('name',''))).casefold():continue
        if not re.fullmatch(r'[a-z0-9_]{1,80}',ident):continue
        selected.append({'id':ident,'name':entry.get('name',ident),'provider':'Poly Haven','license':'CC0-1.0','source_url':'https://polyhaven.com/a/'+ident})
    return {'state':'CACHED_CATALOG','catalog_sha256':digest(snapshot),'matches':len(selected),'items':selected[:50],
            'scope':'PBR textures only; 3D model archives/HDRIs are unsupported, no asset bytes downloaded'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    c=sub.add_parser('catalog');c.add_argument('index',type=Path);c.add_argument('--query',default='');c.add_argument('--refresh',action='store_true');c.add_argument('--allow-network',action='store_true')
    p=sub.add_parser('plan');p.add_argument('asset_id');p.add_argument('--allow-network',action='store_true')
    d=sub.add_parser('download');d.add_argument('plan',type=Path);d.add_argument('cache',type=Path);d.add_argument('--approve-plan-sha256',required=True)
    v=sub.add_parser('verify');v.add_argument('folder',type=Path);v.add_argument('--expected-plan-sha256',required=True)
    args=parser.parse_args()
    try:
        if args.command=='catalog':result=catalog(args.index,args.query,args.refresh,args.allow_network)
        elif args.command=='plan':
            if not args.allow_network:raise ValueError('network is off; explicit --allow-network required')
            if not re.fullmatch(r'[a-z0-9_]{1,80}',args.asset_id):raise ValueError('invalid asset ID')
            result=plan(args.asset_id,json.loads(fetch('https://api.polyhaven.com/files/'+args.asset_id,2*1024*1024)))
            result={'plan':result,'approval_sha256':digest(result)}
        elif args.command=='download':result=download(json.loads(read_file(args.plan)),args.cache,args.approve_plan_sha256)
        else:result=verify_cache(args.folder,args.expected_plan_sha256)
        print(json.dumps(result,indent=2));return 0
    except (ValueError,OSError,KeyError,TypeError,ImportError) as exc:
        print(json.dumps({'state':'BLOCKED','error':str(exc)}));return 1



def glb_texture_facts(path, material_id):
    from PIL import Image
    from glb_qa import read_glb
    doc,binary=read_glb(path)
    materials=[m for m in doc.get('materials',[]) if m.get('name')=='Gridline_'+material_id]
    if len(materials)!=1:raise ValueError('missing/duplicate GLB PBR material')
    material=materials[0];pbr=material.get('pbrMetallicRoughness',{})
    def image_for(texture):
        if type(texture.get('index'))!=int:raise ValueError('missing GLB texture index')
        index=texture['index']
        if not 0<=index<len(doc.get('textures',[])):raise ValueError('GLB texture out of bounds')
        source=doc['textures'][index].get('source')
        if type(source)!=int or not 0<=source<len(doc.get('images',[])):raise ValueError('missing embedded GLB image')
        entry=doc['images'][source]
        if 'uri' in entry or type(entry.get('bufferView'))!=int:raise ValueError('external GLB image prohibited')
        view=doc['bufferViews'][entry['bufferView']];start=view.get('byteOffset',0);end=start+view['byteLength']
        with Image.open(io.BytesIO(binary[start:end])) as picture:
            if max(picture.size)>2048:raise ValueError('GLB image pixel budget exceeded')
            return picture.convert('RGB')
    base=image_for(pbr.get('baseColorTexture',{}));normal=image_for(material.get('normalTexture',{}));packed=image_for(pbr.get('metallicRoughnessTexture',{}))
    if pbr.get('baseColorFactor',[1,1,1,1])!=[1,1,1,1] or pbr.get('roughnessFactor',1)!=1:
        raise ValueError('unexpected GLB PBR factors')
    metallic=packed.getchannel('B')
    if pbr.get('metallicFactor',1)!=0 and metallic.getextrema()!=(0,0):raise ValueError('nonmetal asset exported with effective metallic pixels')
    return {'base_color_pixels_sha256':hashlib.sha256(base.tobytes()).hexdigest(),
            'normal_pixels_sha256':hashlib.sha256(normal.tobytes()).hexdigest(),
            'roughness_pixels_sha256':hashlib.sha256(packed.getchannel('G').tobytes()).hexdigest(),
            'base_color_size':list(base.size),'normal_size':list(normal.size),'roughness_size':list(packed.size),
            'metallic_pixels':'ZERO_EFFECTIVE','state':'EMBEDDED_PBR_READBACK'}


def verify_glb_textures(path, cache, material_id):
    from PIL import Image
    cache=Path(cache)
    manifest=json.loads(read_file(cache/'asset.json'))
    verify_cache(cache,manifest['plan_sha256'])
    facts=glb_texture_facts(path,material_id)
    for channel,key in (('base_color','base_color_pixels_sha256'),('normal','normal_pixels_sha256'),('roughness','roughness_pixels_sha256')):
        with Image.open(cache/(channel+'.jpg')) as image:
            rgb=image.convert('RGB')
            pixels=rgb.getchannel('R').tobytes() if channel=='roughness' else rgb.tobytes()
            if hashlib.sha256(pixels).hexdigest()!=facts[key]:raise ValueError('GLB texture pixels differ from approved asset')
    return facts


if __name__=='__main__':raise SystemExit(main())
