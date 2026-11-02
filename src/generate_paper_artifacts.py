#!/usr/bin/env python3
"""Generate paper-ready tables and plots from BAT/synthetic result JSON."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from src.plots import plot_bat_loss, plot_warm_start_errors, plot_warm_start_effect_forest, warm_start_effects
from src.model_figure import plot_idvc_workflow_surface_panel


MIN_BOOTSTRAP_CLUSTERS = 30
PRIMARY_FRONTIER_POLICY = "shrunk_contextual_idvc"


def fmt(x: Any, digits: int = 4) -> str:
    if x is None:
        return "NA"
    if isinstance(x, float):
        if not math.isfinite(x):
            return "NA"
        if x == 0:
            return "0"
        if abs(x) < 1e-3 or abs(x) >= 1e4:
            return f"{x:.{digits}e}"
        return f"{x:.{digits}f}"
    return str(x)


def latex_escape(value: Any) -> str:
    text = fmt(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def latex_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    spec = "l" * len(cols)
    lines = [rf"\begin{{tabular}}{{{spec}}}", r"\toprule"]
    lines.append(" & ".join(latex_escape(col) for col in cols) + r" \\")
    lines.append(r"\midrule")
    for row in df.itertuples(index=False, name=None):
        lines.append(" & ".join(latex_escape(value) for value in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabular}", ""])
    return "\n".join(lines)


def write_table(df: pd.DataFrame, stem: str, tables_dir: Path) -> None:
    csv_path = tables_dir / f"{stem}.csv"
    tex_path = tables_dir / f"{stem}.tex"
    df.to_csv(csv_path, index=False)
    tex_path.write_text(latex_table(df), encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    """Render a small markdown table without optional pandas tabulate dependency."""
    if df.empty:
        return "_No rows._"
    text_df = df.fillna("NA").astype(str)
    headers = list(text_df.columns)
    widths = [len(h) for h in headers]
    for row in text_df.itertuples(index=False, name=None):
        widths = [max(widths[i], len(str(value))) for i, value in enumerate(row)]
    header = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    rows = [
        "| " + " | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)) + " |"
        for row in text_df.itertuples(index=False, name=None)
    ]
    return "\n".join([header, sep, *rows])


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text())


def bat_summary_tables(bat: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    gram_rows = []
    cat_rows = []
    response_rows = []
    for auction, result in bat["auctions"].items():
        flat = result.get("flat_ols", {})
        ctx = result.get("contextual_bins", {})
        flat_adm = flat.get("admissible", {}) if isinstance(flat, dict) else {}
        counts = ctx.get("admissibility_violation_counts", {}) if isinstance(ctx, dict) else {}
        rows.append(
            {
                "auction": auction.upper(),
                "rows_seen": result.get("rows_seen"),
                "usable_rows": result.get("usable_rows"),
                "campaign_matches": result.get("campaign_matches"),
                "flat_proxy_tcl": flat.get("tcl_mse"),
                "flat_admissible_tcl": flat_adm.get("admissible_tcl_mse") if isinstance(flat_adm, dict) else None,
                "contextual_proxy_tcl": ctx.get("contextual_unconstrained_tcl_mse", ctx.get("contextual_tcl_mse")),
                "contextual_admissible_tcl": ctx.get("contextual_admissible_tcl_mse"),
                "contextual_admissible_delta": ctx.get("contextual_admissible_tcl_delta"),
                "flat_tcl": flat.get("tcl_mse"),
                "contextual_tcl": ctx.get("contextual_tcl_mse"),
                "contextual_rows": ctx.get("contextual_rows"),
                "context_bins": ctx.get("bins_used"),
                "s_violation_bins": counts.get("unconstrained_s_below_min") if isinstance(counts, dict) else None,
                "alpha_hi_violation_bins": counts.get("unconstrained_alpha_above_one") if isinstance(counts, dict) else None,
                "gram_condition": flat.get("gram_condition_number"),
                "truncated": result.get("truncated_stats"),
            }
        )
        gram_rows.append(
            {
                "auction": auction.upper(),
                "scope": "flat",
                "n": flat.get("n"),
                "gram_lambda_min": flat.get("gram_lambda_min"),
                "gram_condition": flat.get("gram_condition_number"),
            }
        )
        for item in ctx.get("top_bins", []) + ctx.get("used_bins", []):
            if not isinstance(item, dict):
                continue
            cat_rows.append(
                {
                    "auction": auction.upper(),
                    "category": item.get("category"),
                    "n": item.get("n"),
                    "tcl_mse": item.get("tcl_mse"),
                    "admissible_tcl_mse": (
                        item.get("admissible", {}).get("admissible_tcl_mse")
                        if isinstance(item.get("admissible"), dict)
                        else None
                    ),
                    "r2": item.get("r2"),
                    "gram_condition": item.get("gram_condition_number"),
                    "beta_v": item.get("beta_v"),
                    "beta_cpc_mu": item.get("beta_cpc_mu"),
                    "admissible_beta_v": (
                        item.get("admissible", {}).get("admissible_beta_v")
                        if isinstance(item.get("admissible"), dict)
                        else None
                    ),
                    "admissible_beta_cpc_mu": (
                        item.get("admissible", {}).get("admissible_beta_cpc_mu")
                        if isinstance(item.get("admissible"), dict)
                        else None
                    ),
                }
            )
        diag = result.get("fpa_response_proxy_diagnostics")
        if isinstance(diag, dict):
            summary = diag.get("ratio_summary", {})
            response_rows.append(
                {
                    "auction": auction.upper(),
                    "proxy_tcl": diag.get("proxy_fit", {}).get("tcl_mse"),
                    "ratio_count": diag.get("ratio_sample_count"),
                    "ratio_mean": diag.get("y_over_contact_price_bin_mean"),
                    "ratio_median": diag.get("y_over_contact_price_bin_median"),
                    "ratio_p95": summary.get("p95"),
                    "platform_rows": result.get("platform_rows"),
                }
            )
    return (
        pd.DataFrame(rows),
        pd.DataFrame(gram_rows),
        pd.DataFrame(cat_rows).drop_duplicates(),
        pd.DataFrame(response_rows),
    )


def synthetic_table(synth: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for exp in synth.get("experiments", []):
        metrics = exp.get("metrics", {})
        key_metrics = "; ".join(f"{k}={fmt(v, 3)}" for k, v in list(metrics.items())[:4])
        rows.append(
            {
                "question": exp.get("question"),
                "status": "PASS" if exp.get("pass") else "CHECK",
                "name": exp.get("name"),
                "key_metrics": key_metrics,
            }
        )
    return pd.DataFrame(rows)


def cold_start_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        cold_start = result.get("cold_start", {}) if isinstance(result, dict) else {}
        for horizon, hres in cold_start.items():
            policies = hres.get("policies", {}) if isinstance(hres, dict) else {}
            for policy, metrics in policies.items():
                if not isinstance(metrics, dict):
                    continue
                rows.append(
                    {
                        "auction": str(auction).upper(),
                        "horizon": horizon,
                        "policy": policy,
                        "campaigns": metrics.get("campaigns"),
                        "contacts": metrics.get("contacts"),
                        "clicks": metrics.get("clicks"),
                        "spend": metrics.get("spend"),
                        "budget_violation": metrics.get("budget_violation_area"),
                        "budget_utilization": metrics.get("budget_utilization"),
                        "cost_per_contact": metrics.get("cost_per_contact"),
                        "contact_lift_vs_hist": metrics.get("contact_lift_vs_historical_stationary"),
                    }
                )
    return pd.DataFrame(rows)


def bat_cold_start_auc_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        cold_start = result.get("cold_start", {}) if isinstance(result, dict) else {}
        auc = cold_start.get("early_auc_fixed_horizons", {}) if isinstance(cold_start, dict) else {}
        if not isinstance(auc, dict):
            continue
        for policy, metrics in auc.items():
            if not isinstance(metrics, dict):
                continue
            rows.append(
                {
                    "auction": str(auction).upper(),
                    "policy": policy,
                    "fixed_horizons": metrics.get("fixed_horizons"),
                    "contacts_early_auc": metrics.get("contacts_early_auc"),
                    "contacts_early_auc_lift_vs_hist": metrics.get("contacts_early_auc_lift_vs_historical"),
                    "budget_violation_auc": metrics.get("budget_violation_auc"),
                    "budget_utilization_auc": metrics.get("budget_utilization_auc"),
                    "cost_per_contact_auc": metrics.get("cost_per_contact_auc"),
                }
            )
    return pd.DataFrame(rows)


def bat_frontier_selection_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        selected = result.get("selected_policy_scales", {}) if isinstance(result, dict) else {}
        if not isinstance(selected, dict):
            continue
        for policy, meta in selected.items():
            if not isinstance(meta, dict):
                continue
            rows.append(
                {
                    "auction": str(auction).upper(),
                    "policy": policy,
                    "scale": meta.get("scale"),
                    "selected_feasible": meta.get("selected_from_feasible_set"),
                    "validation_auc": meta.get("validation_contacts_early_auc"),
                    "validation_violation_auc": meta.get("validation_budget_violation_auc"),
                    "allowed_violation_auc": meta.get("allowed_budget_violation_auc"),
                }
            )
    return pd.DataFrame(rows)


def bat_frontier_bootstrap_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        selected = result.get("frontier_selected_test", {}) if isinstance(result, dict) else {}
        boot = selected.get("paired_bootstrap_vs_historical", {}) if isinstance(selected, dict) else {}
        policies = boot.get("policies", {}) if isinstance(boot, dict) else {}
        gate = result.get("gate_status", {}) if isinstance(result, dict) else {}
        if not isinstance(policies, dict):
            continue
        for policy, metrics in policies.items():
            if not isinstance(metrics, dict):
                continue
            lift = metrics.get("contact_lift", {})
            violation = metrics.get("budget_violation_auc_diff", {})
            utilization = metrics.get("budget_utilization_auc_diff", {})
            clusters = lift.get("n") if isinstance(lift, dict) else None
            enough = isinstance(clusters, int) and clusters >= MIN_BOOTSTRAP_CLUSTERS
            rows.append(
                {
                    "auction": str(auction).upper(),
                    "policy": policy,
                    "evidentiary_run": gate.get("evidentiary_run") if isinstance(gate, dict) else None,
                    "clusters": clusters,
                    "min_clusters": MIN_BOOTSTRAP_CLUSTERS,
                    "resamples": boot.get("resamples") if isinstance(boot, dict) else None,
                    "contact_lift_mean": lift.get("mean") if isinstance(lift, dict) else None,
                    "contact_lift_lo": lift.get("lo") if enough and isinstance(lift, dict) else "NA_insufficient_clusters",
                    "contact_lift_hi": lift.get("hi") if enough and isinstance(lift, dict) else "NA_insufficient_clusters",
                    "violation_diff_mean": violation.get("mean") if isinstance(violation, dict) else None,
                    "violation_diff_lo": violation.get("lo") if enough and isinstance(violation, dict) else "NA_insufficient_clusters",
                    "violation_diff_hi": violation.get("hi") if enough and isinstance(violation, dict) else "NA_insufficient_clusters",
                    "utilization_diff_mean": utilization.get("mean") if isinstance(utilization, dict) else None,
                    "ineligible_reason": gate.get("ineligible_reason") if isinstance(gate, dict) else None,
                }
            )
    return pd.DataFrame(rows)


def bat_gate_status_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        gate = result.get("gate_status", {}) if isinstance(result, dict) else {}
        if not isinstance(gate, dict):
            continue
        rows.append(
            {
                "auction": str(auction).upper(),
                "evidentiary_run": gate.get("evidentiary_run"),
                "primary_policy": gate.get("primary_policy"),
                "primary_comparator": gate.get("primary_comparator"),
                "unchanged_bat_pass": gate.get("unchanged_bat_pass"),
                "endpoint_ci_ok": gate.get("endpoint_lower_ci_positive"),
                "constraint_ci_ok": gate.get("constraint_upper_ci_nonpositive"),
                "clusters": gate.get("bootstrap_clusters"),
                "min_clusters": gate.get("minimum_bootstrap_clusters"),
                "consequence": gate.get("required_manuscript_consequence"),
            }
        )
    return pd.DataFrame(rows)


def bat_support_replay_table(cold: dict[str, Any] | None) -> pd.DataFrame:
    if not cold:
        return pd.DataFrame()
    rows = []
    for auction, result in cold.get("auctions", {}).items():
        selected = result.get("frontier_selected_test", {}) if isinstance(result, dict) else {}
        if not isinstance(selected, dict):
            continue
        for horizon in ["first_period", "first_3", "first_6", "first_12", "first_24"]:
            hres = selected.get(horizon, {})
            strata = hres.get("support_strata", {}) if isinstance(hres, dict) else {}
            if not isinstance(strata, dict):
                continue
            for stratum, policies in strata.items():
                if not isinstance(policies, dict):
                    continue
                for policy, metrics in policies.items():
                    if not isinstance(metrics, dict):
                        continue
                    rows.append(
                        {
                            "auction": str(auction).upper(),
                            "horizon": horizon,
                            "stratum": stratum,
                            "policy": policy,
                            "support_bucket_rule": "low<500; medium<=5000; high>5000; weak cond missing/>1e5",
                            "campaigns": metrics.get("campaigns"),
                            "fallbacks": hres.get("fallback_decisions", {}).get(policy) if isinstance(hres.get("fallback_decisions"), dict) else None,
                            "contacts": metrics.get("contacts"),
                            "contact_lift_vs_hist": metrics.get("contact_lift_vs_historical_stationary"),
                            "budget_violation": metrics.get("budget_violation_area"),
                            "budget_utilization": metrics.get("budget_utilization"),
                        }
                    )
    return pd.DataFrame(rows)


def supported_bridge_summary_table(bridge: dict[str, Any] | None) -> pd.DataFrame:
    if not bridge:
        return pd.DataFrame()
    rows = bridge.get("summary", [])
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def supported_bridge_gate_table(bridge: dict[str, Any] | None) -> pd.DataFrame:
    if not bridge:
        return pd.DataFrame()
    gate = bridge.get("gate_status", {})
    if not isinstance(gate, dict):
        return pd.DataFrame()
    lift = gate.get("contact_lift_ci", {})
    violation = gate.get("violation_diff_ci", {})
    return pd.DataFrame(
        [
            {
                "bridge_pass": gate.get("bridge_pass"),
                "primary_policy": gate.get("primary_policy"),
                "primary_comparator": gate.get("primary_comparator"),
                "primary_scenarios": ",".join(gate.get("primary_scenarios", [])),
                "clusters": lift.get("clusters") if isinstance(lift, dict) else None,
                "scenario_pairs": lift.get("scenario_pairs") if isinstance(lift, dict) else None,
                "min_clusters": gate.get("minimum_bootstrap_clusters"),
                "contact_lift_mean": lift.get("mean") if isinstance(lift, dict) else None,
                "contact_lift_lo": lift.get("lo") if isinstance(lift, dict) else None,
                "contact_lift_hi": lift.get("hi") if isinstance(lift, dict) else None,
                "violation_diff_mean": violation.get("mean") if isinstance(violation, dict) else None,
                "violation_diff_hi": violation.get("hi") if isinstance(violation, dict) else None,
                "mismatch_abstention_rate": gate.get("mismatch_abstention_rate"),
                "negative_controls_pass": gate.get("negative_controls", {}).get("pass") if isinstance(gate.get("negative_controls"), dict) else None,
                "claim_boundary": bridge.get("claim_boundary"),
                "uncertainty_scope": gate.get("uncertainty_scope"),
                "consequence": gate.get("required_manuscript_consequence"),
            }
        ]
    )


def supported_bridge_sensitivity_table(bridge: dict[str, Any] | None) -> pd.DataFrame:
    if not bridge:
        return pd.DataFrame()
    sensitivity = bridge.get("sensitivity", {})
    rows = sensitivity.get("rows", []) if isinstance(sensitivity, dict) else []
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def warm_start_summary_table(warm: dict[str, Any] | None) -> pd.DataFrame:
    if not warm:
        return pd.DataFrame()
    rows = warm.get("summary", {}).get("by_scenario_initialization", [])
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def warm_start_oracle_gap_table(warm: dict[str, Any] | None) -> pd.DataFrame:
    summary = warm_start_summary_table(warm)
    if summary.empty:
        return pd.DataFrame()
    keep = summary[summary["initialization"].isin(["historical_stationary", "contextual_idvc", "response_idvc", "shrunk_idvc", "oracle_init"])]
    return keep[
        [
            "scenario",
            "initialization",
            "reward_h_mean",
            "early_auc_mean",
            "early_auc_lift_vs_historical",
            "oracle_gap_mean",
            "distance_to_oracle_state_mean",
        ]
    ].copy()


def warm_start_negative_transfer_table(warm: dict[str, Any] | None) -> pd.DataFrame:
    if not warm:
        return pd.DataFrame()
    rows = warm.get("summary", {}).get("negative_transfer", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["abstention_accuracy"] = warm.get("summary", {}).get("abstention_accuracy")
    return df


def warm_start_effect_display(effects: pd.DataFrame) -> pd.DataFrame:
    if effects.empty:
        return pd.DataFrame()
    rows = []
    labels = {
        "contextual_idvc": "Contextual IDVC",
        "shrunk_idvc": "Guarded IDVC",
        "response_idvc": "Response-IDVC",
    }
    for row in effects.to_dict(orient="records"):
        lift = row.get("lift_pct")
        lo = row.get("lift_ci_lo")
        hi = row.get("lift_ci_hi")
        rows.append(
            {
                "Setting": row.get("setting"),
                "IDVC variant": labels.get(str(row.get("variant")), row.get("variant")),
                "Comparator": row.get("comparator"),
                "Early-AUC lift (95% CI)": (
                    f"{lift:+.2f}% [{lo:+.2f}, {hi:+.2f}]"
                    if lift is not None and lo is not None and hi is not None
                    else "NA"
                ),
                "TTT change": f"{row.get('ttt_delta'):+.1f}" if row.get("ttt_delta") is not None else "NA",
                "Violation change": f"{row.get('violation_delta'):+.3f}" if row.get("violation_delta") is not None else "NA",
                "n": row.get("n"),
            }
        )
    return pd.DataFrame(rows)


def heldout_table(bat: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for auction, result in bat.get("auctions", {}).items():
        heldout = result.get("heldout_baselines", {})
        split = heldout.get("split", {}) if isinstance(heldout, dict) else {}
        models = heldout.get("models", []) if isinstance(heldout, dict) else []
        for model in models:
            if not isinstance(model, dict):
                continue
            rows.append(
                {
                    "auction": auction.upper(),
                    "model": model.get("model"),
                    "test_rows": model.get("test_rows"),
                    "test_tcl": model.get("test_tcl_mse"),
                    "context_se": model.get("context_block_se"),
                    "blocks": model.get("context_blocks"),
                    "split": split.get("method"),
                }
            )
    return pd.DataFrame(rows)


def support_stratified_heldout_table(bat: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for auction, result in bat.get("auctions", {}).items():
        heldout = result.get("heldout_baselines", {})
        strata = heldout.get("support_stratified", []) if isinstance(heldout, dict) else []
        for item in strata:
            if not isinstance(item, dict):
                continue
            model = item.get("model")
            if model == "fpa_response_proxy" and str(auction).lower() != "fpa":
                continue
            rows.append(
                {
                    "auction": str(auction).upper(),
                    "model": model,
                    "support_scope": item.get("support_scope"),
                    "support_bucket": item.get("support_bucket"),
                    "test_rows": item.get("test_rows"),
                    "test_tcl": item.get("test_tcl_mse"),
                    "context_se": item.get("context_block_se"),
                    "context_blocks": item.get("context_blocks"),
                    "fallback_blocks": item.get("fallback_blocks"),
                }
            )
    return pd.DataFrame(rows)


def target_construction_table(bat: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for auction, result in bat.get("auctions", {}).items():
        flat = result.get("flat_ols", {})
        ctx = result.get("contextual_bins", {})
        y_sources = result.get("y_sources", {})
        skipped = result.get("skipped_rows", {})
        skipped_text = "; ".join(f"{k}={v}" for k, v in sorted(skipped.items())) or "none"
        rows.append(
            {
                "auction": auction.upper(),
                "y": "AuctionWinBidSurplus/max(AuctionCount,1)",
                "v": "CTRPredicts*CRPredicts",
                "Cmu": "contact_price_bin*CTRPredicts",
                "fallback": "contact_price_bin only if win-bid surplus unavailable",
                "exclusions": skipped_text,
                "scanned": result.get("rows_seen"),
                "usable": result.get("usable_rows"),
                "win_bid_y": y_sources.get("win_bid_per_auction"),
                "fallback_y": y_sources.get("contact_price_bin_fallback", 0),
                "ctx_bins": ctx.get("bins_used"),
                "gram_cond": flat.get("gram_condition_number"),
            }
        )
    return pd.DataFrame(rows)


def synthetic_metrics(synth: dict[str, Any], question: str) -> dict[str, Any]:
    for exp in synth.get("experiments", []):
        if exp.get("question") == question:
            return exp.get("metrics", {})
    return {}


def core_evidence_table(bat: dict[str, Any], synth: dict[str, Any]) -> pd.DataFrame:
    fpa = bat["auctions"]["fpa"]
    vcg = bat["auctions"]["vcg"]
    fpa_diag = fpa.get("fpa_response_proxy_diagnostics", {})
    q01 = synthetic_metrics(synth, "Q01")
    q02 = synthetic_metrics(synth, "Q02")
    q05 = synthetic_metrics(synth, "Q05")
    q07 = synthetic_metrics(synth, "Q07")
    q09 = synthetic_metrics(synth, "Q09")
    q10 = synthetic_metrics(synth, "Q10")
    return pd.DataFrame(
        [
            {
                "claim": "BAT VCG proxy calibration",
                "evidence": f"{vcg.get('rows_seen', 0):,} rows; {vcg.get('usable_rows', 0):,} usable",
                "result": (
                    f"adm. TCL {fmt(vcg['flat_ols'].get('admissible', {}).get('admissible_tcl_mse'), 2)}"
                    f" -> {fmt(vcg['contextual_bins'].get('contextual_admissible_tcl_mse'), 2)}"
                ),
                "takeaway": "reported as public-BAT proxy diagnostics, not raw winning-price evidence",
            },
            {
                "claim": "BAT FPA proxy calibration",
                "evidence": f"{fpa.get('rows_seen', 0):,} rows; {fpa['contextual_bins'].get('bins_used', 0)} contexts",
                "result": (
                    f"adm. TCL {fmt(fpa['flat_ols'].get('admissible', {}).get('admissible_tcl_mse'), 2)}"
                    f" -> {fmt(fpa['contextual_bins'].get('contextual_admissible_tcl_mse'), 2)}"
                ),
                "takeaway": "admissibility is explicit; unconstrained affine fits remain proxy baselines",
            },
            {
                "claim": "FPA response layer",
                "evidence": f"{fpa_diag.get('ratio_sample_count', 0):,} ratio rows",
                "result": f"proxy TCL {fmt(fpa_diag.get('proxy_fit', {}).get('tcl_mse'), 2)}",
                "takeaway": f"ratio median {fmt(fpa_diag.get('y_over_contact_price_bin_median'), 3)}, p95 {fmt(fpa_diag.get('ratio_summary', {}).get('p95'), 3)}",
            },
            {
                "claim": "Monotone inversion",
                "evidence": "synthetic FPA + hybrid",
                "result": f"min margins {fmt(q01.get('fpa_min_derivative_margin'), 3)} / {fmt(q01.get('hybrid_min_derivative_margin'), 3)}",
                "takeaway": "zero smooth-regime violations; floor-mix stress 0.013",
            },
            {
                "claim": "Rank-one diagnostic",
                "evidence": "synthetic Hessian sweep",
                "result": f"oracle {fmt(q02.get('oracle_rank_ratio_median'), 3)}, alt. {fmt(q02.get('alternative_rank_ratio_median'), 3)}",
                "takeaway": f"smoothing lowers noisy ratio to {fmt(q02.get('heavy_noise_smoothed_rank_ratio_median'), 3)}",
            },
            {
                "claim": "Hybrid identifiability",
                "evidence": "known-rule vs hidden-rule",
                "result": f"composite RMSE {fmt(q07.get('unknown_composite_rmse'), 3)}",
                "takeaway": "components need rule metadata",
            },
            {
                "claim": "Generated regressors",
                "evidence": "cross-fit vs same-fold",
                "result": f"L2 {fmt(q05.get('crossfit_beta_l2_mean'), 3)} vs {fmt(q05.get('samefold_beta_l2_mean'), 3)}",
                "takeaway": f"same-fold bias x{fmt(q05.get('samefold_bias_ratio'), 2)}",
            },
            {
                "claim": "Deployment extensions",
                "evidence": "pacing + cold-start synthetic",
                "result": f"TTT gain {q09.get('time_to_target_gain')}; EB regret {fmt(q10.get('related_eb_regret_ratio'), 3)}",
                "takeaway": f"mismatch regret {fmt(q10.get('mismatched_eb_regret_ratio'), 3)}",
            },
        ]
    )


def render_report(
    summary: pd.DataFrame,
    response: pd.DataFrame,
    cold_start: pd.DataFrame,
    cold_start_auc: pd.DataFrame,
    heldout: pd.DataFrame,
    target: pd.DataFrame,
    synth_df: pd.DataFrame,
    warm_start: pd.DataFrame,
    warm_oracle_gap: pd.DataFrame,
    warm_negative_transfer: pd.DataFrame,
    warm_effects: pd.DataFrame,
    core_df: pd.DataFrame,
    frontier_selection: pd.DataFrame,
    frontier_bootstrap: pd.DataFrame,
    frontier_gate: pd.DataFrame,
    frontier_support: pd.DataFrame,
    bridge_summary: pd.DataFrame,
    bridge_gate: pd.DataFrame,
    bridge_sensitivity: pd.DataFrame,
    out: Path,
) -> None:
    lines = [
        "# Paper Artifact Summary",
        "",
        "## Core Evidence Summary",
        "",
        markdown_table(core_df),
        "",
        "## BAT Calibration",
        "",
        markdown_table(summary),
        "",
        "## BAT Cold-Start Campaign Replay",
        "",
        markdown_table(cold_start) if len(cold_start) else "No cold-start campaign replay was supplied.",
        "",
        "## BAT Cold-Start Early-AUC",
        "",
        markdown_table(cold_start_auc) if len(cold_start_auc) else "No BAT early-AUC replay was supplied.",
        "",
        "## BAT Frontier Selection",
        "",
        markdown_table(frontier_selection) if len(frontier_selection) else "No BAT frontier-selection diagnostics were supplied.",
        "",
        "## BAT Frontier Bootstrap",
        "",
        markdown_table(frontier_bootstrap) if len(frontier_bootstrap) else "No BAT frontier bootstrap diagnostics were supplied.",
        "",
        "## BAT Frontier Gate Status",
        "",
        markdown_table(frontier_gate) if len(frontier_gate) else "No BAT frontier gate status was supplied.",
        "",
        "## BAT Frontier Support Replay",
        "",
        markdown_table(frontier_support) if len(frontier_support) else "No BAT frontier support replay was supplied.",
        "",
        "## Controlled Scalar-State Bridge Gate",
        "",
        markdown_table(bridge_gate) if len(bridge_gate) else "No supported bridge gate was supplied.",
        "",
        "## Controlled Scalar-State Bridge Sensitivity",
        "",
        markdown_table(bridge_sensitivity) if len(bridge_sensitivity) else "No supported bridge sensitivity grid was supplied.",
        "",
        "## Controlled Scalar-State Bridge Summary",
        "",
        markdown_table(bridge_summary) if len(bridge_summary) else "No supported bridge summary was supplied.",
        "",
        "## BAT Target Construction",
        "",
        markdown_table(target),
        "",
        "## BAT Held-Out Baselines",
        "",
        markdown_table(heldout) if len(heldout) else "No held-out baseline diagnostics.",
        "",
        "## FPA Response Proxy",
        "",
        markdown_table(response) if len(response) else "No FPA response diagnostics.",
        "",
        "## Synthetic Q01-Q10",
        "",
        markdown_table(synth_df),
        "",
        "## Warm-Start Suite",
        "",
        markdown_table(warm_start) if len(warm_start) else "No warm-start suite was supplied.",
        "",
        "## Warm-Start Main Effects",
        "",
        markdown_table(warm_effects) if len(warm_effects) else "No warm-start effect table was supplied.",
        "",
        "## Warm-Start Oracle Gap",
        "",
        markdown_table(warm_oracle_gap) if len(warm_oracle_gap) else "No warm-start oracle-gap table was supplied.",
        "",
        "## Warm-Start Negative Transfer",
        "",
        markdown_table(warm_negative_transfer) if len(warm_negative_transfer) else "No warm-start negative-transfer diagnostics were supplied.",
        "",
        "## Paper Use",
        "",
        "Use `idvc_workflow_surface_panel.pdf` as the compact cold-start workflow visual and `warm_start_effect_forest.pdf` as the main warm-start evidence. Use `warm_start_state_errors.pdf` to inspect early convergence and transfer failures; `bat_calibration_loss.pdf` compares held-out loss including the flexible reference.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bat", default="experiments/results/bat_full_admissible.json")
    parser.add_argument("--cold-start")
    parser.add_argument("--synthetic", help="Optional supplementary synthetic-diagnostic JSON.")
    parser.add_argument("--warm-start", default="experiments/results/warm_start_suite.json")
    parser.add_argument("--bridge", default="experiments/results/supported_bridge.json")
    parser.add_argument("--out-dir", default="outputs/paper", help="Analysis outputs; preserve submitted-paper reference figures")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    tables_dir = out_dir / "tables"
    figures_dir = out_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid", context="paper", font_scale=0.9)
    plt.rcParams.update(
        {
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "font.size": 8,
            "legend.fontsize": 6,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
        }
    )
    bat = load_json(args.bat)
    cold = load_json(args.cold_start) if args.cold_start else None
    synth = load_json(args.synthetic) if args.synthetic else {}
    warm = load_json(args.warm_start) if args.warm_start and Path(args.warm_start).exists() else None
    bridge = load_json(args.bridge) if args.bridge and Path(args.bridge).exists() else None

    summary, gram, categories, response = bat_summary_tables(bat)
    heldout = heldout_table(bat)
    support_heldout = support_stratified_heldout_table(bat)
    cold_start = cold_start_table(cold)
    cold_start_auc = bat_cold_start_auc_table(cold)
    frontier_selection = bat_frontier_selection_table(cold)
    frontier_bootstrap = bat_frontier_bootstrap_table(cold)
    frontier_gate = bat_gate_status_table(cold)
    frontier_support = bat_support_replay_table(cold)
    bridge_summary = supported_bridge_summary_table(bridge)
    bridge_gate = supported_bridge_gate_table(bridge)
    bridge_sensitivity = supported_bridge_sensitivity_table(bridge)
    target = target_construction_table(bat)
    synth_df = synthetic_table(synth)
    warm_start = warm_start_summary_table(warm)
    warm_oracle_gap = warm_start_oracle_gap_table(warm)
    warm_negative_transfer = warm_start_negative_transfer_table(warm)
    warm_effect_numeric = warm_start_effects(warm)
    warm_effects = warm_start_effect_display(warm_effect_numeric)
    core_df = core_evidence_table(bat, synth)
    if not synth:
        core_df = core_df.iloc[:3].copy()
    write_table(core_df, "core_evidence_summary", tables_dir)
    write_table(summary, "bat_calibration_summary", tables_dir)
    write_table(target, "bat_target_construction", tables_dir)
    if len(cold_start):
        write_table(cold_start, "bat_cold_start_campaign_replay", tables_dir)
    if len(cold_start_auc):
        write_table(cold_start_auc, "bat_cold_start_early_auc", tables_dir)
    if len(frontier_selection):
        write_table(frontier_selection, "bat_frontier_selection", tables_dir)
    if len(frontier_bootstrap):
        write_table(frontier_bootstrap, "bat_frontier_bootstrap", tables_dir)
    if len(frontier_gate):
        write_table(frontier_gate, "bat_frontier_gate_status", tables_dir)
    if len(frontier_support):
        write_table(frontier_support, "bat_frontier_support_replay", tables_dir)
    if len(bridge_summary):
        write_table(bridge_summary, "supported_bridge_summary", tables_dir)
    if len(bridge_gate):
        write_table(bridge_gate, "supported_bridge_gate", tables_dir)
    if len(bridge_sensitivity):
        write_table(bridge_sensitivity, "supported_bridge_sensitivity", tables_dir)
    write_table(heldout, "bat_heldout_baselines", tables_dir)
    if len(support_heldout):
        write_table(support_heldout, "bat_support_stratified_heldout", tables_dir)
    write_table(gram, "bat_gram_summary", tables_dir)
    write_table(categories, "bat_category_diagnostics", tables_dir)
    write_table(response, "bat_fpa_response_proxy", tables_dir)
    if synth:
        write_table(synth_df, "synthetic_q_summary", tables_dir)
    if len(warm_start):
        write_table(warm_start, "warm_start_summary", tables_dir)
    if len(warm_oracle_gap):
        write_table(warm_oracle_gap, "warm_start_oracle_gap", tables_dir)
    if len(warm_negative_transfer):
        write_table(warm_negative_transfer, "warm_start_negative_transfer", tables_dir)
    if len(warm_effects):
        write_table(warm_effects, "warm_start_main_effects", tables_dir)

    # Generate only the model and the main calibration/initialization diagnostics.
    plot_idvc_workflow_surface_panel(figures_dir)
    plot_bat_loss(bat, figures_dir)
    plot_warm_start_errors(warm, figures_dir)
    plot_warm_start_effect_forest(warm_effect_numeric, figures_dir)

    render_report(
        summary,
        response,
        cold_start,
        cold_start_auc,
        heldout,
        target,
        synth_df,
        warm_start,
        warm_oracle_gap,
        warm_negative_transfer,
        warm_effects,
        core_df,
        frontier_selection,
        frontier_bootstrap,
        frontier_gate,
        frontier_support,
        bridge_summary,
        bridge_gate,
        bridge_sensitivity,
        out_dir / "paper_artifacts.md",
    )
    print(f"Wrote artifacts to {out_dir}")


if __name__ == "__main__":
    main()
