"""Stage-by-stage command line interface. Each stage fails on invalid inputs."""
import argparse
import json
from pathlib import Path
import sys
import unittest

from .config import ROOT


def unit_checks():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError("Unit checks failed; stopping the pipeline")
    return {"tests_run": result.testsRun, "passed": True}


def main():
    parser = argparse.ArgumentParser(description="Olist real-data analytics pipeline")
    parser.add_argument("stage", choices=["acquire", "audit", "build", "analyze", "report", "notebooks", "check", "all"])
    parser.add_argument("--archive", type=Path, help="Optional manually downloaded official ZIP (acquire/all only)")
    args = parser.parse_args()
    if args.archive and args.stage not in ["acquire", "all"]:
        parser.error("--archive is only valid for acquire/all")
    from .analysis import run_analysis
    from .database import build_database
    from .intake import acquire
    from .notebooks import execute_notebooks
    from .quality import load_and_audit
    from .reporting import render_report
    from .validation import validate_outputs
    from .visualization import make_figures

    def audit():
        _, report = load_and_audit()
        return {"passed": report["passed"], "details": "reports/data_quality.json"}

    def report():
        figures = make_figures()
        render_report()
        return {"figures": figures, "report": "reports/analytical_report.md"}

    def check():
        return {"unit": unit_checks(), "integration": validate_outputs()}

    stages = {"acquire": lambda: acquire(args.archive), "audit": audit,
              "build": build_database, "analyze": run_analysis,
              "report": report, "notebooks": execute_notebooks, "check": check}
    selected = stages if args.stage == "all" else {args.stage: stages[args.stage]}
    for name, function in selected.items():
        print(f"Running {name}...", flush=True)
        try:
            result = function()
        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            print(f"Stage {name} failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc
        print(json.dumps({"stage": name, "result": result}, indent=2), flush=True)


if __name__ == "__main__":
    main()
