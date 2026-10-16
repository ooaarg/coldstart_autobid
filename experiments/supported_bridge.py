"""Supported semi-synthetic bridge: 100 seeds, 60 contexts, sensitivity grid."""

from __future__ import annotations

import sys

from src.run_supported_bridge import main as run


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return run([
        "--seeds", "100",
        "--contexts", "60",
        "--out", "experiments/results/supported_bridge.json",
        "--report", "experiments/results/supported_bridge.md",
        *args,
    ])


if __name__ == "__main__":
    raise SystemExit(main())
