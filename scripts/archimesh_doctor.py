#!/usr/bin/env python3
"""Repository launcher for the portable ARCHIMESH source doctor."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "skills" /
                      "architectural-drawing-generation/scripts/archimesh_doctor.py"), run_name="__main__")
