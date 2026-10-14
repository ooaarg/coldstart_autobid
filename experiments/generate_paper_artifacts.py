#!/usr/bin/env python3
"""Generate paper-ready tables and plots from BAT/synthetic result JSON."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from run_full_synthetic import CPC, dpsi_fpa, fit_contextual_theta, generate_base, psi_fpa, true_theta


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


def mean_ci(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    arr = np.asarray(values, dtype=float)
    center = float(np.mean(arr))
    if len(arr) <= 1:
        return center, center, center
    se = float(np.std(arr, ddof=1) / math.sqrt(len(arr)))
    return center, center - 1.96 * se, center + 1.96 * se


def warm_start_effects(warm: dict[str, Any] | None) -> pd.DataFrame:
    if not warm:
        return pd.DataFrame()
    runs = warm.get("runs", [])
    if not isinstance(runs, list):
        return pd.DataFrame()
    by_key: dict[tuple[str, int, str], dict[str, Any]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        by_key[(str(run.get("scenario")), int(run.get("seed")), str(run.get("initialization")))] = run
    specs = [
        {
            "setting": "related truthful contexts",
            "scenarios": ["matched_stationary", "smooth_drift"],
            "variant": "contextual_idvc",
            "comparator": "best of historical/global",
            "comparator_mode": "best_baseline",
        },
        {
            "setting": "abrupt shift",
            "scenarios": ["abrupt_shift"],
            "variant": "shrunk_idvc",
            "comparator": "best of historical/global",
            "comparator_mode": "best_baseline",
        },
        {
            "setting": "FPA response bias",
            "scenarios": ["fpa_blind_vs_response"],
            "variant": "response_idvc",
            "comparator": "best of historical/global",
            "comparator_mode": "best_baseline",
        },
    ]
    rows = []
    baselines = ["historical_stationary", "global_flat_idvc"]
    for spec in specs:
        lifts: list[float] = []
        ttt_delta: list[float] = []
        violation_delta: list[float] = []
        comparator_wins: dict[str, int] = {}
        for scenario in spec["scenarios"]:
            seeds = sorted(seed for (sc, seed, init) in by_key if sc == scenario and init == spec["variant"])
            for seed in seeds:
                treated = by_key.get((scenario, seed, spec["variant"]))
                if treated is None:
                    continue
                if spec["comparator_mode"] == "best_baseline":
                    candidates = [by_key.get((scenario, seed, name)) for name in baselines]
                    candidates = [item for item in candidates if item is not None]
                    if not candidates:
                        continue
                    comparator = max(candidates, key=lambda item: float(item.get("early_auc", 0.0)))
                    comparator_name = str(comparator.get("initialization"))
                    comparator_wins[comparator_name] = comparator_wins.get(comparator_name, 0) + 1
                else:
                    comparator = by_key.get((scenario, seed, spec["comparator_mode"]))
                    if comparator is None:
                        continue
                    comparator_name = str(comparator.get("initialization"))
                    comparator_wins[comparator_name] = comparator_wins.get(comparator_name, 0) + 1
                comp_auc = float(comparator.get("early_auc", 0.0))
                treat_auc = float(treated.get("early_auc", 0.0))
                if comp_auc <= 0:
                    continue
                lifts.append(100.0 * (treat_auc - comp_auc) / comp_auc)
                ttt_delta.append(float(treated.get("time_to_target", 0.0)) - float(comparator.get("time_to_target", 0.0)))
                violation_delta.append(float(treated.get("early_violation_area", 0.0)) - float(comparator.get("early_violation_area", 0.0)))
        lift_mean, lift_lo, lift_hi = mean_ci(lifts)
        ttt_mean, _, _ = mean_ci(ttt_delta)
        viol_mean, _, _ = mean_ci(violation_delta)
        rows.append(
            {
                "setting": spec["setting"],
                "variant": spec["variant"],
                "comparator": spec["comparator"],
                "n": len(lifts),
                "lift_pct": lift_mean,
                "lift_ci_lo": lift_lo,
                "lift_ci_hi": lift_hi,
                "ttt_delta": ttt_mean,
                "violation_delta": viol_mean,
                "comparator_wins": ", ".join(f"{k}:{v}" for k, v in sorted(comparator_wins.items())),
            }
        )
    return pd.DataFrame(rows)


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


def synthetic_experiment(synth: dict[str, Any], question: str) -> dict[str, Any]:
    for exp in synth.get("experiments", []):
        if exp.get("question") == question:
            return exp
    return {}


def pct_reduction(old: float | None, new: float | None) -> float | None:
    if old is None or new is None or old == 0:
        return None
    return 100.0 * (old - new) / old


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
                "evidence": "23.86M rows; 5.72M usable",
                "result": (
                    f"adm. TCL {fmt(vcg['flat_ols'].get('admissible', {}).get('admissible_tcl_mse'), 2)}"
                    f" -> {fmt(vcg['contextual_bins'].get('contextual_admissible_tcl_mse'), 2)}"
                ),
                "takeaway": "reported as public-BAT proxy diagnostics, not raw winning-price evidence",
            },
            {
                "claim": "BAT FPA proxy calibration",
                "evidence": "9.47M rows; 51 contexts",
                "result": (
                    f"adm. TCL {fmt(fpa['flat_ols'].get('admissible', {}).get('admissible_tcl_mse'), 2)}"
                    f" -> {fmt(fpa['contextual_bins'].get('contextual_admissible_tcl_mse'), 2)}"
                ),
                "takeaway": "admissibility is explicit; unconstrained affine fits remain proxy baselines",
            },
            {
                "claim": "FPA response layer",
                "evidence": "9.45M ratio rows",
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


def savefig(fig, stem: str, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.35)
    fig.savefig(figures_dir / f"{stem}.png", dpi=220)
    fig.savefig(figures_dir / f"{stem}.pdf")
    plt.close(fig)


def warm_start_curve_frame(warm: dict[str, Any] | None, field: str) -> pd.DataFrame:
    if not warm:
        return pd.DataFrame()
    rows = []
    selected = {"historical_stationary", "contextual_idvc", "response_idvc", "shrunk_idvc", "oracle_init"}
    for run in warm.get("runs", []):
        if not isinstance(run, dict) or run.get("initialization") not in selected:
            continue
        values = run.get(field, [])
        if not isinstance(values, list):
            continue
        for step, value in enumerate(values):
            rows.append(
                {
                    "scenario": run.get("scenario"),
                    "initialization": run.get("initialization"),
                    "step": step + 1,
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


def plot_warm_start_reward_trajectories(warm: dict[str, Any] | None, figures_dir: Path) -> None:
    df = warm_start_curve_frame(warm, "cumulative_rewards")
    if df.empty:
        return
    df = df[df["scenario"].isin(["matched_stationary", "smooth_drift", "fpa_blind_vs_response"])]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.4), sharey=False)
    for ax, scenario in zip(axes, ["matched_stationary", "smooth_drift", "fpa_blind_vs_response"]):
        sub = df[df["scenario"] == scenario]
        sns.lineplot(data=sub, x="step", y="value", hue="initialization", errorbar=None, ax=ax, linewidth=1.2)
        ax.set_title(scenario.replace("_", " "))
        ax.set_xlabel("controller update")
        ax.set_ylabel("cumulative reward")
        if ax is not axes[-1]:
            ax.get_legend().remove()
    axes[-1].legend(fontsize=5, frameon=False, loc="lower right")
    savefig(fig, "warm_start_reward_trajectories", figures_dir)


def plot_warm_start_constraint_trajectories(warm: dict[str, Any] | None, figures_dir: Path) -> None:
    df = warm_start_curve_frame(warm, "constraint_violations")
    if df.empty:
        return
    df = df[df["scenario"].isin(["abrupt_shift", "mismatched_prior", "hybrid_lambda_grid"])]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.4), sharey=True)
    for ax, scenario in zip(axes, ["abrupt_shift", "mismatched_prior", "hybrid_lambda_grid"]):
        sub = df[df["scenario"] == scenario]
        sns.lineplot(data=sub, x="step", y="value", hue="initialization", errorbar=None, ax=ax, linewidth=1.2)
        ax.set_title(scenario.replace("_", " "))
        ax.set_xlabel("controller update")
        ax.set_ylabel("constraint gap")
        if ax is not axes[-1]:
            ax.get_legend().remove()
    axes[-1].legend(fontsize=5, frameon=False, loc="upper right")
    savefig(fig, "warm_start_constraint_trajectories", figures_dir)


def plot_warm_start_heatmap(summary: pd.DataFrame, figures_dir: Path) -> None:
    if summary.empty:
        return
    keep = summary[summary["initialization"].isin(["global_flat_idvc", "historical_stationary", "contextual_idvc", "response_idvc", "shrunk_idvc"])]
    pivot = keep.pivot(index="scenario", columns="initialization", values="early_auc_lift_vs_historical")
    fig, ax = plt.subplots(figsize=(6.5, 2.8))
    sns.heatmap(pivot, annot=True, fmt=".2f", cmap="vlag", center=0.0, linewidths=0.4, ax=ax, cbar_kws={"label": "Early-AUC lift"})
    ax.set_title("Initialization effect relative to historical stationary reuse")
    ax.set_xlabel("")
    ax.set_ylabel("")
    savefig(fig, "warm_start_initialization_heatmap", figures_dir)


def plot_warm_start_effect_forest(effects: pd.DataFrame, figures_dir: Path) -> None:
    if effects.empty:
        return
    plot_df = effects.dropna(subset=["lift_pct", "lift_ci_lo", "lift_ci_hi"]).copy()
    if plot_df.empty:
        return
    plot_df = plot_df.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(6.4, 2.65))
    y = np.arange(len(plot_df))
    x = plot_df["lift_pct"].astype(float).to_numpy()
    lo = plot_df["lift_ci_lo"].astype(float).to_numpy()
    hi = plot_df["lift_ci_hi"].astype(float).to_numpy()
    colors = ["#2a9d55" if value >= 0 else "#b55454" for value in x]
    ax.errorbar(
        x,
        y,
        xerr=np.vstack([x - lo, hi - x]),
        fmt="none",
        ecolor="#4f4f4f",
        elinewidth=1.0,
        capsize=3,
        zorder=1,
    )
    ax.scatter(x, y, s=44, color=colors, zorder=2)
    ax.axvline(0.0, color="#555555", linewidth=0.9, linestyle="--")
    labels = [
        f"{row['setting']}\n{row['variant'].replace('_', '-')}"
        for _, row in plot_df.iterrows()
    ]
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Early-AUC lift vs comparator (%)")
    ax.set_title("Warm-start effect sizes with paired 95% CIs")
    for yi, value in zip(y, x):
        ax.text(value + (0.18 if value >= 0 else -0.18), yi, f"{value:+.1f}%", va="center", ha="left" if value >= 0 else "right", fontsize=7)
    savefig(fig, "warm_start_effect_forest", figures_dir)


def effect_against(
    warm: dict[str, Any] | None,
    scenario: str,
    variant: str,
    comparator_mode: str,
) -> tuple[float | None, float | None, float | None]:
    if not warm:
        return None, None, None
    by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for run in warm.get("runs", []):
        if isinstance(run, dict) and run.get("scenario") == scenario:
            by_key[(int(run.get("seed")), str(run.get("initialization")))] = run
    vals: list[float] = []
    for seed in sorted({key[0] for key in by_key}):
        treated = by_key.get((seed, variant))
        if treated is None:
            continue
        if comparator_mode == "best_baseline":
            candidates = [by_key.get((seed, name)) for name in ["historical_stationary", "global_flat_idvc"]]
            candidates = [item for item in candidates if item is not None]
            if not candidates:
                continue
            comparator = max(candidates, key=lambda item: float(item.get("early_auc", 0.0)))
        else:
            comparator = by_key.get((seed, comparator_mode))
            if comparator is None:
                continue
        comp_auc = float(comparator.get("early_auc", 0.0))
        if comp_auc > 0:
            vals.append(100.0 * (float(treated.get("early_auc", 0.0)) - comp_auc) / comp_auc)
    return mean_ci(vals)


def plot_mechanism_boundary_panel(
    warm: dict[str, Any] | None,
    bat_summary: pd.DataFrame,
    cold_start: pd.DataFrame,
    frontier_gate: pd.DataFrame,
    frontier_bootstrap: pd.DataFrame,
    figures_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.25, 2.45), gridspec_kw={"width_ratios": [1.0, 0.9, 1.2]})

    rows = []
    for variant, label in [("contextual_idvc", "blind contextual"), ("response_idvc", "response-aware")]:
        center, lo, hi = effect_against(warm, "fpa_blind_vs_response", variant, "best_baseline")
        rows.append((label, center, lo, hi))
    x = np.arange(len(rows))
    centers = np.array([row[1] if row[1] is not None else 0.0 for row in rows])
    lows = np.array([row[2] if row[2] is not None else 0.0 for row in rows])
    highs = np.array([row[3] if row[3] is not None else 0.0 for row in rows])
    axes[0].bar(x, centers, color=["#b55454", "#2a9d55"], width=0.58)
    axes[0].errorbar(x, centers, yerr=np.vstack([centers - lows, highs - centers]), fmt="none", color="#333333", capsize=3, linewidth=0.9)
    axes[0].axhline(0.0, color="#555555", lw=0.8, ls="--")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([row[0] for row in rows], rotation=12)
    axes[0].set_ylabel("Early-AUC lift (%)")
    axes[0].set_title("(a) FPA response")

    neg = warm_start_negative_transfer_table(warm)
    mismatch_neg = float(neg.loc[neg["scenario"] == "mismatched_prior", "negative_transfer_rate"].iloc[0]) if not neg.empty and any(neg["scenario"] == "mismatched_prior") else 0.0
    summary = warm_start_summary_table(warm)
    abstain = 0.0
    if not summary.empty:
        sub = summary[(summary["scenario"] == "mismatched_prior") & (summary["initialization"] == "shrunk_idvc")]
        if not sub.empty:
            abstain = float(sub["abstention_rate"].iloc[0])
    axes[1].bar([0, 1], [mismatch_neg, abstain], color=["#b55454", "#2a9d55"], width=0.55)
    axes[1].set_xticks([0, 1])
    axes[1].set_xticklabels(["blind\nnegative", "guard\nabstains"])
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("rate")
    axes[1].set_title("(b) mismatch guard")

    boundary_rows = []
    for auction in ["FPA", "VCG"]:
        row = bat_summary[bat_summary["auction"] == auction]
        if not row.empty:
            flat_value = row["flat_admissible_tcl"].iloc[0]
            ctx_value = row["contextual_admissible_tcl"].iloc[0]
            if flat_value is not None and ctx_value is not None and float(flat_value) > 0:
                flat = float(flat_value)
                ctx = float(ctx_value)
                boundary_rows.append((auction, "TCL reduction", 100.0 * (flat - ctx) / flat))
        if not cold_start.empty:
            gate = frontier_gate[frontier_gate["auction"] == auction] if not frontier_gate.empty else pd.DataFrame()
            boot = frontier_bootstrap[
                (frontier_bootstrap["auction"] == auction)
                & (frontier_bootstrap["policy"] == PRIMARY_FRONTIER_POLICY)
            ] if not frontier_bootstrap.empty else pd.DataFrame()
            if not gate.empty and bool(gate["unchanged_bat_pass"].iloc[0]) and not boot.empty:
                value = boot["contact_lift_mean"].iloc[0]
                if isinstance(value, (float, int)):
                    boundary_rows.append((auction, "gated lift", 100.0 * float(value)))
            else:
                boundary_rows.append((auction, "boundary only", 0.0))
    labels = [f"{auction}\n{name}" for auction, name, _ in boundary_rows]
    values = [value for _, _, value in boundary_rows]
    colors = ["#2a9d55" if value >= 0 else "#b55454" for value in values]
    axes[2].bar(np.arange(len(values)), values, color=colors, width=0.6)
    axes[2].axhline(0.0, color="#555555", lw=0.8, ls="--")
    axes[2].set_xticks(np.arange(len(values)))
    axes[2].set_xticklabels(labels)
    axes[2].set_ylabel("effect vs baseline (%)")
    axes[2].set_title("(c) public BAT boundary")
    axes[2].text(0.5, 0.03, "lift shown only if gate passes", transform=axes[2].transAxes, ha="center", va="bottom", fontsize=6)
    savefig(fig, "mechanism_boundary_panel", figures_dir)


def plot_warm_start_fpa_response(summary: pd.DataFrame, figures_dir: Path) -> None:
    if summary.empty:
        return
    sub = summary[
        summary["scenario"].isin(["fpa_blind_vs_response", "hybrid_lambda_grid"])
        & summary["initialization"].isin(["contextual_idvc", "response_idvc", "shrunk_idvc"])
    ]
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(4.8, 2.7))
    sns.barplot(data=sub, x="scenario", y="early_auc_lift_vs_historical", hue="initialization", ax=ax)
    ax.axhline(0.0, color="black", linewidth=0.7)
    ax.set_title("Response-aware initialization in non-truthful settings")
    ax.set_xlabel("")
    ax.set_ylabel("Early-AUC lift vs historical")
    ax.tick_params(axis="x", rotation=12)
    ax.legend(frameon=False, fontsize=6)
    savefig(fig, "warm_start_fpa_response_ablation", figures_dir)


def plot_warm_start_mismatch(warm: dict[str, Any] | None, figures_dir: Path) -> None:
    neg = warm_start_negative_transfer_table(warm)
    summary = warm_start_summary_table(warm)
    if neg.empty or summary.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 2.7))
    sns.barplot(data=neg, x="scenario", y="negative_transfer_rate", ax=axes[0], color="#6c8ebf")
    axes[0].set_title("Blind contextual negative transfer")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("rate")
    axes[0].tick_params(axis="x", rotation=35)
    sub = summary[summary["initialization"] == "shrunk_idvc"]
    sns.barplot(data=sub, x="scenario", y="abstention_rate", ax=axes[1], color="#82a87c")
    axes[1].set_title("Guarded shrinkage abstention")
    axes[1].set_xlabel("")
    axes[1].set_ylabel("rate")
    axes[1].tick_params(axis="x", rotation=35)
    savefig(fig, "warm_start_mismatch_guard", figures_dir)


def plot_bat_tcl(summary: pd.DataFrame, figures_dir: Path) -> None:
    plot_df = summary.melt(
        id_vars=["auction"],
        value_vars=["flat_proxy_tcl", "flat_admissible_tcl", "contextual_proxy_tcl", "contextual_admissible_tcl"],
        var_name="model",
        value_name="TCL",
    )
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    sns.barplot(data=plot_df, x="auction", y="TCL", hue="model", ax=ax)
    ax.set_yscale("log")
    ax.set_title("BAT calibration loss")
    ax.set_ylabel("TCL MSE, lower better (log)")
    ax.set_xlabel("")
    savefig(fig, "bat_tcl_bar", figures_dir)


def plot_gram(categories: pd.DataFrame, summary: pd.DataFrame, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    data = categories.dropna(subset=["gram_condition"]).copy()
    data = data[data["gram_condition"] > 0]
    if len(data):
        sns.histplot(data=data, x="gram_condition", hue="auction", bins=30, log_scale=True, ax=ax)
    else:
        ax.text(0.5, 0.5, "No category gram diagnostics", ha="center", va="center")
    ax.set_title("Context rank diagnostics")
    ax.set_xlabel("Gram condition number (log scale)")
    savefig(fig, "bat_gram_condition_hist", figures_dir)


def plot_ratio_hist(bat: dict[str, Any], figures_dir: Path) -> None:
    fpa = bat["auctions"].get("fpa", {})
    diag = fpa.get("fpa_response_proxy_diagnostics", {})
    hist = diag.get("ratio_histogram", {}) if isinstance(diag, dict) else {}
    labels = list(hist.keys())
    counts = list(hist.values())
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    ax.bar(labels, counts)
    ax.set_yscale("log")
    ax.set_title("FPA response proxy distribution")
    ax.set_ylabel("Rows (log scale)")
    ax.set_xlabel("y / contact_price_bin")
    ax.tick_params(axis="x", rotation=35)
    savefig(fig, "fpa_response_ratio_hist", figures_dir)


def plot_category_tcl(categories: pd.DataFrame, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    data = categories.dropna(subset=["tcl_mse"]).copy()
    data = data[data["tcl_mse"] > 0]
    if len(data):
        sns.boxplot(data=data, x="auction", y="tcl_mse", ax=ax)
        ax.set_yscale("log")
    else:
        ax.text(0.5, 0.5, "No category TCL diagnostics", ha="center", va="center")
    ax.set_title("Category-level TCL distribution")
    ax.set_ylabel("TCL MSE (log scale)")
    ax.set_xlabel("")
    savefig(fig, "category_tcl_distribution", figures_dir)


def plot_synthetic_dashboard(synth_df: pd.DataFrame, figures_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 3.5))
    status = synth_df["status"].map({"PASS": 1, "CHECK": 0}).fillna(0)
    ax.bar(synth_df["question"], status)
    ax.set_ylim(0, 1.2)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["check", "pass"])
    ax.set_title("Synthetic validation checks")
    ax.set_xlabel("")
    savefig(fig, "synthetic_q_dashboard", figures_dir)


def plot_main_results_panel(bat: dict[str, Any], summary: pd.DataFrame, synth_df: pd.DataFrame, figures_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.1, 2.35), gridspec_kw={"width_ratios": [1.0, 1.15, 1.0]})
    plot_df = summary.melt(
        id_vars=["auction"],
        value_vars=["flat_admissible_tcl", "contextual_admissible_tcl"],
        var_name="model",
        value_name="TCL",
    )
    sns.barplot(data=plot_df, x="auction", y="TCL", hue="model", ax=axes[0], palette=["#808080", "#2f7ebc"])
    axes[0].set_yscale("log")
    axes[0].set_title("(a) BAT TCL")
    axes[0].set_xlabel("")
    axes[0].set_ylabel("MSE")
    axes[0].legend(fontsize=6, frameon=False, loc="upper left")

    fpa = bat["auctions"].get("fpa", {})
    hist = fpa.get("fpa_response_proxy_diagnostics", {}).get("ratio_histogram", {})
    axes[1].bar(list(hist.keys()), list(hist.values()), color="#d97b29")
    axes[1].set_yscale("log")
    axes[1].set_title("(b) FPA response")
    axes[1].set_xlabel("y / price bin")
    axes[1].set_ylabel("rows")
    axes[1].tick_params(axis="x", labelrotation=45, labelsize=6)

    status = synth_df["status"].map({"PASS": 1, "CHECK": 0}).fillna(0)
    colors = ["#2a9d55" if value == 1 else "#b55454" for value in status]
    axes[2].bar(synth_df["question"], status, color=colors)
    axes[2].set_ylim(0, 1.2)
    axes[2].set_title("(c) Q checks")
    axes[2].set_xlabel("")
    axes[2].set_yticks([0, 1])
    axes[2].set_yticklabels(["check", "pass"])
    axes[2].tick_params(axis="x", labelrotation=90, labelsize=6)
    savefig(fig, "main_results_panel", figures_dir)


def plot_calibrated_surfaces_panel(
    bat: dict[str, Any],
    summary: pd.DataFrame,
    synth: dict[str, Any],
    figures_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.45), gridspec_kw={"width_ratios": [1.0, 1.08, 1.08]})

    row_df = summary.copy()
    x = np.arange(len(row_df))
    rows_seen = row_df["rows_seen"].astype(float).to_numpy() / 1_000_000.0
    usable_rows = row_df["usable_rows"].astype(float).to_numpy() / 1_000_000.0
    axes[0].bar(x - 0.17, rows_seen, width=0.34, color="#c9c9c9", label="scanned")
    axes[0].bar(x + 0.17, usable_rows, width=0.34, color="#4c78a8", label="usable")
    for i, row in row_df.iterrows():
        gain = pct_reduction(row.get("flat_admissible_tcl"), row.get("contextual_admissible_tcl"))
        axes[0].annotate(
            f"-{fmt(gain, 1)}% TCL",
            xy=(i, max(rows_seen[i], usable_rows[i])),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=7,
        )
    axes[0].set_title("(a) BAT support and TCL gain")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(row_df["auction"])
    axes[0].set_ylabel("rows (M)")
    axes[0].set_ylim(0, max(rows_seen.max(), usable_rows.max()) * 1.22)
    axes[0].legend(fontsize=6, frameon=False, loc="upper left")

    seed = int(synth.get("seed", 20260513))
    rows = generate_base(3600, seed)
    y_response = [r.bid_fpa + r.psi_fpa for r in rows]
    estimates = fit_contextual_theta(rows, y_response, bins=10)
    bins = np.linspace(0.0, 1.0, 11)
    centers = 0.5 * (bins[:-1] + bins[1:])
    est_s = []
    est_alpha = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        idx = [i for i, r in enumerate(rows) if lo <= r.z < hi or (hi == 1.0 and r.z == 1.0)]
        est_s.append(float(np.mean([estimates[i][0] for i in idx])))
        est_alpha.append(float(np.mean([estimates[i][1] for i in idx])))
    z_grid = np.linspace(0.0, 1.0, 120)
    true_s = np.array([true_theta(float(z))[0] for z in z_grid])
    true_alpha = np.array([true_theta(float(z))[1] for z in z_grid])
    axes[1].plot(z_grid, true_s, color="#2f7ebc", lw=1.4, label="true s")
    axes[1].plot(z_grid, true_alpha, color="#d97b29", lw=1.4, label="true alpha")
    axes[1].scatter(centers, est_s, color="#2f7ebc", s=14, marker="o", label="fit s")
    axes[1].scatter(centers, est_alpha, color="#d97b29", s=14, marker="s", label="fit alpha")
    axes[1].set_title("(b) implied dual surface")
    axes[1].set_xlabel("context z")
    axes[1].set_ylabel("dual coefficient")
    axes[1].legend(fontsize=6, frameon=False, ncol=2, loc="lower left")

    z = np.linspace(0.0, 1.0, 60)
    bid_max = max(1.0, float(np.quantile([r.bid_fpa for r in rows], 0.98)))
    b = np.linspace(0.0, bid_max, 60)
    zz, bb = np.meshgrid(z, b)
    phi = bb + np.vectorize(psi_fpa)(bb, zz)
    surface = axes[2].contourf(zz, bb, phi, levels=14, cmap="viridis")
    axes[2].contour(zz, bb, phi, levels=7, colors="white", linewidths=0.35, alpha=0.8)
    q01 = synthetic_metrics(synth, "Q01")
    min_margin = q01.get("fpa_min_derivative_margin")
    axes[2].text(
        0.02,
        0.96,
        f"min dphi/db = {fmt(min_margin, 3)}",
        transform=axes[2].transAxes,
        va="top",
        fontsize=7,
        color="white",
        bbox={"facecolor": "#222222", "alpha": 0.35, "pad": 1.5, "edgecolor": "none"},
    )
    axes[2].set_title("(c) response operator")
    axes[2].set_xlabel("context z")
    axes[2].set_ylabel("bid b")
    cbar = fig.colorbar(surface, ax=axes[2], fraction=0.046, pad=0.02)
    cbar.set_label("phi_z(b)", fontsize=7)
    cbar.ax.tick_params(labelsize=6)

    savefig(fig, "calibrated_surfaces_panel", figures_dir)


def plot_experimental_story_panel(bat: dict[str, Any], summary: pd.DataFrame, synth: dict[str, Any], figures_dir: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.45), gridspec_kw={"width_ratios": [1.05, 1.1, 1.0]})

    fpa = bat["auctions"]["fpa"]
    vcg = bat["auctions"]["vcg"]
    fpa_proxy = fpa.get("fpa_response_proxy_diagnostics", {}).get("proxy_fit", {}).get("tcl_mse")
    x = np.array([0, 1, 2])
    series = {
        "FPA": [
            fpa["flat_ols"].get("admissible", {}).get("admissible_tcl_mse"),
            fpa["contextual_bins"].get("contextual_admissible_tcl_mse"),
            fpa_proxy,
        ],
        "VCG": [
            vcg["flat_ols"].get("admissible", {}).get("admissible_tcl_mse"),
            vcg["contextual_bins"].get("contextual_admissible_tcl_mse"),
            None,
        ],
    }
    colors = {"FPA": "#d97b29", "VCG": "#2f7ebc"}
    for name, values in series.items():
        xs = [x[i] for i, value in enumerate(values) if value is not None]
        ys = [value for value in values if value is not None]
        axes[0].plot(xs, ys, marker="o", color=colors[name], label=name, lw=1.5)
        for xi, yi in zip(xs, ys):
            axes[0].annotate(
                fmt(yi, 1),
                xy=(xi, yi),
                xytext=(0, -10 if name == "FPA" else 5),
                textcoords="offset points",
                ha="center",
                fontsize=6,
                color=colors[name],
            )
    axes[0].set_yscale("log")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["flat\nadm.", "context\nadm.", "proxy\nresponse"], rotation=0)
    axes[0].set_title("(a) calibration path")
    axes[0].set_ylabel("TCL MSE, lower better")
    axes[0].legend(fontsize=6, frameon=False, loc="lower right")

    q02 = synthetic_metrics(synth, "Q02")
    q04 = synthetic_metrics(synth, "Q04")
    diag_labels = ["raw\nsmile", "resp.\nsmile", "oracle\nrank", "smooth\nrank", "alt.\nrank"]
    diag_values = [
        q04.get("raw_contextual_smile_energy"),
        q04.get("contextual_response_smile_energy"),
        max(1e-6, q02.get("oracle_rank_ratio_median", 0.0)),
        q02.get("heavy_noise_smoothed_rank_ratio_median"),
        q02.get("alternative_rank_ratio_median"),
    ]
    diag_colors = ["#b55454", "#2a9d55", "#2a9d55", "#8ab17d", "#b55454"]
    axes[1].bar(np.arange(len(diag_labels)), diag_values, color=diag_colors)
    axes[1].axvline(1.5, color="#666666", lw=0.7, ls="--")
    axes[1].set_yscale("log")
    axes[1].set_xticks(np.arange(len(diag_labels)))
    axes[1].set_xticklabels(diag_labels, fontsize=7)
    axes[1].set_title("(b) diagnostics")
    axes[1].set_ylabel("diagnostic score (log)")

    q09 = synthetic_experiment(synth, "Q09")
    q10 = synthetic_metrics(synth, "Q10")
    policies = q09.get("policies", {}) if isinstance(q09, dict) else {}
    default = policies.get("default", {})
    response = policies.get("response_idvc", {})
    ratios = [
        response.get("initial_distance", 0.0) / max(1e-12, default.get("initial_distance", 1.0)),
        response.get("time_to_target", 0.0) / max(1e-12, default.get("time_to_target", 1.0)),
        q10.get("related_eb_regret_ratio"),
        q10.get("mismatched_eb_regret_ratio"),
    ]
    labels = ["init\ndist.", "time\ntarget", "EB\nrel.", "EB\nmis."]
    bar_colors = ["#2a9d55" if value <= 1.0 else "#b55454" for value in ratios]
    axes[2].bar(np.arange(len(labels)), ratios, color=bar_colors)
    axes[2].axhline(1.0, color="#555555", lw=0.8, ls="--")
    axes[2].set_ylim(0.0, max(1.35, 1.1 * max(ratios)))
    axes[2].set_xticks(np.arange(len(labels)))
    axes[2].set_xticklabels(labels, fontsize=7)
    axes[2].set_title("(c) deployment effect")
    axes[2].set_ylabel("ratio to baseline")
    for i, value in enumerate(ratios):
        label = f"{value:.1e}" if value < 0.005 else fmt(value, 2)
        axes[2].text(i, max(value + 0.04, 0.05), label, ha="center", fontsize=7)

    savefig(fig, "experimental_story_panel", figures_dir)


def plot_support_stratified_heldout(support: pd.DataFrame, figures_dir: Path) -> None:
    if support.empty:
        return

    bucket_order = ["0", "1-9", "10-99", "100-499", "500+"]
    labels = {
        "category_price_mean": "cat-price mean",
        "flat_idvc": "flat IDVC",
        "contextual_idvc": "contextual IDVC",
        "flat_unconstrained_affine_proxy": "flat proxy",
        "contextual_unconstrained_affine_proxy": "context proxy",
        "flat_admissible_idvc": "flat adm. IDVC",
        "contextual_admissible_idvc": "context adm. IDVC",
        "fpa_response_proxy": "FPA proxy",
    }
    colors = {
        "category_price_mean": "#6f6f6f",
        "flat_idvc": "#2f7ebc",
        "contextual_idvc": "#2a9d55",
        "flat_unconstrained_affine_proxy": "#8aa6c1",
        "contextual_unconstrained_affine_proxy": "#8ab17d",
        "flat_admissible_idvc": "#2f7ebc",
        "contextual_admissible_idvc": "#2a9d55",
        "fpa_response_proxy": "#d97b29",
    }
    markers = {
        "category_price_mean": "o",
        "flat_idvc": "s",
        "contextual_idvc": "D",
        "flat_unconstrained_affine_proxy": "s",
        "contextual_unconstrained_affine_proxy": "D",
        "flat_admissible_idvc": "P",
        "contextual_admissible_idvc": "X",
        "fpa_response_proxy": "^",
    }

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.75), sharey=True)
    for ax, auction in zip(axes, ["FPA", "VCG"]):
        part = support[support["auction"] == auction].copy()
        for model in [
            "category_price_mean",
            "flat_unconstrained_affine_proxy",
            "contextual_unconstrained_affine_proxy",
            "flat_admissible_idvc",
            "contextual_admissible_idvc",
            "fpa_response_proxy",
        ]:
            rows = part[part["model"] == model]
            if rows.empty:
                continue
            xs = [bucket_order.index(str(bucket)) for bucket in rows["support_bucket"]]
            ys = rows["test_tcl"].astype(float).to_numpy()
            sizes = 18 + 9 * np.log10(np.maximum(1.0, rows["test_rows"].astype(float).to_numpy()))
            ax.plot(xs, ys, color=colors[model], lw=1.2, alpha=0.85, label=labels[model])
            ax.scatter(
                xs,
                ys,
                s=sizes,
                color=colors[model],
                marker=markers[model],
                edgecolor="white",
                linewidth=0.45,
                zorder=3,
            )
        ax.set_title(auction)
        ax.set_xticks(range(len(bucket_order)))
        ax.set_xticklabels(bucket_order)
        ax.set_xlabel("train support")
        ax.grid(True, axis="y", which="both", alpha=0.35)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("held-out TCL MSE, lower better")

    legend_models = [
        model
        for model in [
            "category_price_mean",
            "flat_unconstrained_affine_proxy",
            "contextual_unconstrained_affine_proxy",
            "flat_admissible_idvc",
            "contextual_admissible_idvc",
            "fpa_response_proxy",
        ]
        if model in set(support["model"])
    ]
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            color=colors[model],
            marker=markers[model],
            lw=1.2,
            markersize=4,
            label=labels[model],
        )
        for model in legend_models
    ]
    axes[1].legend(handles=legend_handles, fontsize=6, frameon=False, loc="upper right")
    fig.tight_layout()
    savefig(fig, "bat_support_stratified_heldout", figures_dir)


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
        "## Supported BAT-Shaped Bridge Gate",
        "",
        markdown_table(bridge_gate) if len(bridge_gate) else "No supported bridge gate was supplied.",
        "",
        "## Supported BAT-Shaped Bridge Sensitivity",
        "",
        markdown_table(bridge_sensitivity) if len(bridge_sensitivity) else "No supported bridge sensitivity grid was supplied.",
        "",
        "## Supported BAT-Shaped Bridge Summary",
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
        "Use `warm_start_effect_forest.pdf` and `mechanism_boundary_panel.pdf` as the main warm-start and mechanism evidence. Keep unchanged BAT replay as boundary evidence unless a validated response-aware public replay becomes decision-positive.",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bat", default="experiments/results/bat_full.json")
    parser.add_argument("--cold-start")
    parser.add_argument("--synthetic", default="experiments/results/full_synthetic.json")
    parser.add_argument("--warm-start", default="experiments/results/warm_start_suite.json")
    parser.add_argument("--bridge", default="experiments/results/supported_bridge.json")
    parser.add_argument("--out-dir", default="experiments/results")
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
    synth = load_json(args.synthetic)
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
    write_table(synth_df, "synthetic_q_summary", tables_dir)
    if len(warm_start):
        write_table(warm_start, "warm_start_summary", tables_dir)
    if len(warm_oracle_gap):
        write_table(warm_oracle_gap, "warm_start_oracle_gap", tables_dir)
    if len(warm_negative_transfer):
        write_table(warm_negative_transfer, "warm_start_negative_transfer", tables_dir)
    if len(warm_effects):
        write_table(warm_effects, "warm_start_main_effects", tables_dir)

    plot_bat_tcl(summary, figures_dir)
    plot_gram(categories, summary, figures_dir)
    plot_ratio_hist(bat, figures_dir)
    plot_category_tcl(categories, figures_dir)
    plot_calibrated_surfaces_panel(bat, summary, synth, figures_dir)
    plot_experimental_story_panel(bat, summary, synth, figures_dir)
    plot_support_stratified_heldout(support_heldout, figures_dir)
    plot_warm_start_reward_trajectories(warm, figures_dir)
    plot_warm_start_constraint_trajectories(warm, figures_dir)
    plot_warm_start_heatmap(warm_start, figures_dir)
    plot_warm_start_effect_forest(warm_effect_numeric, figures_dir)
    plot_mechanism_boundary_panel(warm, summary, cold_start, frontier_gate, frontier_bootstrap, figures_dir)
    plot_warm_start_fpa_response(warm_start, figures_dir)
    plot_warm_start_mismatch(warm, figures_dir)

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
    import argparse

    main()
