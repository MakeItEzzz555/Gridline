#!/usr/bin/env python3
"""Repository-level convenience launcher for the portable drawing skill bridge."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    script = Path(__file__).resolve().parents[1] / "skills" / "architectural-drawing-generation" / "scripts" / "blender_native.py"
    runpy.run_path(str(script), run_name="__main__")
