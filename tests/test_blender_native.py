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

    def test_missing_wall_endpoints_block_before_publishing(self):
        import contextlib
        import io
        import sys
        import types
        from unittest.mock import patch
        for key in ('start','end'):
            model=copy.deepcopy(self.building)
            model['walls'][0].pop(key)
            with self.subTest(endpoint=key):
                with self.assertRaisesRegex(ValueError,'start and end are required'):
                    bridge.compile_scene(model)
                with tempfile.TemporaryDirectory() as tmp:
                    root=Path(tmp).resolve()
                    executable=root/'Blender';executable.write_text('version probe is mocked')
                    source=root/'source.json';source.write_text(json.dumps(model))
                    output=root/'new-output';stderr=io.StringIO()
                    argv=['blender_native.py','--blender',str(executable),'build',str(source),str(output)]
                    with patch.object(sys,'argv',argv), patch.object(bridge.subprocess,'run',return_value=types.SimpleNamespace(stdout='Blender 5.2.3 LTS\n')) as run, contextlib.redirect_stderr(stderr):
                        self.assertEqual(bridge.main(),1)
                    self.assertIn('BLOCKED:',stderr.getvalue())
                    self.assertNotIn('Traceback',stderr.getvalue())
                    self.assertFalse(output.exists())
                    self.assertEqual(run.call_count,1)  # version only; no build process

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
