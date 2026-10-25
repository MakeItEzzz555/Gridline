#!/usr/bin/env python3
"""Offline, read-only ARCHIMESH source inventory. Never imports or enables add-ons."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

REFERENCE = Path(__file__).resolve().parent.parent / "references" / "archimesh-1.2.5.json"
MAX_FILE_BYTES = 1024 * 1024


def absolute_path(path):
    path = Path(os.path.abspath(path))
    # macOS exposes these system directories through aliases, not user-selected links.
    if sys.platform == "darwin" and len(path.parts) > 1 and path.parts[1] in ("tmp", "var"):
        path = Path("/private").joinpath(*path.parts[1:])
    return path


def read_file(path, *, max_bytes=None):
    """Bound reads and reject symlinks/devices, including selected parent links."""
    path = absolute_path(path)
    limit = MAX_FILE_BYTES if max_bytes is None else max_bytes
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("source symlinks are unsupported")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                 getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("source must be a regular file")
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("source file exceeds byte budget")
    return data


def default_root():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Blender"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Blender Foundation/Blender"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "blender"


def discover(root):
    """Only standard user profiles; custom/system repositories need --addon-source."""
    if not root.exists():
        return []
    if root.is_symlink():
        raise ValueError("profile root symlinks are unsupported; select the real source path")
    found = []
    for version in sorted(root.iterdir()):
        if not re.fullmatch(r"\d+\.\d+", version.name) or version.is_symlink() or not version.is_dir():
            continue
        candidates = [version / "scripts/addons/archimesh"]
        extensions = version / "extensions"
        if extensions.is_dir() and not extensions.is_symlink():
            for repository in extensions.iterdir():
                if repository.is_dir() and not repository.is_symlink():
                    candidates.append(repository / "archimesh")
        found.extend(p for p in candidates if p.exists() or p.is_symlink())
    return sorted(found)


def inspect_source(path, reference):
    path = absolute_path(path)
    if not path.is_dir() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("add-on source must be a real directory without symlink parents")
    hashes = {}
    count = 0
    def scan_error(error):
        raise error
    for directory, dirs, files in os.walk(path, onerror=scan_error):
        count += len(dirs) + len(files)
        if count > 128:
            raise ValueError("add-on tree exceeds bounded inventory (128 entries)")
        for name in dirs + files:
            if (Path(directory) / name).is_symlink():
                raise ValueError("source symlinks are unsupported")
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for name in files:
            item = Path(directory) / name
            hashes[item.relative_to(path).as_posix()] = hashlib.sha256(read_file(item)).hexdigest()
    expected = reference["files"]
    changed = sorted(name for name in expected if hashes.get(name) != expected[name])
    extra = sorted(hashes.keys() - expected.keys())
    matched = not changed and not extra
    return {"path": str(path), "source_state": "SOURCE_VERIFIED" if matched else "UNVERIFIED",
            "version": reference["version"] if matched else "UNKNOWN",
            "changed_or_missing": changed, "unexpected_files": extra,
            "file_sha256": hashes, "registration": "NOT_TESTED",
            "available_operators": "NOT_TESTED", "geometry_acceptance": "NOT_TESTED"}


def probe_host(executable):
    """Start only the host, with private resources and no external Python script."""
    executable = Path(executable).expanduser().resolve(strict=True)
    if not executable.is_file() or executable.name.lower() not in ("blender", "blender.exe"):
        raise ValueError("select a trusted Blender executable")
    with tempfile.TemporaryDirectory(prefix="gridline-archimesh-doctor-") as tmp:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BLENDER_", "PYTHON"))}
        for key in ("BLENDER_USER_RESOURCES", "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS",
                    "BLENDER_USER_EXTENSIONS", "BLENDER_USER_DATAFILES",
                    "BLENDER_SYSTEM_SCRIPTS", "BLENDER_SYSTEM_EXTENSIONS"):
            folder = Path(tmp) / key
            folder.mkdir()
            env[key] = str(folder)
        version = subprocess.run([str(executable), "--version"], env=env, cwd=tmp,
                                 capture_output=True, text=True, timeout=15, check=True).stdout
        match = re.search(r"^Blender (\d+\.\d+\.\d+)[^\r\n]*", version)
        if not match:
            raise ValueError("Blender version probe failed")
        subprocess.run([str(executable), "--background", "--factory-startup", "--disable-autoexec",
                        "--offline-mode"], env=env, cwd=tmp, capture_output=True, text=True,
                       timeout=30, check=True)
    return {"state": "HOST_STARTUP_VERIFIED", "version": match.group(1),
            "executable": str(executable), "addon_loading": "NOT_ATTEMPTED",
            "archimesh_compatibility": "NOT_TESTED"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addon-source", type=Path, help="inspect this directory without importing it")
    parser.add_argument("--blender", type=Path, help="trusted executable for isolated host startup")
    args = parser.parse_args(argv)
    try:
        reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
        root = default_root()
        paths = [args.addon_source] if args.addon_source else discover(root)
        sources = [inspect_source(p, reference) for p in paths]
        executable = args.blender or shutil.which("blender")
        if executable is None and sys.platform == "darwin":
            candidate = Path("/Applications/Blender.app/Contents/MacOS/Blender")
            executable = candidate if candidate.is_file() else None
        host = probe_host(executable) if executable else {"state": "NOT_FOUND"}
        report = {"schema": "gridline-archimesh-doctor.v1", "state": "INVENTORY_ONLY",
                  "network": "OFFLINE", "discovery": "EXPLICIT_SOURCE" if args.addon_source else "DEFAULT_USER_PROFILES",
                  "searched_root": None if args.addon_source else str(root),
                  "dependency": "SOURCE_FOUND" if sources else "NOT_FOUND_IN_DEFAULT_PATHS",
                  "host": host, "sources": sources,
                  "reference": {k: reference[k] for k in ("url", "archive_sha256", "version", "license", "blender_version_min")},
                  "operators_in_reference_source": [op["id"] for op in reference["operators"]],
                  "license_boundary": "NEEDS_LICENSE_REVIEW", "generation": "BLOCKED",
                  "unverified": ["No live profile registration or operator availability inspected",
                                 "Advertised minimum Blender version does not establish compatibility",
                                 "No component dimensions, callbacks, panels, native or GLB readback validated",
                                 "Custom/system installs are outside default discovery; select their source explicitly",
                                 "Matching source bytes is not execution authorization or license clearance"]}
        print(json.dumps(report, indent=2, ensure_ascii=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"state": "BLOCKED", "error": str(exc)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
