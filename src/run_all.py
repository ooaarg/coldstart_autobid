#!/usr/bin/env python3
"""Run the reproducible experiment suite in a safe order.

The runner is intentionally conservative. BAT and public RTB experiments can be
multi-GB, so the default command runs smoke-sized checks. Pass `--full` to any
sub-runner that supports it by invoking that runner directly.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments" / "results"


def run_step(name: str, cmd: list[str]) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "name": name,
        "cmd": cmd,
        "returncode": proc.returncode,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def existing_script(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/results/run_all_manifest.json")
    parser.add_argument("--bat-max-rows", type=int, default=20000)
    parser.add_argument("--bat-max-campaigns", type=int, default=1000)
    parser.add_argument("--bat-cold-start-max-rows", type=int, default=200000)
    parser.add_argument("--synthetic-n", type=int, default=5000)
    parser.add_argument("--warm-start-seeds", type=int, default=10)
    parser.add_argument("--warm-start-horizon", type=int, default=100)
    args = parser.parse_args()

    RESULTS.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    steps: list[tuple[str, list[str]]] = [
        (
            "synthetic_smoke",
            [py, "-m", "src.run_synthetic_smoke", "--n", str(args.synthetic_n), "--out", "experiments/results/synthetic_smoke.json"],
        ),
        (
            "bat_access",
            [py, "-m", "src.bat_download_check", "--out", "experiments/results/bat_access.json"],
        ),
        (
            "bat_schema_sample",
            [py, "-m", "src.bat_schema_sample", "--out", "experiments/results/bat_schema_sample.json", "--bytes", "65536", "--rows", "2"],
        ),
    ]

    optional_steps = [
        (
            "full_synthetic",
            [
                py,
                "-m",
                "src.run_full_synthetic",
                "--n",
                str(args.synthetic_n),
                "--out",
                "experiments/results/full_synthetic.json",
                "--report",
                "experiments/results/full_synthetic_report.md",
            ],
            "src/run_full_synthetic.py",
        ),
        (
            "bat_admissible_calibration",
            [
                py,
                "-m",
                "src.bat_runner",
                "--max-rows",
                str(args.bat_max_rows),
                "--json-name",
                "bat_admissible_smoke.json",
                "--md-name",
                "bat_admissible_smoke.md",
            ],
            "src/bat_runner.py",
        ),
        (
            "bat_cold_start_replay",
            [
                py,
                "-m",
                "src.bat_cold_start_runner",
                "--max-campaigns",
                str(args.bat_max_campaigns),
                "--max-stats-rows",
                str(args.bat_cold_start_max_rows),
                "--json-name",
                "bat_cold_start_smoke.json",
                "--md-name",
                "bat_cold_start_smoke.md",
            ],
            "src/bat_cold_start_runner.py",
        ),
        (
            "warm_start_suite",
            [
                py,
                "-m",
                "src.run_warm_start_suite",
                "--n",
                str(args.synthetic_n),
                "--horizon",
                str(args.warm_start_horizon),
                "--seeds",
                str(args.warm_start_seeds),
                "--out",
                "experiments/results/warm_start_suite.json",
                "--report",
                "experiments/results/warm_start_suite.md",
            ],
            "src/run_warm_start_suite.py",
        ),
        (
            "public_rtb_check",
            [py, "-m", "src.public_rtb_check", "--out", "experiments/results/public_rtb_check.json"],
            "src/public_rtb_check.py",
        ),
    ]
    for name, cmd, script in optional_steps:
        if existing_script(script):
            steps.append((name, cmd))

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "steps": [],
    }
    exit_code = 0
    for name, cmd in steps:
        result = run_step(name, cmd)
        manifest["steps"].append(result)
        if result["returncode"] != 0:
            exit_code = result["returncode"]
            break

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
