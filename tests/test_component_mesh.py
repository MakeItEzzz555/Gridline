import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/scripts'))
from component_mesh import compare_triangles

T=[[[0,0,0,0,0,0,0,1],[1,0,0,1,0,0,0,1],[0,1,0,0,1,0,0,1]]]


class ComponentMeshTests(unittest.TestCase):
    def test_float32_jitter_and_cyclic_vertex_order_are_accepted(self):
        actual=copy.deepcopy(T);actual[0]=actual[0][1:]+actual[0][:1]
        actual[0][0][0]+=1e-6
        self.assertEqual(compare_triangles(T,actual)['state'],'PASS')

    def test_missing_duplicated_moved_uv_normal_and_reversed_faces_reject(self):
        changed=[]
        for index in (0,3,7):
            value=copy.deepcopy(T);value[0][0][index]+=.01;changed.append(value)
        changed.extend([[],T+T,[list(reversed(T[0]))]])
        for actual in changed:
            with self.subTest(actual=actual),self.assertRaises(ValueError):compare_triangles(T,actual)

    def test_multiplicity_cannot_be_hidden_by_total_count(self):
        other=copy.deepcopy(T[0])
        for point in other:point[0]+=2
        with self.assertRaises(ValueError):compare_triangles([T[0],other],[T[0],T[0]])


if __name__=='__main__':unittest.main()
