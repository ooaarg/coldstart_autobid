#!/usr/bin/env python3
"""Check public BAT availability and record download/load status.

This script deliberately starts with standard-library Hugging Face API checks
so access can be verified before installing heavy dependencies. If the optional
`datasets` package is installed, it also attempts to inspect the dataset
builder configuration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


HF_DATASET = "AvitoTech/BAT"
HF_API_URL = f"https://huggingface.co/api/datasets/{HF_DATASET}"
EXPECTED_SUBSETS = ["fpa_campaigns", "fpa_stats", "vcg_campaigns", "vcg_stats"]


def fetch_hf_metadata(timeout: int) -> dict[str, object]:
    req = urllib.request.Request(HF_API_URL, headers={"User-Agent": "codex-bat-check/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def optional_datasets_probe() -> dict[str, object]:
    try:
        from datasets import get_dataset_config_names  # type: ignore
    except Exception as exc:  # pragma: no cover - environment dependent
        return {
            "available": False,
            "error": f"datasets package unavailable: {exc}",
            "configs": [],
        }
    try:
        configs = get_dataset_config_names(HF_DATASET)
        return {
            "available": True,
            "error": None,
            "configs": configs,
        }
    except Exception as exc:  # pragma: no cover - network dependent
        return {
            "available": False,
            "error": f"datasets config probe failed: {exc}",
            "configs": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/results/bat_access.json")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    status: dict[str, object] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": HF_DATASET,
        "api_url": HF_API_URL,
        "expected_subsets": EXPECTED_SUBSETS,
        "metadata_accessible": False,
        "metadata_error": None,
        "siblings": [],
        "card_data": {},
        "datasets_probe": {},
        "minimum_private_data_request": None,
    }

    try:
        meta = fetch_hf_metadata(args.timeout)
        status["metadata_accessible"] = True
        status["siblings"] = [s.get("rfilename") for s in meta.get("siblings", []) if s.get("rfilename")]
        status["card_data"] = meta.get("cardData", {})
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        status["metadata_error"] = str(exc)
        status["minimum_private_data_request"] = (
            "Need BAT VCG/FPA logs with campaign-level values, bids or payments, "
            "winning thresholds/prices where available, and auction-format metadata."
        )

    status["datasets_probe"] = optional_datasets_probe()
    configs = status["datasets_probe"].get("configs", []) if isinstance(status["datasets_probe"], dict) else []
    missing = sorted(set(EXPECTED_SUBSETS) - set(configs))
    status["expected_subsets_seen_by_datasets"] = sorted(set(EXPECTED_SUBSETS).intersection(configs))
    status["expected_subsets_missing_by_datasets"] = missing
    if missing and status["metadata_accessible"]:
        status["note"] = (
            "Metadata is reachable. Install requirements.txt and run the full "
            "loader to inspect split names and schema; missing configs here may reflect an "
            "older datasets client or dataset-card naming."
        )

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(status, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0 if status["metadata_accessible"] else 2


if __name__ == "__main__":
    sys.exit(main())
