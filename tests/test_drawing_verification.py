"""Corrupt output bytes while preserving source, labels and schedules."""
import hashlib
import csv
import contextlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/architectural-drawing-generation"
SCRIPT = SKILL / "scripts/aec_cad.py"
EXAMPLE = SKILL / "references/example-house.building.json"
module_spec = importlib.util.spec_from_file_location("aec_readback_test", SKILL / "scripts/aec_readback.py")
readback = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(readback)
try:
    import ezdxf
    import matplotlib
    import pypdf
except ImportError:
    if os.environ.get("GRIDLINE_REQUIRE_CAD_TESTS") == "1":
        raise
    ezdxf = None


def run(command, spec, out):
    return subprocess.run([sys.executable, str(SCRIPT), command, str(spec), str(out)],
                          capture_output=True, text=True)


@unittest.skipIf(ezdxf is None, "requires ezdxf, matplotlib and pypdf")
class DrawingVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden_tmp = tempfile.TemporaryDirectory()
        cls.golden = Path(cls.golden_tmp.name) / "golden"
        result = run("build", EXAMPLE, cls.golden)
        assert result.returncode == 0, result.stdout + result.stderr
        cls.profile = json.loads((SKILL / "references/standards/iso13567.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.golden_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "out"
        shutil.copytree(self.golden, self.out)

    def report(self):
        return json.loads((self.out / "check-report.json").read_text())

    def test_overall_paperspace_viewport_layer_zero_and_native_audit_regression(self):
        for number in ('A-101', 'A-102'):
            doc = ezdxf.readfile(self.out / f'{number}.dxf')
            main = [v for v in doc.layouts.get(number).query('VIEWPORT') if v.dxf.id == 1]
            self.assertEqual(len(main), 1)
            self.assertEqual(main[0].dxf.layer, '0')
        main[0].dxf.layer = 'VIEWPORTS'
        doc.saveas(self.out / 'A-102.dxf')
        checked = run('check', EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 1)
        self.assertIn('overall paper-space viewport must be on layer 0', checked.stdout)

    def test_oversized_csv_field_retains_failure_receipt(self):
        for name in ("room-schedule.csv", "sheet-register.csv"):
            with self.subTest(schedule=name):
                path = self.out / name
                original = path.read_bytes()
                path.write_text("id\n" + "x" * (csv.field_size_limit() + 1) + "\n")
                checked = run("check", EXAMPLE, self.out)
                self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
                self.assertNotIn("Traceback", checked.stderr)
                report = self.report()
                self.assertEqual(report["status"], "FAIL")
                self.assertIn("field larger than field limit", " ".join(report["errors"]))
                self.assertEqual(report["output_hashes"][name], hashlib.sha256(path.read_bytes()).hexdigest())
                self.assertTrue((self.out / "receipts" / f"{report['receipt_id']}.json").exists())
                path.write_bytes(original)

    def test_build_missing_required_pdf_returns_failure(self):
        from unittest import mock
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(sys.path.remove, str(SCRIPT.parent))
        import aec_cad
        for pdf_results in ((False, False), (True, False)):
            with self.subTest(pdf_results=pdf_results), \
                    mock.patch.object(aec_cad, "write_pdf", side_effect=pdf_results), \
                    contextlib.redirect_stdout(io.StringIO()) as stdout, \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = aec_cad.build(EXAMPLE, self.root / "incomplete", None)
                self.assertEqual(result, 1, stdout.getvalue() + stderr.getvalue())
                self.assertIn("required PDF", stderr.getvalue())
                self.assertNotIn("BUILT", stdout.getvalue())

    def test_missing_moved_resized_duplicated_geometry_fails_with_unchanged_labels(self):
        for layer_key, entity_type in (("opening", "LINE"), ("wall_external", "LWPOLYLINE"),
                                       ("room_boundary", "LWPOLYLINE")):
            for mutation in ("delete", "move", "resize", "duplicate"):
                with self.subTest(layer=layer_key, mutation=mutation):
                    path = self.out / "A-101.dxf"
                    path.write_bytes((self.golden / path.name).read_bytes())
                    doc = ezdxf.readfile(path)
                    msp = doc.modelspace()
                    entity = next(e for e in msp.query(entity_type)
                                  if e.dxf.layer == self.profile["layers"][layer_key]["name"])
                    labels = [(e.dxf.layer, e.dxf.text) for e in msp.query("TEXT")]
                    schedules = {p.name: p.read_bytes() for p in self.out.glob("*.csv")}
                    if mutation == "delete":
                        msp.delete_entity(entity)
                    elif mutation == "duplicate":
                        msp.add_entity(entity.copy())
                    elif mutation == "move":
                        entity.translate(125, 250, 0)
                    elif entity_type == "LINE":
                        entity.dxf.end = entity.dxf.end + (100, 0, 0)
                    else:
                        pts = list(entity.get_points())
                        pts[0] = (pts[0][0] + 200, *pts[0][1:])
                        entity.set_points(pts)
                    doc.saveas(path)
                    self.assertEqual(labels, [(e.dxf.layer, e.dxf.text) for e in msp.query("TEXT")])
                    self.assertEqual(schedules, {p.name: p.read_bytes() for p in self.out.glob("*.csv")})
                    checked = run("check", EXAMPLE, self.out)
                    self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
                    self.assertIn("A-101", checked.stdout)
                    self.assertIn("geometry", checked.stdout.lower())

    def test_invalid_dimensions_and_shapes_fail_without_traceback(self):
        cases = [
            ("units absent", lambda d: d.pop("units")),
            ("units ambiguous", lambda d: d.update(units="m")),
            ("negative level", lambda d: d["levels"][0].update(height=-1)),
            ("missing elevation", lambda d: d["levels"][0].pop("elevation")),
            ("missing level id", lambda d: d["levels"][0].pop("id")),
            ("phantom level", lambda d: d["walls"][0].update(level="L99")),
            ("NaN", lambda d: d["walls"][0]["start"].__setitem__(0, float("nan"))),
            ("Infinity", lambda d: d["openings"][0].update(width=float("inf"))),
            ("boolean size", lambda d: d["walls"][0].update(thickness=True)),
            ("text size", lambda d: d["walls"][0].update(thickness="300")),
            ("bad point", lambda d: d["walls"][0].update(start=[0])),
            ("window above level", lambda d: d["openings"][4].update(sill=2500)),
            ("missing sill", lambda d: d["openings"][4].pop("sill")),
            ("negative sill", lambda d: d["openings"][4].update(sill=-1)),
            ("door above level", lambda d: d["openings"][0].update(height=3100)),
            ("duplicate id", lambda d: d["openings"][1].update(id="D01")),
            ("bad collection", lambda d: d.update(walls={})),
            ("bad project", lambda d: d.update(project=[])),
            ("invalid checker", lambda d: d["project"].update(checked_by=False)),
            ("invalid room name", lambda d: d["rooms"][0].update(name=[])),
            ("bad sheet number", lambda d: d["sheets"][0].update(number="../A-101")),
            ("bad reference", lambda d: d["openings"][0].update(wall=[])),
        ]
        for name, change in cases:
            with self.subTest(name=name):
                data = json.loads(EXAMPLE.read_text())
                change(data)
                spec = self.root / "invalid.json"
                spec.write_text(json.dumps(data))
                checked = run("check", spec, self.out)
                self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
                self.assertNotIn("Traceback", checked.stderr)
                self.assertEqual(self.report()["status"], "FAIL")
                self.assertEqual(self.report()["coverage"]["dxf_geometry"]["status"], "NOT_RUN")

    def test_pdf_required_and_independently_measured(self):
        for mutation in ("missing", "malformed", "blank", "wrong_sheet", "wrong_scale"):
            with self.subTest(mutation=mutation):
                path = self.out / "A-101.pdf"
                path.write_bytes((self.golden / path.name).read_bytes())
                if mutation == "missing":
                    path.unlink()
                elif mutation == "malformed":
                    path.write_bytes(b"%PDF-1.4\nnot a document")
                elif mutation == "wrong_sheet":
                    path.write_bytes((self.golden / "A-102.pdf").read_bytes())
                else:
                    writer = pypdf.PdfWriter()
                    if mutation == "blank":
                        writer.add_blank_page(width=841 / 25.4 * 72, height=594 / 25.4 * 72)
                    else:
                        reader = pypdf.PdfReader(path)
                        page = writer.add_page(reader.pages[0])
                        page.add_transformation(pypdf.Transformation().scale(0.9))
                        writer.add_metadata(reader.metadata)
                    with path.open("wb") as fh:
                        writer.write(fh)
                checked = run("check", EXAMPLE, self.out)
                self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
                self.assertIn("A-101.pdf", checked.stdout)

    def test_receipt_hashes_coverage_and_source_inputs(self):
        checked = run("check", EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        report = self.report()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["input_hashes"][str(EXAMPLE)], hashlib.sha256(EXAMPLE.read_bytes()).hexdigest())
        for name, digest in report["output_hashes"].items():
            self.assertEqual(digest, hashlib.sha256((self.out / name).read_bytes()).hexdigest())
        self.assertEqual(report["validator"]["files"]["aec_cad.py"], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(len(report["code_sha"]), 40)
        self.assertEqual(report["coverage"]["dxf_geometry"]["status"], "PASS")
        self.assertFalse(report["native_host_verified"])
        self.assertEqual(report["coverage"]["autocad_native"]["status"], "NOT_RUN")
        self.assertEqual(report["coverage"]["semantic_3d"]["status"], "NOT_RUN")
        self.assertTrue(report["unverified_items"])
        self.assertTrue((self.out / "receipts" / f"{report['receipt_id']}.json").exists())

    def test_hand_authored_geometry_oracle_and_missing_door_arc(self):
        spec = {"walls": [{"id": "wall", "level": "L", "type": "external", "start": [0, 0],
                           "end": [3000, 0], "thickness": 200}],
                "openings": [{"id": "door", "wall": "wall", "kind": "door", "offset": 500,
                              "width": 800, "hinge": "start", "opens": "left"}], "rooms": []}
        doc = ezdxf.new()
        layers = {k: v["name"] for k, v in self.profile["layers"].items()}
        for a, b in ((0, 500), (1300, 3000)):
            doc.modelspace().add_lwpolyline([(a, -100), (b, -100), (b, 100), (a, 100)],
                                            close=True, dxfattribs={"layer": layers["wall_external"]})
        for x in (500, 1300):
            doc.modelspace().add_line((x, -100), (x, 100), dxfattribs={"layer": layers["opening"]})
        doc.modelspace().add_line((500, 100), (500, 900), dxfattribs={"layer": layers["opening"]})
        arc = doc.modelspace().add_arc((500, 100), 800, 0, 90, dxfattribs={"layer": layers["opening"]})
        requirements = readback.plan_requirements(spec, self.profile, "L")
        errors, evidence = readback.geometry_check(doc, requirements, "A-101", self.profile)
        self.assertEqual(errors, [])
        self.assertEqual(len(evidence), 6)
        arc.dxf.invisible = 1
        errors, _ = readback.geometry_check(doc, requirements, "A-101", self.profile)
        self.assertTrue(errors)
        arc.dxf.invisible = 0
        doc.modelspace().delete_entity(arc)
        errors, _ = readback.geometry_check(doc, requirements, "A-101", self.profile)
        self.assertIn("A-101: geometry door: missing or changed ARC", errors[0])

    def test_legacy_geometry_without_xdata_is_measured_and_wrong_identity_fails(self):
        path = self.out / "A-101.dxf"
        doc = ezdxf.readfile(path)
        associated = [e for e in doc.modelspace() if e.has_xdata("GRIDLINE")]
        for entity in associated:
            entity.discard_xdata("GRIDLINE")
        doc.saveas(path)
        checked = run("check", EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 0, checked.stdout)
        measurements = self.report()["coverage"]["dxf_geometry"]["sheets"]["A-101"]["measured"]
        self.assertTrue(all(e["identity"] == "GEOMETRY_INFERRED" for e in measurements))
        associated[0].set_xdata("GRIDLINE", [(1000, "invented")])
        doc.saveas(path)
        checked = run("check", EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 1, checked.stdout)
        self.assertIn("incorrect GRIDLINE association", checked.stdout)

    def test_translated_rotated_plan_and_malformed_points(self):
        data = json.loads(EXAMPLE.read_text())
        def transform(p):
            x, y = p
            return [x * math.cos(0.37) - y * math.sin(0.37) + 1234,
                    x * math.sin(0.37) + y * math.cos(0.37) - 456]
        for wall in data["walls"] + data["grids"]:
            wall["start"], wall["end"] = transform(wall["start"]), transform(wall["end"])
        for room in data["rooms"]:
            room["boundary"] = [transform(p) for p in room["boundary"]]
        for sheet in data["sheets"]:
            sheet["size"] = "A1"
        spec = self.root / "rotated.json"
        spec.write_text(json.dumps(data))
        built = run("build", spec, self.out)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        checked = run("check", spec, self.out)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        # Curved/3D substitutes for straight plan edges must never silently pass.
        path = self.out / "A-101.dxf"
        doc = ezdxf.readfile(path)
        wall = next(e for e in doc.modelspace().query("LWPOLYLINE") if e.has_xdata("GRIDLINE"))
        points = list(wall.get_points())
        points[0] = (*points[0][:4], 0.5)
        wall.set_points(points)
        doc.saveas(path)
        checked = run("check", spec, self.out)
        self.assertEqual(checked.returncode, 1, checked.stdout)

    def test_malformed_and_oversized_json_have_failure_receipts(self):
        spec = self.root / "bad.json"
        for value in (b"{", b"[]", b" " * (10 * 1024 * 1024 + 1)):
            with self.subTest(length=len(value)):
                spec.write_bytes(value)
                checked = run("check", spec, self.out)
                self.assertEqual(checked.returncode, 1, checked.stderr)
                self.assertNotIn("Traceback", checked.stderr)
                self.assertEqual(self.report()["status"], "FAIL")

    def test_receipt_detects_files_changed_during_validation(self):
        from unittest import mock
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(sys.path.remove, str(SCRIPT.parent))
        import aec_cad
        original = aec_cad.pdf_check
        path = self.out / "A-101.pdf"
        consumed = path.read_bytes()
        def replace_after_read(*args):
            result = original(*args)
            path.write_bytes(b"changed during check")
            return result
        with mock.patch.object(aec_cad, "pdf_check", side_effect=replace_after_read):
            self.assertEqual(aec_cad.check(EXAMPLE, self.out, None), 1)
        report = self.report()
        self.assertEqual(report["output_hashes"][path.name], hashlib.sha256(consumed).hexdigest())
        self.assertEqual(report["coverage"]["snapshot_consistency"]["status"], "FAIL")
        self.assertIn("files changed during verification", " ".join(report["errors"]))

    def test_standalone_canonical_and_claude_bundles_need_no_repository_imports(self):
        for label, source in (("canonical", SKILL),
                              ("claude", ROOT / "providers/claude/skills/architectural-drawing-generation")):
            with self.subTest(bundle=label):
                copied = self.root / label
                shutil.copytree(source, copied, ignore=shutil.ignore_patterns("__pycache__"))
                checked = subprocess.run([sys.executable, "-I", str(copied / "scripts/aec_cad.py"), "check",
                                          str(copied / "references/example-house.building.json"), str(self.out)],
                                         cwd=self.root, capture_output=True, text=True)
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertEqual(self.report()["code_sha"], "UNKNOWN")

    def test_stale_register_date_and_broken_dxf_are_failures(self):
        path = self.out / "sheet-register.csv"
        path.write_text(path.read_text().replace("2026-10-22", "2000-01-01"))
        checked = run("check", EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 1, checked.stdout)
        self.assertIn("sheet-register.csv", checked.stdout)
        (self.out / "A-101.dxf").write_bytes(b"not a dxf")
        checked = run("check", EXAMPLE, self.out)
        self.assertEqual(checked.returncode, 1, checked.stderr)
        self.assertNotIn("Traceback", checked.stderr)
        self.assertEqual(self.report()["status"], "FAIL")
