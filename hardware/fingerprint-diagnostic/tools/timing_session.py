"""Run an explicitly selected existing hardware tool with private monotonic timings.

No hardware operation runs on import. This module does not implement matching.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from functools import wraps
import importlib
import json
from pathlib import Path
import sys
import time
import uuid


OPERATIONS = {
    "deferred-download": ("deferred_batches", "download", ("receive_batch", "save_download")),
    "probe-compare": ("probe_experiment", "compare", ("compare_probe", "save_new")),
    "reference-export": ("portable_template", "export", ("receive_export",)),
    "reference-restore": ("portable_template", "restore", ("restore_bytes",)),
}


def measured(function, phase, records, clock=time.perf_counter_ns):
    """Record duration and success without retaining arguments, return data or errors."""
    @wraps(function)
    def call(*args, **kwargs):
        started = clock()
        success = False
        try:
            result = function(*args, **kwargs)
            success = True
            return result
        finally:
            records.append({"phase": phase, "elapsed_ms": (clock() - started) / 1_000_000,
                            "completed": success})
    return call


def run(operation, tool_args, evidence_dir, *, loader=importlib.import_module):
    module_name, command, phases = OPERATIONS[operation]
    if not tool_args or tool_args[0] != command:
        raise ValueError(f"This operation requires the existing tool's '{command}' subcommand.")
    if "--new-gallery" in tool_args or "--all" in tool_args:
        raise ValueError("Use one existing reference; gallery replacement and bulk exports are excluded.")
    evidence_dir.mkdir(parents=True, exist_ok=False)
    records = []
    report = {"schema_version": 1, "operation": operation,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "host monotonic operation intervals; see TIMING-SESSION.md",
              "phases": records, "completed": False}
    module = loader(module_name)
    originals = {phase: getattr(module, phase) for phase in phases}
    previous_argv = sys.argv
    started = time.perf_counter_ns()
    exit_code = 1
    try:
        for phase, function in originals.items():
            setattr(module, phase, measured(function, phase, records))
        sys.argv = [module_name, *tool_args]
        with (evidence_dir / "console-private.log").open("x", encoding="utf-8") as stream:
            with redirect_stdout(stream), redirect_stderr(stream):
                try:
                    result = module.main()
                    exit_code = result if isinstance(result, int) else 0
                except SystemExit as error:
                    exit_code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
                    if error.code:
                        print(str(error), file=sys.stderr)
                except KeyboardInterrupt:
                    print("Operator interrupted; preserve pending receipts and device files.", file=sys.stderr)
                    exit_code = 130
                except Exception as error:
                    # Existing tools may include private paths/metadata in error text.
                    print(f"{type(error).__name__}: {error}", file=sys.stderr)
                    exit_code = 1
    finally:
        sys.argv = previous_argv
        for phase, function in originals.items():
            setattr(module, phase, function)
        report.update(completed=exit_code == 0, exit_code=exit_code,
                      process_elapsed_ms=(time.perf_counter_ns() - started) / 1_000_000)
        with (evidence_dir / "timing-metadata.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=OPERATIONS)
    parser.add_argument("--evidence-root", type=Path,
                        default=Path(__file__).resolve().parents[3] / "private-data" / "hardware-timing")
    parser.add_argument("tool_args", nargs=argparse.REMAINDER,
                        help="-- followed by the existing tool subcommand and arguments")
    args = parser.parse_args()
    tool_args = args.tool_args[1:] if args.tool_args[:1] == ["--"] else args.tool_args
    run_dir = args.evidence_root / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    print("Running selected hardware operation. Its console is saved privately; no scanner data is printed here.")
    try:
        result = run(args.operation, tool_args, run_dir)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Timing session did not start: {error}\n")
    print(f"Private evidence: {run_dir}")
    print("Completed." if result == 0 else "Failed or interrupted; preserve evidence and review before retrying.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
