"""Read raw GLB triangles before host import can repair duplicate mesh faces.

Deliberately restricted to Gridline's embedded, uncompressed glTF 2.0 profile.
No external resources, sparse accessors, geometry extensions or external reads.
"""
import json
import math
import struct
from pathlib import Path


def read_glb(path):
    path=Path(path)
    if path.stat().st_size>64*1024*1024:raise ValueError('GLB byte budget exceeded')
    raw=path.read_bytes()
    if len(raw)<20 or struct.unpack_from('<4sII',raw)!=(b'glTF',2,len(raw)):
        raise ValueError('invalid GLB header')
    offset=12;chunks=[]
    while offset<len(raw):
        if offset+8>len(raw):raise ValueError('truncated GLB chunk')
        length,kind=struct.unpack_from('<II',raw,offset);offset+=8
        if length%4 or offset+length>len(raw):raise ValueError('invalid GLB chunk bounds')
        chunks.append((kind,raw[offset:offset+length]));offset+=length
    if [c[0] for c in chunks]!=[0x4E4F534A,0x004E4942]:raise ValueError('unsupported GLB chunks')
    doc=json.loads(chunks[0][1],parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite GLB JSON')));binary=chunks[1][1]
    extensions=set(doc.get('extensionsUsed',[])) | set(doc.get('extensionsRequired',[]))
    if doc.get('asset',{}).get('version')!='2.0' or extensions-{'KHR_materials_transmission'}:
        raise ValueError('unsupported GLB version/extensions')
    buffers=doc.get('buffers',[])
    if len(buffers)!=1 or 'uri' in buffers[0] or not 0<=len(binary)-buffers[0]['byteLength']<=3:
        raise ValueError('unsupported GLB buffer')
    for picture in doc.get('images',[]):
        ref=picture.get('bufferView')
        if ('uri' in picture or type(ref)!=int or not 0<=ref<len(doc.get('bufferViews',[]))
                or picture.get('mimeType') not in ('image/png','image/jpeg')):
            raise ValueError('external/unsupported GLB image resource')
        view=doc['bufferViews'][ref]
        base=view.get('byteOffset',0);length=view.get('byteLength')
        if type(base)!=int or type(length)!=int or base<0 or length<=0 or base+length>len(binary) or view.get('buffer')!=0:
            raise ValueError('GLB image outside buffer')
    return doc,binary


def accessor(doc,binary,index):
    if type(index)!=int or not 0<=index<len(doc['accessors']):raise ValueError('invalid GLB accessor reference')
    a=doc['accessors'][index]
    if 'sparse' in a or a.get('normalized'):raise ValueError('unsupported GLB accessor')
    count=a['count'];types={5121:('B',1),5123:('H',2),5125:('I',4),5126:('f',4)}
    if type(count)!=int or not 0<count<=2_000_000 or a['componentType'] not in types:
        raise ValueError('invalid GLB accessor type/count')
    fmt,size=types[a['componentType']];width={'SCALAR':1,'VEC3':3}.get(a['type'])
    if width is None:raise ValueError('unsupported GLB accessor width')
    ref=a['bufferView']
    if type(ref)!=int or not 0<=ref<len(doc['bufferViews']):raise ValueError('invalid GLB view reference')
    view=doc['bufferViews'][ref]
    stride=view.get('byteStride',width*size);start=a.get('byteOffset',0)
    base=view.get('byteOffset',0);length=view['byteLength']
    if (any(type(v)!=int for v in (start,base,length,stride)) or view['buffer']!=0 or min(start,base,length)<0 or stride<width*size
            or start+(count-1)*stride+width*size>length or base+length>len(binary)):
        raise ValueError('GLB accessor outside buffer')
    return [struct.unpack_from('<'+fmt*width,binary,base+start+i*stride) for i in range(count)]


def check_glb(path):
    doc,binary=read_glb(path);triangles=0
    references=[n['mesh'] for n in doc.get('nodes',[]) if 'mesh' in n]
    if any(type(i)!=int for i in references) or sorted(references)!=list(range(len(doc.get('meshes',[])))):
        raise ValueError('unused/instanced/invalid GLB meshes unsupported')
    for mesh in doc['meshes']:
        seen=set()
        for primitive in mesh['primitives']:
            if primitive.get('mode',4)!=4 or primitive.get('extensions'):
                raise ValueError('unsupported GLB primitive')
            attributes=primitive['attributes']
            positions=accessor(doc,binary,attributes['POSITION'])
            normals=accessor(doc,binary,attributes['NORMAL'])
            indices=[i[0] for i in accessor(doc,binary,primitive['indices'])]
            if (len(indices)%3 or len(normals)!=len(positions)
                    or any(not math.isfinite(v) for p in positions+normals for v in p)):
                raise ValueError('invalid GLB triangle data')
            for start in range(0,len(indices),3):
                ids=indices[start:start+3]
                if any(type(i)!=int or not 0<=i<len(positions) for i in ids):raise ValueError('GLB index out of range')
                points=[positions[i] for i in ids];signature=tuple(sorted(points))
                if signature in seen:raise ValueError('raw GLB duplicate triangle')
                seen.add(signature)
                a,b,c=points;u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
                normal=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
                if sum(x*x for x in normal)<1e-20:raise ValueError('raw GLB degenerate triangle')
                if any(sum(normal[k]*normals[i][k] for k in range(3))<=0 for i in ids):
                    raise ValueError('raw GLB inconsistent normals')
                triangles+=1
    return dict(status='PASS',raw_triangles=triangles,mesh_count=len(references))
