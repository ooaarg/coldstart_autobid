#!/usr/bin/env python3
"""Run public BAT calibration experiments with streaming stats readers.

The default run intentionally uses a bounded stats sample. Pass --full to stream
the full public Hugging Face stats files.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Mapping

from experiment_utils import (
    BatAccumulator,
    bat_row_from_csv,
    ensure_dir,
    fmt,
    iter_csv_rows,
    load_campaign_metadata,
    markdown_table,
    schema_report,
    sniff_columns,
    utc_now,
    write_json,
)


BASE_URL = "https://huggingface.co/datasets/AvitoTech/BAT/resolve/main"
FILES = {
    "vcg": {
        "stats": f"{BASE_URL}/vcg/stats.csv",
        "campaigns": f"{BASE_URL}/vcg/campaigns.csv",
    },
    "fpa": {
        "stats": f"{BASE_URL}/fpa/stats.csv",
        "campaigns": f"{BASE_URL}/fpa/campaigns.csv",
    },
}
LOCAL_DEFAULTS = {
    "vcg": {
        "stats": "experiments/data/bat/raw/vcg/stats.csv",
        "campaigns": "experiments/data/bat/raw/vcg/campaigns.csv",
    },
    "fpa": {
        "stats": "experiments/data/bat/raw/fpa/stats.csv",
        "campaigns": "experiments/data/bat/raw/fpa/campaigns.csv",
    },
}

REQUIRED_STATS_COLUMNS = [
    "campaign_id",
    "item_id",
    "period",
    "contact_price_bin",
    "AuctionVisibilitySurplus",
    "AuctionClicksSurplus",
    "AuctionContactsSurplus",
    "AuctionWinBidSurplus",
    "CTRPredicts",
    "CRPredicts",
    "AuctionCount",
]
OPTIONAL_STATS_COLUMNS = ["x_platfrom_num", "platform_p"]
REQUIRED_CAMPAIGN_COLUMNS = ["campaign_id", "item_id"]
OPTIONAL_CAMPAIGN_COLUMNS = ["logical_category", "microcat_ext", "region_id"]

DEFAULT_SAMPLE_ROWS = 100_000
DEFAULT_CAMPAIGN_ROWS = None


def source_from_args(args: argparse.Namespace, auction: str, kind: str) -> str:
    override = getattr(args, f"{auction}_{kind}")
    if override:
        return override
    local = LOCAL_DEFAULTS[auction][kind]
    if os.path.exists(local):
        return local
    return FILES[auction][kind]


def row_limit(args: argparse.Namespace) -> int | None:
    if args.full:
        return args.max_rows
    if args.max_rows is not None:
        return args.max_rows
    return args.sample_rows


def run_one_auction(
    auction: str,
    stats_source: str,
    campaign_source: str | None,
    max_rows: int | None,
    campaign_max_rows: int | None,
    min_category_rows: int,
    timeout: int,
) -> dict[str, object]:
    stats_columns = sniff_columns(stats_source, timeout=timeout)
    stats_schema = schema_report(stats_columns, REQUIRED_STATS_COLUMNS, OPTIONAL_STATS_COLUMNS)

    campaign_meta: dict[tuple[str, str], dict[str, str]] = {}
    campaign_report: dict[str, object] = {
        "available": False,
        "source": campaign_source,
        "schema": None,
        "load_report": None,
    }
    if campaign_source:
        campaign_columns = sniff_columns(campaign_source, timeout=timeout)
        campaign_schema = schema_report(campaign_columns, REQUIRED_CAMPAIGN_COLUMNS, OPTIONAL_CAMPAIGN_COLUMNS)
        campaign_report["available"] = bool(campaign_schema["valid"])
        campaign_report["schema"] = campaign_schema
        if campaign_schema["valid"]:
            campaign_meta, load_report = load_campaign_metadata(
                campaign_source,
                max_rows=campaign_max_rows,
                timeout=timeout,
            )
            campaign_report["load_report"] = load_report

    acc = BatAccumulator()
    acc.ensure_heldout(min_category_rows=min_category_rows)
    if stats_schema["valid"]:
        for idx, row in enumerate(iter_csv_rows(stats_source, timeout=timeout), start=1):
            bat = bat_row_from_csv(row)
            campaign = campaign_meta.get((bat.campaign_id, bat.item_id)) if campaign_meta else None
            acc.add(bat, campaign=campaign)
            if max_rows is not None and idx >= max_rows:
                break

    result = acc.to_json(min_category_rows=min_category_rows)
    if auction != "fpa" and isinstance(result.get("heldout_baselines"), dict):
        heldout = result["heldout_baselines"]
        heldout["models"] = [
            model
            for model in heldout.get("models", [])
            if not (isinstance(model, dict) and model.get("model") == "fpa_response_proxy")
        ]
    if auction == "fpa":
        result["fpa_response_proxy_diagnostics"] = acc.response_report()
    result.update(
        {
            "auction": auction,
            "stats_source": stats_source,
            "campaign_source": campaign_source,
            "max_rows": max_rows,
            "truncated_stats": max_rows is not None and result["rows_seen"] >= max_rows,
            "schema": stats_schema,
            "campaign_metadata": campaign_report,
        }
    )
    return result


def compact_auction_summary(result: Mapping[str, object]) -> list[object]:
    flat = result.get("flat_ols", {})
    contextual = result.get("contextual_bins", {})
    if not isinstance(flat, Mapping):
        flat = {}
    if not isinstance(contextual, Mapping):
        contextual = {}
    admissible = flat.get("admissible", {})
    if not isinstance(admissible, Mapping):
        admissible = {}
    return [
        result.get("auction"),
        result.get("rows_seen"),
        result.get("usable_rows"),
        fmt(flat.get("beta_v")),
        fmt(flat.get("beta_cpc_mu")),
        fmt(flat.get("tcl_mse")),
        fmt(admissible.get("admissible_beta_v")),
        fmt(admissible.get("admissible_beta_cpc_mu")),
        fmt(admissible.get("admissible_tcl_mse")),
        fmt(contextual.get("contextual_unconstrained_tcl_mse")),
        fmt(contextual.get("contextual_admissible_tcl_mse")),
        fmt(contextual.get("contextual_admissible_tcl_delta")),
        fmt(flat.get("gram_condition_number")),
        contextual.get("bins_used"),
        result.get("campaign_matches"),
    ]


def render_markdown(payload: Mapping[str, object]) -> str:
    auctions = payload.get("auctions", {})
    rows = [
        [
            "auction",
            "rows",
            "usable",
            "proxy s",
            "proxy alpha",
            "proxy TCL",
            "adm. s",
            "adm. alpha",
            "adm. TCL",
            "ctx proxy TCL",
            "ctx adm. TCL",
            "ctx adm. delta",
            "Gram cond.",
            "ctx bins",
            "campaign matches",
        ]
    ]
    if isinstance(auctions, Mapping):
        for key in ("vcg", "fpa"):
            result = auctions.get(key)
            if isinstance(result, Mapping):
                rows.append(compact_auction_summary(result))

    lines = [
        "# BAT Calibration Run",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Mode: `{payload.get('mode')}`",
        f"- Stats row limit: `{payload.get('stats_row_limit')}`",
        f"- Dataset: [AvitoTech/BAT]({BASE_URL})",
        "",
        "## Admissible And Proxy Calibration",
        "",
        markdown_table(rows),
        "",
        "Features are `v = CTRPredicts * CRPredicts` and `contact_price_bin * mu`, with `mu = CTRPredicts`.",
        "`proxy` columns are unconstrained affine least squares and are not called implied-dual fits.",
        "`adm.` columns solve the same squared loss under `s >= 1e-8` and `0 <= alpha <= 1`.",
        "Response is the declared public-BAT proxy `AuctionWinBidSurplus / max(AuctionCount, 1)` with `contact_price_bin` fallback when surplus is unavailable; it is not a raw winning-price target.",
        "Held-out baselines use period-block split `period // 3600 mod 5`, with fold 4 held out.",
        "",
        "## Admissibility Diagnostics",
        "",
    ]

    diag_rows = [
        [
            "auction",
            "s<0 bins",
            "alpha<0 bins",
            "alpha>1 bins",
            "active s-min bins",
            "active alpha=0 bins",
            "active alpha=1 bins",
            "weak cond. bins",
            "singular bins",
        ]
    ]
    if isinstance(auctions, Mapping):
        for key in ("vcg", "fpa"):
            result = auctions.get(key)
            if not isinstance(result, Mapping):
                continue
            contextual = result.get("contextual_bins", {})
            counts = contextual.get("admissibility_violation_counts", {}) if isinstance(contextual, Mapping) else {}
            weak = contextual.get("weak_design_counts", {}) if isinstance(contextual, Mapping) else {}
            if not isinstance(counts, Mapping):
                counts = {}
            if not isinstance(weak, Mapping):
                weak = {}
            diag_rows.append(
                [
                    key,
                    counts.get("unconstrained_s_below_min", 0),
                    counts.get("unconstrained_alpha_below_zero", 0),
                    counts.get("unconstrained_alpha_above_one", 0),
                    counts.get("admissible_active_s_min", 0),
                    counts.get("admissible_active_alpha_min", 0),
                    counts.get("admissible_active_alpha_max", 0),
                    weak.get("condition_gt_1e6", 0),
                    weak.get("condition_missing", 0),
                ]
            )

    lines.extend(
        [
            markdown_table(diag_rows),
            "",
        "## Schema And Availability",
        "",
        ]
    )

    if isinstance(auctions, Mapping):
        for key in ("vcg", "fpa"):
            result = auctions.get(key)
            if not isinstance(result, Mapping):
                continue
            schema = result.get("schema", {})
            campaign = result.get("campaign_metadata", {})
            missing_required = schema.get("missing_required") if isinstance(schema, Mapping) else []
            missing_optional = schema.get("missing_optional") if isinstance(schema, Mapping) else []
            lines.extend(
                [
                    f"### {str(key).upper()}",
                    "",
                    f"- Required stats columns missing: `{missing_required}`",
                    f"- Optional stats columns missing: `{missing_optional}`",
                    f"- Campaign metadata available: `{campaign.get('available') if isinstance(campaign, Mapping) else None}`",
                    f"- Truncated stats stream: `{result.get('truncated_stats')}`",
                    "",
                ]
            )

    fpa = auctions.get("fpa") if isinstance(auctions, Mapping) else None
    lines.extend(["## Held-Out Baselines", ""])
    heldout_rows = [["auction", "model", "test rows", "test TCL", "context SE", "blocks"]]
    if isinstance(auctions, Mapping):
        for key in ("vcg", "fpa"):
            result = auctions.get(key)
            if not isinstance(result, Mapping):
                continue
            heldout = result.get("heldout_baselines")
            if not isinstance(heldout, Mapping):
                continue
            for model in heldout.get("models", []):
                if not isinstance(model, Mapping):
                    continue
                heldout_rows.append(
                    [
                        key,
                        model.get("model"),
                        model.get("test_rows"),
                        fmt(model.get("test_tcl_mse")),
                        fmt(model.get("context_block_se")),
                        model.get("context_blocks"),
                    ]
                )
    if len(heldout_rows) > 1:
        lines.extend([markdown_table(heldout_rows), ""])
    else:
        lines.extend(["No held-out baselines were available.", ""])

    if isinstance(fpa, Mapping) and "fpa_response_proxy_diagnostics" in fpa:
        diag = fpa["fpa_response_proxy_diagnostics"]
        if isinstance(diag, Mapping):
            proxy = diag.get("proxy_fit", {})
            lines.extend(
                [
                    "## FPA Response Proxy Diagnostics",
                    "",
                    f"- Proxy fit TCL MSE: `{fmt(proxy.get('tcl_mse') if isinstance(proxy, Mapping) else None)}`",
                    f"- Proxy features: `{diag.get('proxy_features')}`",
                    f"- Proxy target: `{diag.get('proxy_target')}`",
                    f"- Mean `y / contact_price_bin`: `{fmt(diag.get('y_over_contact_price_bin_mean'))}`",
                    f"- Median `y / contact_price_bin`: `{fmt(diag.get('y_over_contact_price_bin_median'))}`",
                    f"- Ratio sample count: `{diag.get('ratio_sample_count')}`",
                    "",
                    str(diag.get("interpretation")),
                    "",
                ]
            )

    lines.extend(
        [
            "## Data Request Status",
            "",
            "No private data was required for this run. Public BAT CSVs were used first.",
            "Private/platform logs would only be needed for uncensored thresholds, exact payment-rule metadata, or production regime labels.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="experiments/results")
    parser.add_argument("--json-name", default="bat_calibration.json")
    parser.add_argument("--md-name", default="bat_calibration.md")
    parser.add_argument("--sample-rows", type=int, default=DEFAULT_SAMPLE_ROWS)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--full", action="store_true", help="Stream all stats rows unless --max-rows is also supplied.")
    parser.add_argument("--min-category-rows", type=int, default=500)
    parser.add_argument("--campaign-max-rows", type=int, default=DEFAULT_CAMPAIGN_ROWS)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--only", choices=["both", "vcg", "fpa"], default="both")
    parser.add_argument("--vcg-stats")
    parser.add_argument("--vcg-campaigns")
    parser.add_argument("--fpa-stats")
    parser.add_argument("--fpa-campaigns")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    limit = row_limit(args)
    selected = ["vcg", "fpa"] if args.only == "both" else [args.only]
    payload: dict[str, object] = {
        "generated_at_utc": utc_now(),
        "mode": "full" if args.full and args.max_rows is None else "bounded",
        "stats_row_limit": limit,
        "min_category_rows": args.min_category_rows,
        "base_url": BASE_URL,
        "auctions": {},
    }

    for auction in selected:
        stats_source = source_from_args(args, auction, "stats")
        campaign_source = source_from_args(args, auction, "campaigns")
        payload["auctions"][auction] = run_one_auction(
            auction=auction,
            stats_source=stats_source,
            campaign_source=campaign_source,
            max_rows=limit,
            campaign_max_rows=args.campaign_max_rows,
            min_category_rows=args.min_category_rows,
            timeout=args.timeout,
        )

    ensure_dir(args.out_dir)
    json_path = os.path.join(args.out_dir, args.json_name)
    md_path = os.path.join(args.out_dir, args.md_name)
    write_json(json_path, payload)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(payload))
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
