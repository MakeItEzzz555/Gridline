"""Orientation-preserving, multiplicity-aware triangle/UV roundtrip comparison."""
from collections import defaultdict
from itertools import product
import math


def compare_triangles(expected, actual, tolerance=1e-5, normal_tolerance=5e-5):
    if len(expected) != len(actual):
        raise ValueError('triangle inventory changed')
    buckets=defaultdict(list)
    def cell(triangle):
        return tuple(math.floor(sum(p[i] for p in triangle)/3/tolerance) for i in range(3))
    for index,triangle in enumerate(expected):
        if len(triangle)!=3 or any(len(p)!=8 or any(not math.isfinite(v) for v in p) for p in triangle):
            raise ValueError('invalid reference triangle/UV')
        buckets[cell(triangle)].append(index)
    remaining=set(range(len(expected)))
    for triangle in actual:
        if len(triangle)!=3 or any(len(p)!=8 or any(not math.isfinite(v) for v in p) for p in triangle):
            raise ValueError('invalid roundtrip triangle/UV')
        key=cell(triangle);found=None
        for offset in product((-1,0,1),repeat=3):
            for index in buckets.get(tuple(key[i]+offset[i] for i in range(3)),()):
                if index not in remaining:continue
                wanted=expected[index]
                if any(all(abs(triangle[i][k]-wanted[(i+shift)%3][k])<=(tolerance if k<5 else normal_tolerance) for i in range(3) for k in range(8)) for shift in range(3)):
                    found=index;break
            if found is not None:break
        if found is None:
            raise ValueError('changed vertex, UV, normal or face winding')
        remaining.remove(found)
    return {'state':'PASS','triangles':len(expected),'position_tolerance_m':tolerance,'uv_tolerance':tolerance,'normal_channel_tolerance':normal_tolerance}
