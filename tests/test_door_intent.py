"""Room-based oracle for door swings, independent of generator/readback formulas."""
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/architectural-drawing-generation/scripts'
try:
    import ezdxf
except ImportError:
    if os.environ.get('GRIDLINE_REQUIRE_CAD_TESTS') == '1':
        raise
    ezdxf = None


def fixture(angle=0, reverse=False, hinge='start', room='BED'):
    data = json.loads((SCRIPTS.parent / 'references/example-house.building.json').read_text())
    data['grids'] = []
    data['walls'] = [dict(id='W', level='L00', type='internal', start=[0, 0], end=[4000, 0], thickness=200)]
    data['rooms'] = [dict(id='BED', name='Bedroom', level='L00', boundary=[[0, 100], [4000, 100], [4000, 3000], [0, 3000]]),
                     dict(id='HALL', name='Hall', level='L00', boundary=[[0, -100], [0, -3000], [4000, -3000], [4000, -100]])]
    data['openings'] = [dict(id='D', kind='door', wall='W', offset=1000, width=900, height=2100,
                             hinge=hinge, opens='into_room', receiving_room=room)]
    if reverse:
        data['walls'][0]['start'], data['walls'][0]['end'] = data['walls'][0]['end'], data['walls'][0]['start']
        data['openings'][0]['offset'] = 2100
    a = math.radians(angle)
    def rotate(p):
        x, y = p
        return [x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a)]
    for wall in data['walls']:
        for key in ('start', 'end'):
            wall[key] = rotate(wall[key])
    for r in data['rooms']:
        r['boundary'] = [rotate(p) for p in r['boundary']]
    return data


@unittest.skipIf(ezdxf is None, 'requires CAD environment')
class DoorIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(SCRIPTS))
        import aec_cad
        import blender_native
        cls.cad, cls.blender = aec_cad, blender_native
        cls.profile = aec_cad.load_profile('iso13567')

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(SCRIPTS))

    def draw(self, data):
        doc = self.cad.new_document(self.profile, 100)
        self.cad.draw_plan(doc.modelspace(), data, self.profile, 'L00', 100)
        return doc

    def test_room_oracle_all_directions_hinges_endpoint_orders_and_rotations(self):
        for angle in (0, 90, 180, 270, 15, 37):
            for reverse in (False, True):
                for hinge in ('start', 'end'):
                    for room in ('BED', 'HALL'):
                        with self.subTest(angle=angle, reverse=reverse, hinge=hinge, room=room):
                            data = fixture(angle, reverse, hinge, room)
                            self.assertEqual(self.cad.validate(data, self.profile), [])
                            doc = self.draw(data)
                            arc = next(iter(doc.modelspace().query('ARC')))
                            self.assertAlmostEqual((arc.dxf.end_angle-arc.dxf.start_angle)%360, 90)
                            self.assertAlmostEqual(arc.dxf.radius, 900)
                            leaf = next(e for e in doc.modelspace().query('LINE') if abs(e.dxf.start.distance(e.dxf.end)-900)<.01)
                            self.assertLess(leaf.dxf.start.distance(arc.dxf.center), .01)
                            # Inverse rotation reduces the oracle to the declared rectangular room.
                            a = math.radians(angle)
                            side = 1 if room == 'BED' else -1
                            cx, cy, _ = arc.dxf.center
                            self.assertAlmostEqual((-cx*math.sin(a)+cy*math.cos(a))*side, 100)
                            for point in arc.vertices([arc.dxf.start_angle + t*90 for t in (.1, .5, .9)]):
                                x, y = point.x*math.cos(a)+point.y*math.sin(a), -point.x*math.sin(a)+point.y*math.cos(a)
                                self.assertTrue(0 < x < 4000 and 100 < y*side < 3000)
                            errors, _ = self.cad.geometry_check(doc, self.cad.plan_requirements(data, self.profile, 'L00'), 'test', self.profile)
                            self.assertEqual(errors, [])
                            scene = self.blender.compile_scene(data)
                            door = next(e for e in scene['elements'] if e['id'] == 'D')
                            self.assertEqual(door['receiving_room'], room)

    def test_rotated_legacy_arc_is_a_quarter_turn(self):
        data = fixture(105)
        data['openings'][0].update(opens='right')
        arc = next(iter(self.draw(data).modelspace().query('ARC')))
        self.assertAlmostEqual((arc.dxf.end_angle-arc.dxf.start_angle)%360, 90)

    def test_missing_ambiguous_distant_wrong_level_or_too_small_room_rejected(self):
        for case in ('missing', 'unknown', 'ambiguous', 'distant', 'level', 'no_level', 'no_boundary', 'small', 'nonhinged'):
            data = fixture()
            if case == 'missing':
                data['openings'][0].pop('receiving_room')
            elif case == 'unknown':
                data['openings'][0]['receiving_room'] = 'UNKNOWN'
            elif case == 'ambiguous':
                data['rooms'][0]['boundary'] = [[0, -3000], [4000, -3000], [4000, 3000], [0, 3000]]
            elif case == 'distant':
                data['rooms'][0]['boundary'] = [[0, 2000], [4000, 2000], [4000, 3000], [0, 3000]]
            elif case == 'level':
                data['rooms'][0]['level'] = 'L99'
            elif case == 'no_level':
                data['rooms'][0].pop('level')
            elif case == 'no_boundary':
                data['rooms'][0].pop('boundary')
            elif case == 'small':
                data['rooms'][0]['boundary'] = [[0, 100], [4000, 100], [4000, 500], [0, 500]]
            else:
                data['openings'][0]['operation'] = 'sliding'
            with self.subTest(case=case):
                self.assertTrue(self.cad.validate(data, self.profile))
                with self.assertRaises(ValueError):
                    self.blender.compile_scene(data)

    def test_explicit_legacy_exception_is_preserved(self):
        data = fixture()
        data['openings'][0]['opens'] = 'right'
        self.assertEqual(self.cad.validate(data, self.profile), [])
        arc = next(iter(self.draw(data).modelspace().query('ARC')))
        self.assertLess(arc.dxf.center.y, 0)
        self.assertEqual(data['openings'][0]['opens'], 'right')

    def test_coordinated_build_schedule_and_readback_reject_changed_intent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, out = root / 'spec.json', root / 'out'
            data = fixture(15)
            path.write_text(json.dumps(data))
            command = [sys.executable, str(SCRIPTS / 'aec_cad.py')]
            built = subprocess.run(command + ['build', str(path), str(out)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            checked = subprocess.run(command + ['check', str(path), str(out)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            schedule = out / 'door-schedule.csv'
            self.assertIn('opens,receiving_room,resolved_opens', schedule.read_text())
            self.assertIn('into_room,BED,left', schedule.read_text())
            schedule.write_text(schedule.read_text().replace('into_room,BED,left', 'into_room,HALL,right'))
            checked = subprocess.run(command + ['check', str(path), str(out)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 1)
            self.assertIn('door-schedule.csv', checked.stdout)

    def test_pdf_omits_nonplot_room_edges_but_retains_door_leaf(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = fixture()
            path, out = root / 'spec.json', root / 'out'
            path.write_text(json.dumps(data))
            built = subprocess.run([sys.executable, str(SCRIPTS / 'aec_cad.py'), 'build', str(path), str(out)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            doc = ezdxf.readfile(out / 'A-101.dxf')
            vp = next(v for v in doc.layouts.get('A-101').query('VIEWPORT') if v.dxf.id != 1).dxf
            # Map the declared horizontal room edge and actual door leaf into paper points.
            def paper(x, y):
                return ((x-vp.view_center_point.x)/100*72/25.4+vp.center.x*72/25.4,
                        (y-vp.view_center_point.y)/100*72/25.4+vp.center.y*72/25.4)
            segments = []
            current = None
            def visit(op, args, cm, tm):
                nonlocal current
                if op not in (b'm', b'l'):
                    return
                x, y = map(float, args)
                point = (x*cm[0]+y*cm[2]+cm[4], x*cm[1]+y*cm[3]+cm[5])
                if op == b'l' and current is not None:
                    segments.append((current, point))
                current = point
            PdfReader(out / 'A-101.pdf').pages[0].extract_text(visitor_operand_before=visit)
            def has(a, b):
                return any((math.dist(a,c)<.05 and math.dist(b,d)<.05) or
                           (math.dist(a,d)<.05 and math.dist(b,c)<.05) for c,d in segments)
            self.assertFalse(has(paper(0,100), paper(4000,100)), 'nonplot room boundary crosses door opening')
            self.assertTrue(has(paper(1000,100), paper(1000,1000)), 'door leaf must remain visible')
            boundary_layer = self.profile['layers']['room_boundary']['name']
            self.assertEqual(len([e for e in doc.modelspace().query('LWPOLYLINE') if e.dxf.layer == boundary_layer]), 2)

    def test_explicit_sides_validate_supplied_room_without_flipping_exception(self):
        for side in ('left', 'right'):
            for fault in ('unknown', 'wrong_level', 'nonadjacent', 'ambiguous'):
                data = fixture()
                data['openings'][0]['opens'] = side
                if fault == 'unknown':
                    data['openings'][0]['receiving_room'] = 'MISSING'
                elif fault == 'wrong_level':
                    data['rooms'][0]['level'] = 'OTHER'
                elif fault == 'nonadjacent':
                    data['rooms'][0]['boundary'] = [[0,2000],[4000,2000],[4000,3000],[0,3000]]
                else:
                    data['rooms'][0]['boundary'] = [[0,-3000],[4000,-3000],[4000,3000],[0,3000]]
                with self.subTest(side=side, fault=fault):
                    self.assertTrue(self.cad.validate(data, self.profile))
                    with self.assertRaises(ValueError):
                        self.blender.compile_scene(data)
        data = fixture()
        data['openings'][0].update(opens='right')
        self.assertEqual(self.cad.validate(data, self.profile), [])
        data['openings'][0].pop('receiving_room')
        data['rooms'] = []
        self.assertEqual(self.cad.validate(data, self.profile), [])
