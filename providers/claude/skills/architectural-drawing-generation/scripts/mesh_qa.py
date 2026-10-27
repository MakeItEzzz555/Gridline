"""Independent face/volume oracle. Does not import or use the union mesher."""
import math
from collections import Counter, defaultdict


def bounds_in_basis(boxes):
    """Return [min, max] bounds of each box in the first box's basis, in metres.

    Computed from projected corners, independently of the mesher. Raises ValueError
    when a box is not a quarter-turn from the first.
    """
    a=boxes[0]['rotation_z']; c,s=math.cos(a),math.sin(a)
    result=[]
    for b in boxes:
        x,y,z=b['center_m']; dx,dy,dz=b['dimensions_m']
        t=b['rotation_z']-a
        # Project all box corners, rather than using the mesher's quarter-turn rules.
        pts=[(c*(x+math.cos(b['rotation_z'])*u-math.sin(b['rotation_z'])*v)+s*(y+math.sin(b['rotation_z'])*u+math.cos(b['rotation_z'])*v),
              -s*(x+math.cos(b['rotation_z'])*u-math.sin(b['rotation_z'])*v)+c*(y+math.sin(b['rotation_z'])*u+math.cos(b['rotation_z'])*v),z+w)
             for u in (-dx/2,dx/2) for v in (-dy/2,dy/2) for w in (-dz/2,dz/2)]
        if abs(math.sin(2*t))>1e-7: raise ValueError('oracle does not support mixed oblique boxes')
        result.append(([min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]))
    return result


def union_volume(boxes,voids=()):
    """Analytic interval sweep; integrate solid intervals after aperture subtraction."""
    all_bounds=bounds_in_basis(boxes+list(voids))
    bounds=all_bounds[:len(boxes)]; cuts=all_bounds[len(boxes):]
    xs=sorted({p[0] for b in all_bounds for p in b})
    volume=0
    for xa,xb in zip(xs,xs[1:]):
        active=[b for b in bounds if b[0][0]<(xa+xb)/2<b[1][0]]
        negative=[b for b in cuts if b[0][0]<(xa+xb)/2<b[1][0]]
        ys=sorted({p[1] for b in active+negative for p in b})
        for ya,yb in zip(ys,ys[1:]):
            positive_z=[(lo[2],hi[2]) for lo,hi in active if lo[1]<(ya+yb)/2<hi[1]]
            negative_z=[(lo[2],hi[2]) for lo,hi in negative if lo[1]<(ya+yb)/2<hi[1]]
            stops=sorted({z for span in positive_z+negative_z for z in span})
            length=sum(zb-za for za,zb in zip(stops,stops[1:])
                       if any(lo<(za+zb)/2<hi for lo,hi in positive_z)
                       and not any(lo<(za+zb)/2<hi for lo,hi in negative_z))
            volume+=(xb-xa)*(yb-ya)*length
    return volume


def inside(point,boxes,margin=0):
    """True if a world point (m) is strictly inside any rotated box grown by margin.

    A negative margin shrinks the boxes.
    """
    for b in boxes:
        a=b['rotation_z']; c,s=math.cos(a),math.sin(a)
        x,y,z=[point[i]-b['center_m'][i] for i in range(3)]
        local=(c*x+s*y,-s*x+c*y,z)
        if all(abs(local[i])<b['dimensions_m'][i]/2+margin for i in range(3)):return True
    return False


def check_surface(vertices,faces,boxes,tolerance=1e-7,voids=()):
    """Verify a mesh is exactly the closed boundary of boxes minus voids.

    vertices are world metres; tolerance (m) welds split normals for topology checks
    only. Requires manifold, consistently wound edges, no orphan, duplicate or sliver
    faces, a boundary witness for every source and void face, and the analytic union
    volume. Returns volume and count fields with status 'PASS'; raises ValueError on the
    first failure. Inputs are not mutated.
    """
    if not vertices or not faces or any(len(p)!=3 or any(not math.isfinite(v) for v in p) for p in vertices):
        raise ValueError('invalid mesh vertices')
    edges=Counter(); directed=Counter(); seen=set(); volume=0; used=set(); links=defaultdict(lambda:defaultdict(set))
    angle=boxes[0]['rotation_z'];ca,sa=math.cos(angle),math.sin(angle)
    local=[(ca*x+sa*y,-sa*x+ca*y,z) for x,y,z in vertices]
    planes=defaultdict(list)
    # Weld exported split normals by position for topology checks, never change the model.
    keys=[tuple(round(v/tolerance) for v in p) for p in vertices]
    for face in faces:
        if len(face)<3 or any(type(i)!=int or not 0<=i<len(vertices) for i in face):raise ValueError('invalid face indices')
        used.update(face)
        f=[keys[i] for i in face]
        for j,key in enumerate(f):
            a,b=f[j-1],f[(j+1)%len(f)]
            links[key][a].add(b);links[key][b].add(a)
        signature=tuple(sorted(f))
        if len(set(f))!=len(f) or signature in seen:raise ValueError('duplicate/degenerate faces')
        seen.add(signature)
        for a,b in zip(f,f[1:]+f[:1]):edges[tuple(sorted((a,b)))]+=1; directed[(a,b)]+=1
        a=vertices[face[0]]
        for j in range(1,len(face)-1):
            b,c=(vertices[face[k]] for k in (j,j+1))
            u=[b[k]-a[k] for k in range(3)]; v=[c[k]-a[k] for k in range(3)]
            n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            length=math.sqrt(sum(x*x for x in n))
            if length<=tolerance*tolerance:raise ValueError('sliver/zero-area face')
            tri=[local[face[k]] for k in (0,j,j+1)]
            # Plane indexing uses the source basis; supports arbitrary whole-layout rotation.
            local_n=(ca*n[0]+sa*n[1],-sa*n[0]+ca*n[1],n[2])
            axis=max(range(3),key=lambda k:abs(local_n[k]))
            planes[(axis,round(sum(p[axis] for p in tri)/3/tolerance))].append(tri)
            mid=[(a[k]+b[k]+c[k])/3 for k in range(3)]
            delta=max(tolerance*4,1e-7)
            inward=[mid[k]-n[k]/length*delta for k in range(3)]
            outward=[mid[k]+n[k]/length*delta for k in range(3)]
            if (not inside(inward,boxes,tolerance) or inside(inward,voids,-tolerance)
                    or (inside(outward,boxes,-tolerance) and not inside(outward,voids,tolerance))):
                raise ValueError('internal, extra or inverted boundary face')
            volume+=sum(a[k]*([b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0]][k]) for k in range(3))/6
    if any(n!=2 for n in edges.values()) or any(directed[(b,a)]!=n for (a,b),n in directed.items()):
        raise ValueError('open/nonmanifold or inconsistent boundary edges')
    if used!=set(range(len(vertices))):raise ValueError('orphan mesh vertices')
    for graph in links.values():
        visited=set();todo=[next(iter(graph))]
        while todo:
            v=todo.pop()
            if v in visited:continue
            visited.add(v);todo.extend(graph[v]-visited)
        if len(visited)!=len(graph) or any(len(neighbors)!=2 for neighbors in graph.values()):
            raise ValueError('nonmanifold vertex fan')
    # Witness every source member: a missing closed small component must not hide
    # below the aggregate volume tolerance. Aperture faces get reversed witnesses.
    for lo,hi in bounds_in_basis(boxes+list(voids)):
        for axis in range(3):
            tangents=[i for i in range(3) if i!=axis]
            for side in (lo[axis],hi[axis]):
                for fu in (.1,.5,.9):
                    for fv in (.1,.5,.9):
                        p=[(lo[i]+hi[i])/2 for i in range(3)];p[axis]=side
                        for i,fraction in zip(tangents,(fu,fv)):p[i]=lo[i]+fraction*(hi[i]-lo[i])
                        samples=[]
                        for sign in (-1,1):
                            q=list(p);q[axis]+=sign*max(4*tolerance,1e-7)
                            world=(ca*q[0]-sa*q[1],sa*q[0]+ca*q[1],q[2])
                            samples.append(inside(world,boxes) and not inside(world,voids))
                        if samples[0]==samples[1]:continue
                        found=False
                        for shift in (-1,0,1):
                            for tri in planes[(axis,round(side/tolerance)+shift)]:
                                crosses=[]
                                u,v=tangents
                                for a,b in zip(tri,tri[1:]+tri[:1]):
                                    crosses.append((b[u]-a[u])*(p[v]-a[v])-(b[v]-a[v])*(p[u]-a[u]))
                                eps=tolerance*max(math.dist(tri[0],tri[1]),math.dist(tri[1],tri[2]),math.dist(tri[2],tri[0]))*2
                                if min(crosses)>=-eps or max(crosses)<=eps:found=True;break
                            if found:break
                        if not found:raise ValueError('missing source/aperture boundary witness')
    expected=union_volume(boxes,voids)
    if abs(volume-expected)>max(tolerance*100,expected*1e-5):raise ValueError(f'occupied volume mismatch: {volume} != {expected}')
    return dict(volume_m3=volume,expected_union_m3=expected,faces=len(faces),vertices=len(vertices),status='PASS')
