import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/architectural-drawing-generation/scripts"))
import revision_impact as impact

EXAMPLE = ROOT / "skills/architectural-drawing-generation/references/example-house.building.json"


class RevisionImpactTests(unittest.TestCase):
    def setUp(self):
        self.old = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.new = copy.deepcopy(self.old)

    def test_no_changes(self):
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["status"], "NO_INDEXED_CHANGES")
        self.assertEqual(result["changes"], [])

    def test_window_schedule_change_flags_both_plans_and_schedule(self):
        self.new["openings"][4]["width"] = 2100
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["schedules_to_recheck"], ["window-schedule.csv"])
        self.assertEqual(result["affected_indexed_sheets"], ["A-101", "A-102"])
        self.assertEqual(result["changes"][0]["changed_fields"], ["width"])
        self.assertIs(result["changes"][0]["references_exhaustive"], False)

    def test_explicit_section_reference_is_included(self):
        self.new["openings"][4]["width"] = 2100
        self.new["sheets"].append({
            "number": "A-301", "title": "Section 1", "level": "L99",
            "references": {"openings": ["W01"]},
        })
        result = impact.analyze(self.old, self.new)
        self.assertIn("A-301", result["affected_indexed_sheets"])
        self.assertIn("A-301", result["changed_sheets"])

    def test_window_removed_still_flags_original_sheets(self):
        self.new["openings"] = [x for x in self.new["openings"] if x["id"] != "W01"]
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["changes"][0]["operation"], "removed")
        self.assertEqual(result["affected_indexed_sheets"], ["A-101", "A-102"])

    def test_new_window_identifies_schedule(self):
        self.new["openings"].append({
            "id": "W99", "kind": "window", "wall": "E1",
            "offset": 9500, "width": 700, "height": 900,
        })
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["schedules_to_recheck"], ["window-schedule.csv"])

    def test_wall_change_flags_affected_plans(self):
        self.new["walls"][0]["thickness"] = 350
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["affected_indexed_sheets"], ["A-101", "A-102"])

    def test_room_change_flags_room_schedule(self):
        self.new["rooms"][0]["name"] = "Living area"
        result = impact.analyze(self.old, self.new)
        self.assertIn("room-schedule.csv", result["schedules_to_recheck"])

    def test_project_revision_change_marks_all_sheets(self):
        self.new["project"]["revision"] = "P02"
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["changed_project_fields"], ["revision"])
        self.assertEqual(result["affected_indexed_sheets"], ["A-101", "A-102"])
        self.assertIn("sheet-register.csv", result["schedules_to_recheck"])

    def test_move_wall_level_flags_old_and_new_levels(self):
        self.new["levels"].append({"id": "L01", "name": "First floor", "elevation": 3000, "height": 3000})
        self.new["walls"][0]["level"] = "L01"
        self.new["sheets"].append({"number": "A-201", "title": "First floor", "level": "L01"})
        result = impact.analyze(self.old, self.new)
        self.assertIn("A-101", result["affected_indexed_sheets"])
        self.assertIn("A-201", result["affected_indexed_sheets"])

    def test_stale_sheet_reference_is_reported_not_silently_accepted(self):
        self.new["sheets"][0]["references"] = {"openings": ["W404"]}
        result = impact.analyze(self.old, self.new)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["stale_sheet_references"][0]["id"], "W404")

    def test_duplicate_ids_fail_closed(self):
        self.new["openings"].append(dict(self.new["openings"][0]))
        with self.assertRaises(impact.InvalidSpecification):
            impact.analyze(self.old, self.new)

    def test_invalid_sheet_reference_fails_closed(self):
        self.new["sheets"][0]["references"] = {"openings": "W01"}
        with self.assertRaises(impact.InvalidSpecification):
            impact.analyze(self.old, self.new)

    def test_wall_edit_flags_hosted_opening_only_section_and_dependent_schedules(self):
        # This section has no wall reference and is on a different level;
        # the hosted opening is the only explicit link to the changed wall.
        section = {"number": "A-301", "title": "Door detail",
                   "level": "L99", "references": {"openings": ["D01"]}}
        self.old["sheets"].append(copy.deepcopy(section))
        self.new["sheets"].append(copy.deepcopy(section))
        self.new["walls"][0]["thickness"] += 50
        result = impact.analyze(self.old, self.new)
        self.assertIn("A-301", result["affected_indexed_sheets"])
        self.assertEqual(result["changed_sheets"], [])
        self.assertTrue({"door-schedule.csv", "window-schedule.csv",
                         "room-schedule.csv"}.issubset(result["schedules_to_recheck"]))

    def test_level_height_edit_flags_dependent_detail_and_schedules(self):
        detail = {"number": "A-401", "title": "Room volume detail",
                  "level": "L99", "references": {"rooms": ["R01"]}}
        self.old["sheets"].append(copy.deepcopy(detail))
        self.new["sheets"].append(copy.deepcopy(detail))
        self.new["levels"][0]["height"] += 200
        result = impact.analyze(self.old, self.new)
        self.assertIn("A-401", result["affected_indexed_sheets"])
        self.assertEqual(result["changed_sheets"], [])
        self.assertTrue({"door-schedule.csv", "window-schedule.csv",
                         "room-schedule.csv"}.issubset(result["schedules_to_recheck"]))

    def test_cli_reports_json_and_nonzero_for_bad_spec(self):
        with tempfile.TemporaryDirectory() as td:
            old = Path(td) / "old.json"
            new = Path(td) / "new.json"
            out = Path(td) / "impact.json"
            old.write_text(json.dumps(self.old), encoding="utf-8")
            self.new["openings"][4]["width"] = 2100
            new.write_text(json.dumps(self.new), encoding="utf-8")
            cmd = [sys.executable, str(ROOT / "skills/architectural-drawing-generation/scripts/revision_impact.py"),
                   str(old), str(new), "--out", str(out)]
            p = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(out.read_text())["status"], "REVIEW_REQUIRED")
            new.write_text("not json!", encoding="utf-8")
            p = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)
            self.assertIn("ERROR", p.stderr)


if __name__ == "__main__":
    unittest.main()
