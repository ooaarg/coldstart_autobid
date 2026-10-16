#!/usr/bin/env python3
"""Write a reproducibility manifest for the CIKM code release."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


COMMANDS = [
    "python3 -m experiments.warm_start",
    "python3 -m experiments.supported_bridge",
    "python3 -m experiments.bat_calibration",
    "python3 -m src.bat_cold_start_runner --jobs 2 --json-name bat_cold_start_frontier_full.json --md-name bat_cold_start_frontier_full.md --timeout 180",
    "python3 -m src.generate_bat_category_hour_surfaces",
    "python3 -m src.generate_paper_artifacts --bat experiments/results/bat_full_admissible.json --cold-start experiments/results/bat_cold_start_frontier_full.json --warm-start experiments/results/warm_start_suite.json --bridge experiments/results/supported_bridge.json --out-dir experiments/results",
    "python3 -m tests.test_cold_start_frontier",
    "python3 -m tests.test_supported_bridge",
    "python3 -m src.generate_artifact_manifest",
]

SOURCE_FILES = [
    "README.md",
    "requirements.txt",
    "docs/reproducing.md",
    "docs/evaluation.md",
    "docs/figures/idvc-workflow.png",
    "experiments/README.md",
    "experiments/__init__.py",
    "experiments/bat_calibration.py",
    "experiments/supported_bridge.py",
    "experiments/warm_start.py",
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "src").glob("*.py")),
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("*.py")),
]

OUTPUTS = [
    "experiments/results/bat_full_admissible.json",
    "experiments/results/bat_cold_start_frontier_full.json",
    "experiments/results/bat_cold_start_frontier_full.md",
    "experiments/results/supported_bridge.json",
    "experiments/results/supported_bridge.md",
    "experiments/results/warm_start_suite.json",
    "experiments/results/warm_start_suite.md",
    "experiments/results/paper_artifacts.md",
    "experiments/results/bat_category_hour_dual_surface_summary.json",
    "experiments/results/tables/bat_frontier_gate_status.csv",
    "experiments/results/tables/bat_frontier_bootstrap.csv",
    "experiments/results/tables/supported_bridge_gate.csv",
    "experiments/results/tables/supported_bridge_sensitivity.csv",
    "experiments/results/figures/idvc_workflow_surface_panel.pdf",
    "experiments/results/figures/bat_selected_category_hour_dual_surfaces_clean.pdf",
    "experiments/results/figures/warm_start_effect_forest.pdf",
    "experiments/results/figures/mechanism_boundary_panel.pdf",
]


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def command_output(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()
    except Exception:
        return None


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": sys.version.split()[0], "platform": platform.platform()}
    for module in ["numpy", "pandas", "matplotlib", "seaborn"]:
        try:
            mod = __import__(module)
            versions[module] = getattr(mod, "__version__", None)
        except Exception:
            versions[module] = None
    return versions


def json_counts(path: Path) -> dict[str, Any]:
    if not path.exists() or path.suffix != ".json":
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, Any] = {}
    if isinstance(payload, dict):
        out["top_level_keys"] = sorted(payload)[:40]
        if "auctions" in payload and isinstance(payload["auctions"], dict):
            out["auctions"] = {}
            for auction, result in payload["auctions"].items():
                if isinstance(result, dict):
                    out["auctions"][auction] = {
                        "campaigns_loaded": result.get("campaign_report", {}).get("campaigns_loaded")
                        if isinstance(result.get("campaign_report"), dict)
                        else None,
                        "stream_rows_seen": result.get("stream_report", {}).get("rows_seen")
                        if isinstance(result.get("stream_report"), dict)
                        else None,
                        "test_campaigns": result.get("split", {}).get("test")
                        if isinstance(result.get("split"), dict)
                        else None,
                        "gate_pass": result.get("gate_status", {}).get("unchanged_bat_pass")
                        if isinstance(result.get("gate_status"), dict)
                        else None,
                    }
        if "gate_status" in payload and isinstance(payload["gate_status"], dict):
            gate = payload["gate_status"]
            out["bridge_pass"] = gate.get("bridge_pass")
            out["bridge_clusters"] = gate.get("contact_lift_ci", {}).get("clusters") if isinstance(gate.get("contact_lift_ci"), dict) else None
        if "sensitivity" in payload and isinstance(payload["sensitivity"], dict):
            out["sensitivity_all_pass"] = payload["sensitivity"].get("all_pass")
            out["sensitivity_grid"] = payload["sensitivity"].get("grid")
    return out


def main() -> int:
    sources = {}
    for rel in SOURCE_FILES:
        path = ROOT / rel
        sources[rel] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256(path),
        }
    outputs = {}
    for rel in OUTPUTS:
        path = ROOT / rel
        outputs[rel] = {
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
            "sha256": sha256(path),
            "counts": json_counts(path),
        }
    manifest = {
        "generated_by": "src/generate_artifact_manifest.py",
        "git_commit": command_output(["git", "rev-parse", "--short", "HEAD"]),
        "git_status_scope": "source and artifact paths only; local notes/raw data/draft supplements intentionally excluded",
        "git_status_short": command_output(["git", "status", "--short", "--", *sorted(set(SOURCE_FILES + OUTPUTS))]),
        "commands": COMMANDS,
        "versions": package_versions(),
        "sources": sources,
        "outputs": outputs,
    }
    out = ROOT / "experiments/results/artifact_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
