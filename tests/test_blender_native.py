"""Blender bridge: bounded native-model preprocessing (works without Blender in CI)."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"skills"/"architectural-drawing-generation"/"scripts"/"blender_native.py"
spec=importlib.util.spec_from_file_location("blender_native",MODULE)
bridge=importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)
FIXTURE=ROOT/"skills"/"architectural-drawing-generation"/"references"/"example-house.building.json"


class BlenderNativeTests(unittest.TestCase):
    def setUp(self):
        self.building=json.loads(FIXTURE.read_text())

    def test_sample_model_preserves_stable_ids_and_millimeter_units(self):
        scene=bridge.compile_scene(copy.deepcopy(self.building))
        self.assertEqual(scene["output_units"],"m")
        self.assertEqual(len(scene["elements"]),17)
        self.assertEqual(len(scene["boxes"]),42)
        for box in scene["boxes"]:
            self.assertFalse(set(box["metadata"]) & {"id", "kind", "host", "source_units", "schema"})
        ids={x["id"] for x in scene["elements"]}
        self.assertEqual(len(ids),17)
        self.assertEqual(ids,{x["gridline_id"] for x in scene["boxes"]})
        self.assertTrue(any("Image-reference similarity" in x for x in scene["unverified"]))

    def test_supported_wall_segments_have_real_opening_gap(self):
        scene=bridge.compile_scene(copy.deepcopy(self.building))
        # W01 on E1 spans 4200..6200 mm, sill 900, top 2400.
        # No fragment may fill the window aperture, even if tags exist.
        for box in scene["boxes"]:
            if box["kind"]!="wall" or box["gridline_id"]!="E1":
                continue
            x=box["center_m"][0]
            length=box["dimensions_m"][0]
            low=box["center_m"][2]-box["dimensions_m"][2]/2
            high=box["center_m"][2]+box["dimensions_m"][2]/2
            overlaps_x=x+length/2>4.2+1e-5 and x-length/2<6.2-1e-5
            overlaps_z=high>0.9+1e-5 and low<2.4-1e-5
            self.assertFalse(overlaps_x and overlaps_z,box["name"])

    def test_missing_units_and_floor_heights_block_not_default(self):
        for alteration in (
            lambda x:x.pop("units"),
            lambda x:x.__setitem__("units","m"),
            lambda x:x["levels"][0].pop("height"),
            lambda x:x["levels"][0].__setitem__("height",float("nan")),
        ):
            model=copy.deepcopy(self.building)
            alteration(model)
            with self.assertRaises(ValueError):
                bridge.compile_scene(model)

    def test_opening_outside_host_and_host_overlap_fail(self):
        model=copy.deepcopy(self.building)
        model["openings"][0]["width"]=100000
        with self.assertRaisesRegex(ValueError,"does not fit"):
            bridge.compile_scene(model)
        model=copy.deepcopy(self.building)
        model["openings"][4]["offset"]=model["openings"][0]["offset"]
        with self.assertRaisesRegex(ValueError,"overlapping"):
            bridge.compile_scene(model)

    def test_bad_ids_and_invalid_coordinates_fail(self):
        model=copy.deepcopy(self.building)
        model["openings"][0]["id"]="E1"
        with self.assertRaisesRegex(ValueError,"duplicate"):
            bridge.compile_scene(model)
        model=copy.deepcopy(self.building)
        model["walls"][0]["start"][0]="1000"
        with self.assertRaises(ValueError):
            bridge.compile_scene(model)
        model=copy.deepcopy(self.building)
        model["walls"][0]["start"][0]=10**12
        with self.assertRaises(ValueError):
            bridge.compile_scene(model)

    def test_source_json_constant_nan_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.json"
            p.write_text('{"units":"mm","floors":NaN}')
            with self.assertRaises(ValueError):
                bridge.load_spec(p)

    def test_explicit_version_and_source_data_not_modified(self):
        model=copy.deepcopy(self.building)
        original=json.dumps(model,sort_keys=True)
        bridge.compile_scene(model)
        # Current compiler populates absent OPTIONAL arrays as an internal normalization;
        # the user file remains untouched because only an in-memory copy is loaded.
        self.assertEqual(original,json.dumps(model,sort_keys=True))


if __name__=="__main__":
    unittest.main()


class BlenderHardeningTests(unittest.TestCase):
    def test_source_rejects_oversize_symlinks_and_fifo(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(ValueError):
                bridge.source_bytes(Path('/'))
            p = root / 'source.json'
            p.write_bytes(b'x' * (bridge.MAX_SPEC_BYTES + 1))
            with self.assertRaisesRegex(ValueError, 'oversized'):
                bridge.source_bytes(p)
            (root / 'link.json').symlink_to(p)
            with self.assertRaises(OSError):
                bridge.source_bytes(root / 'link.json')
            os.mkfifo(root / 'pipe')
            with self.assertRaisesRegex(ValueError, 'regular'):
                bridge.source_bytes(root / 'pipe')

    def test_output_directory_swap_cannot_redirect_artifacts(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            stage, out, moved, foreign = [root / x for x in ('stage', 'out', 'moved', 'foreign')]
            stage.mkdir()
            foreign.mkdir()
            for name in ('model.blend', 'model.glb', 'scene.json', 'verification.json'):
                (stage / name).write_bytes(b'new data')
            real_open = os.open
            def swap(path, *args, **kwargs):
                fd = real_open(path, *args, **kwargs)
                if path == out.name and 'dir_fd' in kwargs:
                    out.rename(moved)
                    out.symlink_to(foreign, target_is_directory=True)
                return fd
            with patch.object(bridge.os, 'open', side_effect=swap):
                with self.assertRaisesRegex(ValueError, 'directory changed'):
                    bridge.publish(stage, out, {'status': 'test'})
            self.assertEqual(list(foreign.iterdir()), [])
            self.assertTrue((moved / 'model.blend').exists())

    def worker(self):
        import types
        from unittest.mock import patch
        path = MODULE.with_name('blender_native_worker.py')
        info = importlib.util.spec_from_file_location('worker_for_checks', path)
        worker = importlib.util.module_from_spec(info)
        with patch.dict('sys.modules', {'bpy': types.SimpleNamespace(),
                                        'mathutils': types.SimpleNamespace(Vector=None)}):
            info.loader.exec_module(worker)
        return worker

    def object(self, angle=0, drift=0):
        import math
        import types
        entry = {'name': 'wall_w1', 'kind': 'wall', 'gridline_id': 'w1', 'host': '',
                 'center_m': [0, 0, 0], 'dimensions_m': [4, .2, 3], 'rotation_z': 0}
        class Matrix:
            def __matmul__(self, point):
                x, y, z = point
                return (math.cos(angle)*x-math.sin(angle)*y+drift,
                        math.sin(angle)*x+math.cos(angle)*y, z)
        class Object(dict):
            pass
        obj = Object(gridline_id='w1', gridline_kind='wall', gridline_host='',
                     gridline_source_units='mm', gridline_schema='gridline-blender-scene.v0')
        obj.name = entry['name']
        obj.matrix_world = Matrix()
        obj.data = types.SimpleNamespace(
            vertices=[types.SimpleNamespace(co=(x,y,z)) for x in (-2,2) for y in (-.1,.1) for z in (-1.5,1.5)],
            materials=[types.SimpleNamespace(name='Gridline Wall')],
            polygons=[types.SimpleNamespace(material_index=0,vertices=f) for f in
                      [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]]])
        return obj, entry

    def test_world_rotation_parent_drift_and_nonfinite_vertices_fail(self):
        import math
        worker = self.worker()
        obj, entry = self.object()
        worker.verify_object(obj, entry, .001)
        for angle, drift in ((math.pi/2, 0), (0, 1)):
            obj, entry = self.object(angle, drift)
            with self.assertRaisesRegex(ValueError, 'world geometry'):
                worker.verify_object(obj, entry, .001)
        obj, entry = self.object()
        obj.data.vertices[0].co = (float('nan'), 0, 0)
        with self.assertRaisesRegex(ValueError, 'invalid mesh'):
            worker.verify_object(obj, entry, .001)

    def test_identity_host_kind_and_missing_material_fail(self):
        worker = self.worker()
        for attribute,value in [('modifiers',[object()]),('constraints',[object()]),('hide_render',True),('hide_viewport',True)]:
            obj,entry=self.object();setattr(obj,attribute,value)
            with self.assertRaisesRegex(ValueError,'unsupported'):worker.verify_object(obj,entry,.001)
        obj,entry=self.object();entry['role']='wall';obj['gridline_role']='furniture'
        with self.assertRaisesRegex(ValueError,'role mapping'):worker.verify_object(obj,entry,.001)
        for key in ('gridline_id', 'gridline_host', 'gridline_kind', 'gridline_source_units', 'gridline_schema'):
            obj, entry = self.object()
            del obj[key]
            with self.assertRaisesRegex(ValueError, 'metadata'):
                worker.verify_object(obj, entry, .001)
        obj, entry = self.object()
        obj.data.materials = []
        with self.assertRaisesRegex(ValueError, 'material'):
            worker.verify_object(obj, entry, .001)
