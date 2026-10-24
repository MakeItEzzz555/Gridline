"""Bounded orthogonal box-union boundary, in metres; no host or dependencies.

Preserves the occupied envelope, without snapping gaps or inventing corner infill.
A common rotated orthogonal basis is supported; oblique mixed joins fail closed.
"""
import math
from collections import defaultdict

QUANTUM_M = 1e-7  # 0.0001 mm coordinate rounding, never a connection tolerance.
MAX_CELLS = 250_000


def local_boxes(entries):
    if not entries or len(entries)>10000:
        raise ValueError('unsupported topology input count')
    angle=entries[0]['rotation_z']
    if type(angle) not in (int,float) or not math.isfinite(angle):
        raise ValueError('invalid rotation')
    c,s=math.cos(angle),math.sin(angle)
    bounds=[]
    for entry in entries:
        values=entry['center_m']+entry['dimensions_m']+[entry['rotation_z']]
        if len(values)!=7 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in values):
            raise ValueError('invalid geometry coordinates')
        dims=entry['dimensions_m']
        if min(dims)<1e-6:
            raise ValueError('invalid or sub-micron dimensions')
        turn=(entry['rotation_z']-angle)/(math.pi/2)
        if abs(turn-round(turn))>1e-8:
            raise ValueError('oblique mixed wall joins unsupported; use a common orthogonal basis')
        dx,dy,dz=dims
        if round(turn)%2: dx,dy=dy,dx
        x,y,z=entry['center_m']
        center=[c*x+s*y,-s*x+c*y,z]
        bounds.append([[round((center[i]+sign*d/2)/QUANTUM_M)*QUANTUM_M for i,d in enumerate((dx,dy,dz))] for sign in (-1,1)])
    return angle,bounds


def union_boxes(entries,name,void_boxes=()):
    angle,bounds=local_boxes(entries+list(void_boxes))
    axes=[sorted({b[side][i] for b in bounds for side in (0,1)}) for i in range(3)]
    if math.prod(len(a)-1 for a in axes)>MAX_CELLS:
        raise ValueError('topology cell budget exceeded')
    indices=[{v:i for i,v in enumerate(a)} for a in axes]
    occupied=set()
    for number,(lo,hi) in enumerate(bounds):
        ranges=[range(indices[i][lo[i]],indices[i][hi[i]]) for i in range(3)]
        cells=((x,y,z) for x in ranges[0] for y in ranges[1] for z in ranges[2])
        if number<len(entries):occupied.update(cells)
        else:occupied.difference_update(cells)
    vertices,faces,lookup=[],[],{}
    c,s=math.cos(angle),math.sin(angle)
    # Outward winding; shared grid vertices make every retained face conformal.
    sides=[((-1,0,0),[(0,0,0),(0,0,1),(0,1,1),(0,1,0)]),
           ((1,0,0),[(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),
           ((0,-1,0),[(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),
           ((0,1,0),[(0,1,0),(0,1,1),(1,1,1),(1,1,0)]),
           ((0,0,-1),[(0,0,0),(0,1,0),(1,1,0),(1,0,0)]),
           ((0,0,1),[(0,0,1),(1,0,1),(1,1,1),(0,1,1)])]
    for cell in sorted(occupied):
        for direction,corners in sides:
            if tuple(cell[i]+direction[i] for i in range(3)) in occupied: continue
            face=[]
            for offset in corners:
                key=tuple(cell[i]+offset[i] for i in range(3))
                if key not in lookup:
                    x,y,z=(axes[i][key[i]] for i in range(3))
                    lookup[key]=len(vertices)
                    vertices.append([c*x-s*y,s*x+c*y,z])
                face.append(lookup[key])
            faces.append(face)
    result=dict(entries[0],name=name,gridline_id=name,host='',vertices=vertices,faces=faces,
                source_ids=sorted({e['gridline_id'] for e in entries}),source_boxes=entries,void_boxes=list(void_boxes))
    return result


ROLE_BY_KIND = dict(wall='wall', door='opening_door', glass='opening_glass',
    frame='opening_frame', roof='roof_slab', parapet='parapet', balcony='balcony_slab',
    railing='guard_rail', slab='floor_slab', ceiling='ceiling', furniture='furniture',
    fixture='fixture', stair='stair', site='site', terrace='terrace', pool='pool',
    coping='coping', **{'pool-step':'pool_step'}, water='water')


def geometry_entries(scene):
    """Explicit groups only: preserve level, material, group and deliberate joints."""
    groups=defaultdict(list)
    result=[]
    walls=[b for b in scene['boxes'] if b['kind']=='wall']
    voids=[]
    for aperture in scene['boxes']:
        if aperture['kind'] not in ('door','glass') or not aperture['host']: continue
        hosts=[b for b in walls if b['gridline_id']==aperture['host']]
        if not hosts: raise ValueError('opening has no wall host')
        probe=dict(aperture,dimensions_m=[aperture['dimensions_m'][0],hosts[0]['dimensions_m'][1],aperture['dimensions_m'][2]])
        voids.append(probe)
    for raw in scene['boxes']:
        if raw.get('kind') not in ROLE_BY_KIND:
            raise ValueError('unsupported/orphan geometry role')
        role=raw.get('role',ROLE_BY_KIND[raw['kind']])
        if role!=ROLE_BY_KIND[raw['kind']] and not (raw['kind']=='railing' and role=='balcony_guard'):
            raise ValueError('unsupported/orphan geometry role')
        entry=dict(raw,role=role)
        if entry['kind']=='wall':
            key=('wall',entry['metadata'].get('level',''),entry.get('material',''),entry.get('group',''),entry['metadata'].get('joint_group',''))
        elif entry.get('join_group'):
            key=(entry['kind'],entry['join_group'],entry.get('material',''),entry.get('group',''))
        else:
            result.append(entry)
            continue
        groups[key].append(entry)
    for number,(_,entries) in enumerate(sorted(groups.items())):
        result.append(union_boxes(entries,f'joined_{entries[0]["kind"]}_{number:03d}',voids if entries[0]['kind']=='wall' else ()))
    return result
