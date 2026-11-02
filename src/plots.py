"""Plots for the three main experiments; shared with the paper artifact generator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


def plot_bridge(payload: dict, folder: Path) -> None:
    rows = [row for row in payload["summary"] if row["initialization"] == "guarded_idvc"]
    baseline = {row["scenario"]: row for row in payload["summary"]
                if row["initialization"] == "historical_stationary"}
    labels = [row["scenario"].replace("_", " ") for row in rows]
    lift = [100 * row["early_auc_lift_vs_historical"] for row in rows]
    violation = [row["violation_auc_mean"] - baseline[row["scenario"]]["violation_auc_mean"] for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, values, label in zip(axes, [lift, violation],
                                 ["Early-AUC lift (%) · higher is better", "State-violation difference · lower is better"]):
        ax.barh(labels, values, color="#3976a8")
        ax.axvline(0, color="#555555", linewidth=0.8)
        ax.set_xlabel(label)
    fig.suptitle("Supported bridge: guarded IDVC vs historical reuse\nScenario means in the scalar-state simulation", fontsize=11)
    savefig(fig, "supported_bridge_comparison", folder)


def plot_sensitivity(payload: dict, folder: Path) -> None:
    sensitivity = payload["sensitivity"]
    grid = sensitivity["grid"]
    lookup = {(row["shift_multiplier"], row["response_multiplier"]): row for row in sensitivity["rows"]}
    data = [[100 * lookup[(shift, response)]["contact_lift_mean"] for response in grid] for shift in grid]
    fig, ax = plt.subplots(figsize=(5, 4))
    sns.heatmap(data, annot=True, fmt=".2f", xticklabels=grid, yticklabels=grid, ax=ax,
                cmap="RdYlGn", center=0, cbar_kws={"label": "Mean early-AUC lift (%)"})
    ax.set(xlabel="Response multiplier", ylabel="Shift multiplier",
           title="Bridge sensitivity: guarded IDVC vs historical reuse")
    savefig(fig, "supported_bridge_sensitivity", folder)


def plot_bat_loss(payload: dict, folder: Path) -> None:
    # Compare held-out prediction, including the stronger flexible reference.
    names = {"flat_admissible_idvc": "Flat IDVC",
             "contextual_admissible_idvc": "Contextual IDVC",
             "category_price_mean": "Category-price mean"}
    rows = []
    for auction, result in payload["auctions"].items():
        for model in result.get("heldout_baselines", {}).get("models", []):
            if model["model"] in names and model.get("test_tcl_mse") is not None:
                rows.append({"Auction": auction.upper(), "Fit": names[model["model"]],
                             "MSE": model["test_tcl_mse"]})
    frame = pd.DataFrame(rows, columns=["Auction", "Fit", "MSE"])
    auctions = list(payload["auctions"])
    fig, axes = plt.subplots(1, len(auctions), figsize=(5 * len(auctions), 3.5), squeeze=False)
    for ax, auction in zip(axes.flat, auctions):
        sub = frame[frame["Auction"] == auction.upper()]
        if sub.empty:
            ax.text(0.5, 0.5, "No held-out observations", ha="center", transform=ax.transAxes)
        else:
            sns.barplot(data=sub, y="Fit", x="MSE", ax=ax, color="#3976a8", errorbar=None)
        ax.set(title=auction.upper(), xlabel="Held-out proxy MSE · lower is better", ylabel="")
    fig.suptitle("BAT calibration: compact dual fit vs flexible prediction", fontsize=11)
    savefig(fig, "bat_calibration_loss", folder)


def render_plots(task: str, payload: dict, folder: Path) -> list[str]:
    """Use only this run's data; never pick up reference outputs from another run."""
    folder.mkdir(parents=True, exist_ok=True)
    with plt.rc_context():
        sns.set_theme(style="whitegrid", font_scale=0.85)
        if task == "warm_start":
            plot_warm_start_effect_forest(warm_start_effects(payload), folder)
            plot_warm_start_errors(payload, folder)
            return ["warm_start_effect_forest", "warm_start_state_errors"]
        if task == "supported_bridge":
            plot_bridge(payload, folder)
            stems = ["supported_bridge_comparison"]
            if "sensitivity" in payload:
                plot_sensitivity(payload, folder)
                stems.append("supported_bridge_sensitivity")
            return stems
        from src.generate_bat_category_hour_surfaces import plot_selected_surfaces
        plot_selected_surfaces({auction: result["category_hour_surface"]
                                for auction, result in payload["auctions"].items()}, folder)
        plot_bat_loss(payload, folder)
        return ["bat_selected_category_hour_dual_surfaces_clean", "bat_calibration_loss"]

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
        lifts_by_seed: dict[int, list[float]] = {}
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
                lifts_by_seed.setdefault(seed, []).append(100.0 * (treat_auc - comp_auc) / comp_auc)
                ttt_delta.append(float(treated.get("time_to_target", 0.0)) - float(comparator.get("time_to_target", 0.0)))
                violation_delta.append(float(treated.get("early_violation_area", 0.0)) - float(comparator.get("early_violation_area", 0.0)))
        # Related-context panels share seeds. Average within seed before the CI
        # so two scenarios from the same seed are not independent replicates.
        lifts = [float(np.mean(values)) for values in lifts_by_seed.values()]
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


def savefig(fig, stem: str, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(pad=0.35)
    fig.savefig(figures_dir / f"{stem}.png", dpi=220)
    fig.savefig(figures_dir / f"{stem}.pdf")
    plt.close(fig)


def plot_warm_start_errors(warm: dict[str, Any] | None, figures_dir: Path) -> None:
    """Show the transient that cumulative reward conceals after convergence."""
    if not warm:
        return
    from src.run_warm_start_suite import Scenario, scenario_target
    scenarios = {item["name"]: Scenario(**item) for item in warm["scenarios"]}
    policies = {"historical_stationary": "Historical", "global_flat_idvc": "Global",
                "contextual_idvc": "Contextual", "response_idvc": "Response-aware",
                "shrunk_idvc": "Guarded"}
    rows = []
    for run in warm["runs"]:
        if run["initialization"] not in policies:
            continue
        states = run["controller_states"]
        targets = scenario_target(scenarios[run["scenario"]], len(states))
        for step, (state, target) in enumerate(zip(states, targets)):
            if step >= 32:
                break
            rows.append({"scenario": run["scenario"], "policy": policies[run["initialization"]],
                         "step": step, "error": abs(state - target)})
    frame = pd.DataFrame(rows)
    titles = {"matched_stationary": "Matched initial state", "smooth_drift": "Smooth target drift",
              "abrupt_shift": "Abrupt target shift", "mismatched_prior": "Mismatched prior (labelled control)",
              "fpa_blind_vs_response": "Additive FPA-like bias", "hybrid_lambda_grid": "Interpolated additive bias"}
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), sharex=True, sharey=True)
    for ax, scenario in zip(axes.flat, scenarios):
        sub = frame[frame["scenario"] == scenario]
        sns.lineplot(data=sub, x="step", y="error", hue="policy", hue_order=list(policies.values()),
                     errorbar=None, ax=ax, linewidth=1.5)
        ax.axhline(warm.get("config", {}).get("tolerance", 0.05), color="#555555", linestyle="--", linewidth=0.8)
        ax.set(title=titles[scenario], xlabel="Step (0 = first decision)", ylabel="Mean absolute state error")
        ax.get_legend().remove()
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(policies), frameon=False)
    fig.suptitle("Initialization and failure modes · dashed line = state tolerance", fontsize=12)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    figures_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(figures_dir / "warm_start_state_errors.png", dpi=220)
    fig.savefig(figures_dir / "warm_start_state_errors.pdf")
    plt.close(fig)


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
    lower, upper = min(0.0, float(lo.min())), max(0.0, float(hi.max()))
    span = max(upper - lower, 0.1)
    ax.set_xlim(lower - 0.05 * span, upper + 0.25 * span)
    for yi, value in zip(y, x):
        ax.text(upper + 0.08 * span, yi, f"{value:+.1f}%", va="center", ha="left", fontsize=7)
    savefig(fig, "warm_start_effect_forest", figures_dir)
