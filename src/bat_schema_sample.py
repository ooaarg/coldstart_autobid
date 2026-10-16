#!/usr/bin/env python3
"""Fetch small public BAT CSV samples without downloading the full dataset."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import urllib.request
from datetime import datetime, timezone


BASE_URL = "https://huggingface.co/datasets/AvitoTech/BAT/resolve/main"
FILES = {
    "fpa_campaigns": "fpa/campaigns.csv",
    "fpa_stats": "fpa/stats.csv",
    "vcg_campaigns": "vcg/campaigns.csv",
    "vcg_stats": "vcg/stats.csv",
}


def fetch_prefix(path: str, max_bytes: int) -> tuple[bytes, dict[str, str]]:
    url = f"{BASE_URL}/{path}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "codex-bat-schema-sample/1.0",
            "Range": f"bytes=0-{max_bytes - 1}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(max_bytes)
        headers = {k.lower(): v for k, v in resp.headers.items()}
    return data, headers


def parse_sample(data: bytes, max_rows: int) -> dict[str, object]:
    text = data.decode("utf-8", errors="replace")
    # Keep only complete lines to avoid parsing a truncated final record.
    lines = text.splitlines()
    if not lines:
        return {"columns": [], "rows": [], "line_count_in_prefix": 0}
    reader = csv.DictReader(io.StringIO("\n".join(lines[:-1] if len(lines) > 1 else lines)))
    rows = []
    for idx, row in enumerate(reader):
        if idx >= max_rows:
            break
        rows.append(row)
    return {
        "columns": reader.fieldnames or [],
        "rows": rows,
        "line_count_in_prefix": len(lines),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiments/results/bat_schema_sample.json")
    parser.add_argument("--bytes", type=int, default=131072)
    parser.add_argument("--rows", type=int, default=3)
    args = parser.parse_args()

    result: dict[str, object] = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "max_bytes_per_file": args.bytes,
        "files": {},
    }

    file_results: dict[str, object] = {}
    for name, path in FILES.items():
        try:
            prefix, headers = fetch_prefix(path, args.bytes)
            parsed = parse_sample(prefix, args.rows)
            file_results[name] = {
                "path": path,
                "status": "ok",
                "content_length_header": headers.get("content-length"),
                "content_range_header": headers.get("content-range"),
                "linked_size_header": headers.get("x-linked-size"),
                "bytes_read": len(prefix),
                **parsed,
            }
        except Exception as exc:  # pragma: no cover - network dependent
            file_results[name] = {
                "path": path,
                "status": "error",
                "error": str(exc),
            }
    result["files"] = file_results

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
