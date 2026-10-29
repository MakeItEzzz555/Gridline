#!/usr/bin/env python3
"""Gridline's opt-in, read-only local MCP server for revision-impact analysis.

Requires the official MCP Python SDK v2: python -m pip install 'mcp>=2,<3'
Requires GRIDLINE_MCP_PROJECT_ROOT to name an explicitly authorized project
directory. No write tools, shell execution, network listener, or host mutations.
"""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from revision_impact import analyze

MAX_SPEC_SIZE = 5_000_000
HAS_SECURE_OPEN = (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
                   and os.open in os.supports_dir_fd)


def project_file(path: str, root: Path) -> Path:
    """Validate a path for legacy callers; do not reopen it as a security boundary.

    compare_revisions uses read_project_spec instead, which pins file descriptors
    on platforms supporting descriptor-relative, no-follow directory traversal.
    """
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("A non-empty project-relative JSON path is required")
    root = root.expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project root must be a directory")
    requested = Path(path)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("Only project-relative JSON files within the authorized directory are allowed")
    candidate = (root / requested).resolve(strict=False)
    if not candidate.is_relative_to(root) or candidate.suffix.lower() != ".json":
        raise ValueError("The path must be a JSON file within the authorized project directory")
    if not candidate.is_file():
        raise ValueError("The authorized project JSON file was not found")
    if candidate.stat().st_size > MAX_SPEC_SIZE:
        raise ValueError("Project JSON exceeds the 5 MB read limit")
    return candidate



def read_project_spec(path: str, root: Path) -> dict:
    """Read a bounded JSON snapshot with descriptor-relative confinement on POSIX.

    Pin the authorized directory, traverse each component without following
    symlinks, and read only from the final opened regular-file descriptor.
    A concurrent rename cannot redirect that descriptor outside the root.
    On platforms without these OS primitives, retain the existing checked
    pathname fallback; that fallback is not race-proof.
    """
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("A non-empty project-relative JSON path is required")
    requested = Path(path)
    if requested.is_absolute() or ".." in requested.parts or requested.suffix.lower() != ".json":
        raise ValueError("Only project-relative JSON files within the authorized directory are allowed")
    base = root.expanduser().resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Project root must be a directory")

    if not HAS_SECURE_OPEN:
        # Backward-compatible fallback for platforms lacking dir_fd support.
        # This does not provide race-proof confinement; see README.
        with project_file(path, base).open("rb") as handle:
            data = handle.read(MAX_SPEC_SIZE + 1)
        if len(data) > MAX_SPEC_SIZE:
            raise ValueError("Project JSON exceeds the 5 MB read limit")
    else:
        dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        dir_fd = os.open(base, dir_flags)
        try:
            for part in requested.parts[:-1]:
                next_fd = os.open(part, dir_flags, dir_fd=dir_fd)
                os.close(dir_fd)
                dir_fd = next_fd
            flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
            file_fd = os.open(requested.parts[-1], flags, dir_fd=dir_fd)
            try:
                info = os.fstat(file_fd)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("Project JSON must be a regular file")
                if info.st_size > MAX_SPEC_SIZE:
                    raise ValueError("Project JSON exceeds the 5 MB read limit")
                chunks = []
                total = 0
                while True:
                    chunk = os.read(file_fd, min(65536, MAX_SPEC_SIZE + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_SPEC_SIZE:
                        raise ValueError("Project JSON exceeds the 5 MB read limit")
                    chunks.append(chunk)
                data = b"".join(chunks)
            finally:
                os.close(file_fd)
        finally:
            os.close(dir_fd)
    document = json.loads(data.decode("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Project JSON must contain an object")
    return document


def compare_revisions(before: str, after: str, project_root: str | None = None) -> dict:
    """Compare two explicitly provided project JSON files; never alter them."""
    root = project_root or os.environ.get("GRIDLINE_MCP_PROJECT_ROOT", "")
    if not root:
        raise ValueError("GRIDLINE_MCP_PROJECT_ROOT must be set explicitly")
    base = Path(root)
    return analyze(read_project_spec(before, base), read_project_spec(after, base))


def capabilities() -> dict:
    """Accurately describe what this server can and cannot verify."""
    return {
        "server": "Gridline Review",
        "scope": "read_only_local_project_json",
        "tools": ["compare_revisions", "capabilities"],
        "native_autocad_or_revit_connection": False,
        "reads_dxf_or_ifc": False,
        "edits_models": False,
        "coverage": "indexed spec references only; unindexed sheets require human review",
    }


def main() -> int:
    if not os.environ.get("GRIDLINE_MCP_PROJECT_ROOT"):
        print("ERROR: Set GRIDLINE_MCP_PROJECT_ROOT before launching Gridline MCP.", file=sys.stderr)
        return 2
    try:
        from mcp.server.mcpserver import MCPServer  # MCP official Python SDK v2
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError:
        print("ERROR: install official MCP Python SDK v2: pip install 'mcp>=2,<3'", file=sys.stderr)
        return 2
    server = MCPServer("Gridline Review")

    @server.tool()
    def compare_gridline_revisions(before: str, after: str) -> dict:
        """Read two building spec JSON files under the authorized project root; list impacted sheets and schedules."""
        try:
            return compare_revisions(before, after)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            raise ToolError(str(exc)) from exc

    @server.tool()
    def get_gridline_capabilities() -> dict:
        """Describe read-only capabilities and verification limits."""
        return capabilities()

    server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    sys.exit(main())
