"""Controlled warm-start comparisons: 100 seeds and 100 controller updates."""

from __future__ import annotations

import sys

from src.run_warm_start_suite import main as run


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    run([
        "--n", "5000",
        "--horizon", "100",
        "--seeds", "100",
        "--out", "experiments/results/warm_start_suite.json",
        "--report", "experiments/results/warm_start_suite.md",
        *args,
    ])


if __name__ == "__main__":
    main()
