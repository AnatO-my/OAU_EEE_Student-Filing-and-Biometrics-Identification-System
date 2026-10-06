#!/usr/bin/env python
"""Compatibility entry point; delegates to the root management script."""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent.parent / "manage.py"), run_name="__main__")
