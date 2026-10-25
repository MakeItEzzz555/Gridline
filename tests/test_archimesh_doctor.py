"""Offline inventory must never mistake source bytes or host startup for acceptance."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/architectural-drawing-generation"
SPEC = importlib.util.spec_from_file_location("archimesh_doctor", SKILL / "scripts/archimesh_doctor.py")
doctor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(doctor)


class ArchimeshDoctorTests(unittest.TestCase):
    def test_source_is_hashed_never_executed_and_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            source = b"raise RuntimeError('must never execute')\n"
            (root / "__init__.py").write_bytes(source)
            reference = {"version": "1.2.5", "files": {"__init__.py": hashlib.sha256(source).hexdigest()}}
            report = doctor.inspect_source(root, reference)
            self.assertEqual(report["source_state"], "SOURCE_VERIFIED")
            for key in ("registration", "available_operators", "geometry_acceptance"):
                self.assertEqual(report[key], "NOT_TESTED")
            (root / "__init__.py").write_bytes(source + b"# changed\n")
            self.assertEqual(doctor.inspect_source(root, reference)["source_state"], "UNVERIFIED")
            (root / "__init__.py").unlink()
            self.assertIn("__init__.py", doctor.inspect_source(root, reference)["changed_or_missing"])

    def test_extra_source_and_oversized_files_do_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "extra.py").write_text("unexpected", encoding="utf-8")
            report = doctor.inspect_source(root, {"version": "1.2.5", "files": {}})
            self.assertEqual(report["source_state"], "UNVERIFIED")
            self.assertEqual(report["unexpected_files"], ["extra.py"])
            with patch.object(doctor, "MAX_FILE_BYTES", 2):
                with self.assertRaisesRegex(ValueError, "exceeds"):
                    doctor.inspect_source(root, {"files": {}})

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO only")
    def test_special_file_rejected_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp).resolve() / "pipe"
            os.mkfifo(path)
            with self.assertRaisesRegex(ValueError, "regular file"):
                doctor.read_file(path)

    def test_symlinks_and_tree_overflow_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "source").mkdir()
            (root / "source/file.py").write_text("data", encoding="utf-8")
            try:
                (root / "link").symlink_to(root / "source", target_is_directory=True)
            except OSError:
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "symlink"):
                doctor.inspect_source(root / "link", {})
            (root / "source/linked.py").symlink_to(root / "source/file.py")
            with self.assertRaisesRegex(ValueError, "symlink"):
                doctor.inspect_source(root / "source", {})
            (root / "source/linked.py").unlink()
            for i in range(129):
                (root / "source" / str(i)).touch()
            with self.assertRaisesRegex(ValueError, "128"):
                doctor.inspect_source(root / "source", {})

    def test_discovery_is_scoped_to_default_profiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            expected = [root / "5.2/scripts/addons/archimesh",
                        root / "4.2/extensions/blender_org/archimesh"]
            for p in expected + [root / "unrelated/archimesh"]:
                p.mkdir(parents=True)
            self.assertEqual(doctor.discover(root), sorted(expected))
            self.assertEqual(doctor.discover(root / "missing"), [])

    def test_unreadable_subdirectory_cannot_be_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            def walk(path, *, onerror):
                onerror(PermissionError("unreadable nested source"))
            with patch.object(doctor.os, "walk", side_effect=walk):
                with self.assertRaises(PermissionError):
                    doctor.inspect_source(Path(tmp).resolve(), {"files": {}})

    def test_host_process_has_private_resources_and_no_addon_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "Blender"
            executable.touch()
            seen = []
            def run(cmd, **kwargs):
                seen.append(cmd)
                self.assertTrue(Path(kwargs["cwd"]).is_dir())
                self.assertNotIn("PYTHONPATH", kwargs["env"])
                self.assertNotEqual(kwargs["env"]["BLENDER_USER_CONFIG"], "private-user-profile")
                self.assertTrue(Path(kwargs["env"]["BLENDER_USER_CONFIG"]).is_dir())
                self.assertNotIn("--python", cmd)
                self.assertNotIn("--addons", cmd)
                return subprocess.CompletedProcess(cmd, 0, "Blender 5.2.3 LTS\n", "")
            with patch.dict(os.environ, {"PYTHONPATH": "untrusted", "BLENDER_USER_CONFIG": "private-user-profile"}), patch.object(doctor.subprocess, "run", side_effect=run):
                result = doctor.probe_host(executable)
            self.assertEqual(result["archimesh_compatibility"], "NOT_TESTED")
            self.assertEqual(len(seen), 2)
            self.assertIn("--factory-startup", seen[1])
            self.assertIn("--disable-autoexec", seen[1])
            self.assertIn("--offline-mode", seen[1])

    def test_missing_dependency_is_inventory_only_not_pass(self):
        output = io.StringIO()
        with patch.object(doctor, "discover", return_value=[]), patch.object(doctor, "probe_host", return_value={"state": "NOT_FOUND"}), contextlib.redirect_stdout(output):
            self.assertEqual(doctor.main([]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["dependency"], "NOT_FOUND_IN_DEFAULT_PATHS")
        self.assertEqual(report["generation"], "BLOCKED")
        self.assertEqual(report["license_boundary"], "NEEDS_LICENSE_REVIEW")
        self.assertEqual(report["state"], "INVENTORY_ONLY")

    def test_windows_executable_name_and_invalid_host_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable = Path(tmp) / "blender.exe"
            executable.touch()
            with patch.object(doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "Blender 5.2.3\n", "")):
                self.assertEqual(doctor.probe_host(executable)["version"], "5.2.3")
            with patch.object(doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "different program\n", "")):
                with self.assertRaisesRegex(ValueError, "version probe"):
                    doctor.probe_host(executable)

    def test_host_errors_are_structured_blocked(self):
        for error in (FileNotFoundError("missing"), subprocess.TimeoutExpired("Blender", 15),
                      subprocess.CalledProcessError(1, "Blender"), ValueError("bad version")):
            output = io.StringIO()
            with self.subTest(error=type(error).__name__), patch.object(doctor, "probe_host", side_effect=error), contextlib.redirect_stdout(output):
                self.assertEqual(doctor.main(["--blender", "/missing/Blender"]), 1)
                self.assertEqual(json.loads(output.getvalue())["state"], "BLOCKED")

    def test_portable_skill_has_no_repo_import_and_pin_has_only_source_hashes(self):
        reference = json.loads(doctor.REFERENCE.read_text(encoding="utf-8"))
        self.assertEqual(len(reference["files"]), 19)
        self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in reference["files"]))
        self.assertEqual(len(reference["operators"]), 16)
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "installed"
            shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
            result = subprocess.run([os.sys.executable, str(installed / "scripts/archimesh_doctor.py"), "--help"], cwd=tmp, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--addon-source", result.stdout)


if __name__ == "__main__":
    unittest.main()
