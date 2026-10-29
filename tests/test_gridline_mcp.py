import json
from unittest import mock
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "skills/architectural-drawing-generation/scripts"
sys.path.insert(0, str(TOOLS))
import gridline_mcp

EXAMPLE = ROOT / "skills/architectural-drawing-generation/references/example-house.building.json"


class GridlineReadOnlyMCPTests(unittest.TestCase):
    def test_requires_opt_in_project_root(self):
        with self.assertRaisesRegex(ValueError, "GRIDLINE_MCP_PROJECT_ROOT"):
            gridline_mcp.compare_revisions("one.json", "two.json", project_root="")

    def test_rejects_outside_root_and_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "source.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "authorized"):
                gridline_mcp.project_file("../../etc/passwd", base)
            with self.assertRaisesRegex(ValueError, "authorized"):
                gridline_mcp.project_file(str(EXAMPLE), base)

    def test_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "escape.json").symlink_to(EXAMPLE)
            with self.assertRaisesRegex(ValueError, "authorized"):
                gridline_mcp.project_file("escape.json", base)

    def test_rejects_non_json_and_large_files(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "note.txt").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON file"):
                gridline_mcp.project_file("note.txt", base)
            (base / "huge.json").write_bytes(b"x" * (gridline_mcp.MAX_SPEC_SIZE + 1))
            with self.assertRaisesRegex(ValueError, "5 MB"):
                gridline_mcp.project_file("huge.json", base)

    def test_reads_under_root_without_mutating_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            spec = json.loads(EXAMPLE.read_text(encoding="utf-8"))
            old, new = base / "old.json", base / "new.json"
            old.write_text(json.dumps(spec), encoding="utf-8")
            spec["openings"][4]["width"] = 2150
            new.write_text(json.dumps(spec), encoding="utf-8")
            before_bytes, after_bytes = old.read_bytes(), new.read_bytes()
            result = gridline_mcp.compare_revisions("old.json", "new.json", project_root=td)
            self.assertIn("window-schedule.csv", result["schedules_to_recheck"])
            self.assertEqual(before_bytes, old.read_bytes())
            self.assertEqual(after_bytes, new.read_bytes())

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd,
                         "requires descriptor-relative no-follow opens")
    def test_ancestor_swap_after_validation_cannot_escape_root(self):
        # A concurrent process replaces an authorized directory with a symlink
        # just before its descriptor-relative open. The outside JSON must not
        # be opened even if it contains a syntactically valid building spec.
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            authorized = base / "authorized"
            folder = authorized / "part"
            folder.mkdir(parents=True)
            outside = base / "outside"
            outside.mkdir()
            payload = EXAMPLE.read_bytes()
            (folder / "before.json").write_bytes(payload)
            (folder / "after.json").write_bytes(payload)
            (outside / "before.json").write_bytes(payload)
            (outside / "after.json").write_bytes(payload)
            real_open = os.open
            swapped = False

            def swap_then_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == "part" and "dir_fd" in kwargs and not swapped:
                    swapped = True
                    folder.rename(authorized / "old-part")
                    folder.symlink_to(outside, target_is_directory=True)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(gridline_mcp.os, "open", side_effect=swap_then_open):
                with self.assertRaises((ValueError, OSError)):
                    gridline_mcp.compare_revisions(
                        "part/before.json", "part/after.json", project_root=str(authorized))
            self.assertTrue(swapped)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd,
                         "requires descriptor-relative no-follow opens")
    def test_file_growth_after_stat_is_still_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            payload = EXAMPLE.read_bytes()
            (base / "before.json").write_bytes(payload)
            (base / "after.json").write_bytes(payload)
            real_read = os.read
            grown = False

            def grow_then_read(fd, size):
                nonlocal grown
                if not grown:
                    grown = True
                    with (base / "before.json").open("ab") as target:
                        target.write(b" " * (gridline_mcp.MAX_SPEC_SIZE + 1))
                return real_read(fd, size)

            with mock.patch.object(gridline_mcp.os, "read", side_effect=grow_then_read):
                with self.assertRaisesRegex(ValueError, "5 MB"):
                    gridline_mcp.compare_revisions(
                        "before.json", "after.json", project_root=str(base))
            self.assertTrue(grown)

    def test_nested_authorized_json_is_readable(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            nested = base / "subdir"
            nested.mkdir()
            payload = EXAMPLE.read_bytes()
            (nested / "before.json").write_bytes(payload)
            (nested / "after.json").write_bytes(payload)
            report = gridline_mcp.compare_revisions(
                "subdir/before.json", "subdir/after.json", project_root=td)
            self.assertEqual(report["status"], "NO_INDEXED_CHANGES")

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW") and os.open in os.supports_dir_fd,
                         "requires descriptor-relative no-follow opens")
    def test_leaf_swap_to_outside_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            authorized = base / "authorized"
            authorized.mkdir()
            outside = base / "outside.json"
            outside.write_bytes(EXAMPLE.read_bytes())
            leaf = authorized / "before.json"
            leaf.write_bytes(EXAMPLE.read_bytes())
            (authorized / "after.json").write_bytes(EXAMPLE.read_bytes())
            real_open = os.open
            swapped = False

            def swap_then_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == "before.json" and "dir_fd" in kwargs and not swapped:
                    swapped = True
                    leaf.unlink()
                    leaf.symlink_to(outside)
                return real_open(path, flags, *args, **kwargs)

            with mock.patch.object(gridline_mcp.os, "open", side_effect=swap_then_open):
                with self.assertRaises((ValueError, OSError)):
                    gridline_mcp.compare_revisions(
                        "before.json", "after.json", project_root=str(authorized))
            self.assertTrue(swapped)

    def test_capabilities_do_not_claim_native_connections(self):
        cap = gridline_mcp.capabilities()
        self.assertFalse(cap["native_autocad_or_revit_connection"])
        self.assertFalse(cap["edits_models"])

    def test_server_without_explicit_root_refuses_start(self):
        env = dict(os.environ)
        env.pop("GRIDLINE_MCP_PROJECT_ROOT", None)
        p = subprocess.run([sys.executable, str(TOOLS / "gridline_mcp.py")],
                           capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(p.returncode, 2)
        self.assertIn("GRIDLINE_MCP_PROJECT_ROOT", p.stderr)


if __name__ == "__main__":
    unittest.main()
