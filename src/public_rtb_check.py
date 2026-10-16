#!/usr/bin/env python3
"""Record public RTB/iPinYou availability for the censoring stress test.

This is intentionally a status check, not a downloader. Public iPinYou mirrors
are often routed through preprocessing repositories, Kaggle, or manual contest
archives. The paper should not depend on this source for structural claims.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request
from datetime import datetime, timezone


SOURCES = {
    "make_ipinyou_data": "https://raw.githubusercontent.com/wnzhang/make-ipinyou-data/master/README.md",
    "make_ipinyou_schema": "https://raw.githubusercontent.com/wnzhang/make-ipinyou-data/master/schema.txt",
    "ipinyou_dataset_note": "https://contest.ipinyou.com/ipinyou-dataset.pdf",
}


def check_url(url: str, timeout: int) -> dict[str, object]:
    req = urllib.request.Request(url, headers={"User-Agent": "codex-public-rtb-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            sample = resp.read(4096)
            return {
                "status": "reachable",
                "code": getattr(resp, "status", None),
                "content_type": resp.headers.get("content-type"),
                "sample_bytes": len(sample),
            }
    except Exception as exc:  # pragma: no cover - network dependent
        return {
            "status": "error",
            "error": str(exc),
        }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Public RTB / iPinYou Censoring Stress-Test Status",
        "",
        f"- Checked UTC: `{payload['checked_at_utc']}`",
        f"- Decision: `{payload['decision']}`",
        "",
        "## Source Checks",
        "",
        "| Source | Status | Note |",
        "| --- | --- | --- |",
    ]
    checks = payload.get("checks", {})
    if isinstance(checks, dict):
        for name, check in checks.items():
            if isinstance(check, dict):
                note = check.get("content_type") or check.get("error") or ""
                lines.append(f"| `{name}` | `{check.get('status')}` | `{note}` |")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Public RTB data should be used only as a censored-observability stress test.",
            "The main identification claims should remain anchored in synthetic, BAT, and semi-synthetic BAT evidence.",
            "If a full public RTB run is needed, prepare it as a separate preprocessing stage with explicit license/access notes.",
            "",
            "## Minimum Data Needed For A Stronger Censoring Experiment",
            "",
            "- bid, win indicator, paid price when won, and historical bid value;",
            "- campaign/context features aligned with `f` and `z`;",
            "- enough bid support or logging-policy variation to identify market-price tails;",
            "- clear train/test splits and permission to report derived aggregate diagnostics.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/results/public_rtb_check.json")
    parser.add_argument("--md", default="experiments/results/public_rtb_check.md")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    checks = {name: check_url(url, args.timeout) for name, url in SOURCES.items()}
    reachable = [name for name, status in checks.items() if status.get("status") == "reachable"]
    payload: dict[str, object] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": SOURCES,
        "checks": checks,
        "reachable_sources": reachable,
        "decision": "documented_stress_test_only",
        "blocked_reason": (
            "A clean, direct, license-explicit public RTB dataset download is not part of this repository. "
            "Use iPinYou-style data only after a separate preprocessing/download step."
        ),
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.makedirs(os.path.dirname(args.md) or ".", exist_ok=True)
    with open(args.md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(payload))
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
