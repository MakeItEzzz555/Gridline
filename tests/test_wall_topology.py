"""Measured topology regressions; oracle reads faces, never generator counts."""
import copy
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/scripts'))
from wall_topology import union_boxes, geometry_entries
from mesh_qa import check_surface, union_volume


def box(name, c, d, angle=0):
    return dict(name=name,gridline_id=name,kind='wall',host='',center_m=c,dimensions_m=d,
                rotation_z=angle,metadata={'level':'L0'})


class WallTopologyTests(unittest.TestCase):
    def check(self, boxes, volume):
        mesh=union_boxes(boxes,'joined')
        report=check_surface(mesh['vertices'],mesh['faces'],boxes)
        self.assertAlmostEqual(report['volume_m3'],volume,places=6)
        self.assertAlmostEqual(union_volume(boxes),volume,places=6)
        return mesh

    def test_l_t_cross_unequal_and_levels(self):
        a=box('a',[2,0,1.5],[4,.2,3])
        for x,y,length,overlap in [(0,2,4,.01),(2,2,4,.02),(2,0,4,.04)]:
            b=box('b',[x,y,1.5],[.2,length,3])
            self.check([a,b],4.8-overlap*3)
        self.check([a,box('b',[2,2,1.5],[.4,4,3])],7.2-.04*3)
        self.check([a,box('upper',[2,0,4.5],[4,.2,3])],4.8)

    def test_rotated_translated_and_reversed_order(self):
        a=box('a',[2,0,1.5],[4,.2,3])
        b=box('b',[0,2,1.5],[4,.2,3],math.pi/2)
        angle=.37
        for entry in (a,b):
            x,y,z=entry['center_m']
            entry['center_m']=[10+math.cos(angle)*x-math.sin(angle)*y,-7+math.sin(angle)*x+math.cos(angle)*y,z]
            entry['rotation_z']+=angle
        self.check([a,b],4.77)
        self.check([b,a],4.77)

    def test_offset_joints_no_gap_snapping(self):
        a=box('a',[2,0,1.5],[4,.2,3])
        for gap in (-.00005,.00005):
            b=box('b',[4.1+gap,0,1.5],[.2,4,3])
            self.check([a,b],4.8+min(0,gap)*.2*3)

    def test_opening_voids_sill_head_adjacent_and_full_height(self):
        for sill,head in [(0,2.3),(.9,2.4),(0,3)]:
            entries=[box('left',[.5,0,1.5],[1,.2,3]),box('right',[3,0,1.5],[2,.2,3])]
            if sill: entries.append(box('sill',[1.5,0,sill/2],[1,.2,sill]))
            if head<3: entries.append(box('head',[1.5,0,(head+3)/2],[1,.2,3-head]))
            self.check(entries,2.4-(head-sill)*.2)
        self.check([box('left',[.5,0,1.5],[1,.2,3]),box('pier',[2.5,0,1.5],[1,.2,3]),box('right',[4.5,0,1.5],[1,.2,3]),box('head',[2.5,0,2.75],[5,.2,.5])],1.8+.2)

    def test_negative_surface_mutations(self):
        entries=[box('a',[2,0,1.5],[4,.2,3])]
        mesh=self.check(entries,2.4)
        for fault in ('duplicate','missing','normal','lintel','phantom','orphan'):
            v,f=copy.deepcopy(mesh['vertices']),copy.deepcopy(mesh['faces'])
            if fault=='duplicate': f.append(f[0])
            if fault=='missing': f.pop()
            if fault=='normal': f[0].reverse()
            if fault=='orphan': v.append([999,999,999])
            if fault in ('lintel','phantom'): v[0][0]+=.05
            with self.assertRaises(ValueError,msg=fault):check_surface(v,f,entries)

    def test_unsupported_malicious_and_oblique_fail(self):
        a=box('a',[0,0,0],[4,.2,3])
        for change in (dict(rotation_z=.2),dict(center_m=[float('nan'),0,0]),dict(dimensions_m=[-1,1,1])):
            b={**a,**change,'name':'b'}
            with self.assertRaises(ValueError):union_boxes([a,b],'bad')


class PublishedTopologyTests(unittest.TestCase):
    def test_measured_villa_walls_and_all_43_apertures(self):
        import json
        from blender_native import compile_scene
        path=Path(__file__).parent/'fixtures/villa-topology.building.json'
        scene=compile_scene(json.loads(path.read_text()))
        entries=geometry_entries(scene)
        walls=[e for e in entries if e['kind']=='wall']
        self.assertEqual(len(walls),2)
        self.assertEqual(len([e for e in entries if e['host']]),43)
        self.assertEqual(len({i for e in walls for i in e['source_ids']}),27)
        for e in walls:
            report=check_surface(e['vertices'],e['faces'],e['source_boxes'],voids=e['void_boxes'])
            self.assertGreater(report['volume_m3'],50)
        # Original fragment surfaces fail the independent volume/boundary oracle.
        a=box('a',[2,0,1.5],[4,.2,3]);b=box('b',[0,2,1.5],[.2,4,3])
        ma=union_boxes([a],'a');mb=union_boxes([b],'b');n=len(ma['vertices'])
        with self.assertRaisesRegex(ValueError,'internal|volume'):
            check_surface(ma['vertices']+mb['vertices'],ma['faces']+[[i+n for i in f] for f in mb['faces']],[a,b])

    def test_roof_guard_overlaps_and_thin_roles(self):
        import json
        path=Path(__file__).parent/'fixtures/villa-topology-members.json'
        scene=json.loads(path.read_text())
        entries=geometry_entries(scene)
        self.assertEqual(len(entries),3)  # roof slab, parapet ring, balcony guards
        for e in entries:
            if 'vertices' in e:
                check_surface(e['vertices'],e['faces'],e['source_boxes'])
                removed=sum(math.prod(b['dimensions_m']) for b in e['source_boxes'])-union_volume(e['source_boxes'])
                self.assertAlmostEqual(removed,.08 if e['kind']=='parapet' else .001375,places=8)
        for kind,role in [('helper','helper'),('railing','orphan'),('unknown','wall')]:
            bad=box('phantom',[0,0,0],[.001,1,1]);bad.update(kind=kind,role=role)
            with self.assertRaisesRegex(ValueError,'role'):geometry_entries(dict(boxes=[bad]))

    def test_declared_opening_subtracts_crossing_partition(self):
        wall=box('host',[2,0,1.5],[4,.2,3])
        other=box('partition',[2,1,1.5],[.2,2,3])
        aperture=box('opening',[2,0,1.5],[1,.035,1.8]);aperture.update(kind='glass',host='host')
        entries=geometry_entries(dict(boxes=[wall,other,aperture]))
        mesh=next(e for e in entries if 'vertices' in e)
        check_surface(mesh['vertices'],mesh['faces'],mesh['source_boxes'],voids=mesh['void_boxes'])
        # Omitting void subtraction must fail even though exterior bounds match.
        bad=union_boxes([wall,other],'bad')
        with self.assertRaisesRegex(ValueError,'internal|volume'):
            check_surface(bad['vertices'],bad['faces'],[wall,other],voids=mesh['void_boxes'])

    def test_resource_budget_and_intentional_joint_groups(self):
        entries=[box(str(i),[i*.31,i*.27,i*.23],[.2,.2,.2]) for i in range(40)]
        with self.assertRaisesRegex(ValueError,'budget'):union_boxes(entries,'large')
        a=box('a',[0,0,1.5],[4,.2,3]);b=box('b',[0,0,4.5],[4,.2,3])
        b['metadata']['level']='L1'
        self.assertEqual(len(geometry_entries(dict(boxes=[a,b]))),2)
        b['metadata']['level']='L0';b['metadata']['joint_group']='deliberate'
        self.assertEqual(len(geometry_entries(dict(boxes=[a,b]))),2)


class OpeningCompilerTests(unittest.TestCase):
    def test_door_window_wide_adjacent_near_corner_full_height_rotated_two_levels(self):
        import json
        from blender_native import compile_scene
        template=json.loads((Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/references/example-house.building.json').read_text())
        cases=[[(0,1000,2300,0,'door')],[(1000,3000,1500,900,'window')],
               [(500,1000,1500,900,'window'),(2000,1500,1500,900,'window')],
               [(0,2000,3000,0,'window')],[(500,1000,2300,0,'door'),(2500,2000,1500,900,'window')],
               [(1,1500,1500,900,'window')]]
        for openings in cases:
            model=copy.deepcopy(template);model['rooms']=[];model['sheets']=[];model['grids']=[];model['walls']=[];model['openings']=[]
            model['levels']=[dict(id='L0',name='ground',elevation=0,height=3000),dict(id='L1',name='upper',elevation=3300,height=3000)]
            for level in model['levels']:
                ident='wall'+level['id'];angle=.37
                model['walls'].append(dict(id=ident,level=level['id'],type='external',start=[1000,2000],end=[1000+6000*math.cos(angle),2000+6000*math.sin(angle)],thickness=200))
                for i,(offset,width,height,sill,kind) in enumerate(openings):
                    op=dict(id=level['id']+str(i),wall=ident,kind=kind,offset=offset,width=width,height=height,sill=sill,type='test')
                    if kind=='door':op.update(hinge='start',opens='left')
                    model['openings'].append(op)
            scene=compile_scene(model)
            for e in geometry_entries(scene):
                if 'vertices' in e:check_surface(e['vertices'],e['faces'],e['source_boxes'],tolerance=1e-6,voids=e['void_boxes'])


class BoundaryCompletenessTests(unittest.TestCase):
    def test_small_missing_closed_member_below_volume_threshold_is_rejected(self):
        big=box('large',[2,0,1.5],[4,.2,3]);small=box('small',[9,0,1],[.01,.01,.01])
        mesh=union_boxes([big],'only-large')
        with self.assertRaisesRegex(ValueError,'missing source'):
            check_surface(mesh['vertices'],mesh['faces'],[big,small],tolerance=1e-5)


class PerLevelApertureTests(unittest.TestCase):
    def test_different_level_basis_does_not_receive_foreign_apertures(self):
        a=box('L0',[0,0,1.5],[4,.2,3],.37)
        b=box('L1',[8,8,4.8],[4,.2,3],1.0)
        a['metadata']['level']='L0';b['metadata']['level']='L1'
        door=box('door',[8,8,4.45],[1,.035,2.3],1.0)
        door.update(kind='door',host='L1')
        walls=[e for e in geometry_entries(dict(boxes=[a,b,door])) if e['kind']=='wall']
        self.assertEqual([len(e['void_boxes']) for e in walls],[0,1])
        for e,volume in zip(walls,(2.4,1.94)):
            report=check_surface(e['vertices'],e['faces'],e['source_boxes'],voids=e['void_boxes'])
            self.assertAlmostEqual(report['volume_m3'],volume,places=6)
