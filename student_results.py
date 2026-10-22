"""Compatibility CLI for the packaged master-sheet parser."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
from record_imports.student_sheet import *  # noqa: F403,F401

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract student fields from a master marks sheet CSV.")
    parser.add_argument("tables_csv")
    parser.add_argument("extra_text_file")
    parser.add_argument("--output", help="Output folder; defaults to the table CSV folder.")
    args = parser.parse_args()
    export_student_results(args.tables_csv, args.extra_text_file, args.output)
