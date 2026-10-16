"""Full public BAT calibration used in the paper."""

from __future__ import annotations

import sys

from src.bat_runner import main as run


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return run([
        "--full",
        "--timeout", "180",
        "--json-name", "bat_full_admissible.json",
        "--md-name", "bat_full_admissible.md",
        *args,
    ])


if __name__ == "__main__":
    raise SystemExit(main())
