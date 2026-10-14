#!/usr/bin/env python3
"""BAT-shaped semi-synthetic bridge for supported cold-start IDVC evidence.

The bridge freezes BAT-like context support and campaign counts, then injects
known dual shifts and response transforms. It is mechanism evidence: it can
validate the supported initialization claim, but it is not public-BAT
deployment lift.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping


SCENARIO_REGISTRY = {
    "matched": {
        "role": "primary",
        "history_shift": -0.10,
        "global_shift": -0.070,
        "context_shift": 0.0,
        "response_factor": 0.0,
        "target_level_shift": 0.0,
        "abrupt_after": 0.0,
    },
    "fpa_response_bias": {
        "role": "primary",
        "history_shift": -0.10,
        "global_shift": -0.070,
        "context_shift": 0.0,
        "response_factor": 1.0,
        "target_level_shift": 0.0,
        "abrupt_after": 0.0,
    },
    "hybrid": {
        "role": "primary",
        "history_shift": -0.10,
        "global_shift": -0.070,
        "context_shift": 0.0,
        "response_factor": 0.55,
        "target_level_shift": 0.0,
        "abrupt_after": 0.0,
    },
    "abrupt_shift": {
        "role": "primary",
        "history_shift": -0.14,
        "global_shift": -0.070,
        "context_shift": 0.0,
        "response_factor": 0.0,
        "target_level_shift": 0.05,
        "abrupt_after": 0.13,
    },
    "null_stationary": {
        "role": "negative_control",
        "history_shift": 0.0,
        "global_shift": -0.020,
        "context_shift": 0.0,
        "response_factor": 0.0,
        "target_level_shift": 0.0,
        "abrupt_after": 0.0,
    },
    "unsupported_mismatch": {
        "role": "negative_control",
        "history_shift": -0.060,
        "global_shift": -0.060,
        "context_shift": -0.55,
        "response_factor": 0.0,
        "target_level_shift": 0.30,
        "abrupt_after": 0.0,
    },
}
SCENARIOS = tuple(SCENARIO_REGISTRY)
INITIALIZATIONS = (
    "historical_stationary",
    "global_flat_idvc",
    "contextual_idvc",
    "response_idvc",
    "guarded_idvc",
    "oracle",
)
PRIMARY_SCENARIOS = tuple(name for name, spec in SCENARIO_REGISTRY.items() if spec["role"] == "primary")
NEGATIVE_CONTROL_SCENARIOS = tuple(name for name, spec in SCENARIO_REGISTRY.items() if spec["role"] == "negative_control")
PRIMARY_POLICY = "guarded_idvc"
COMPARATOR = "historical_stationary"
BOOTSTRAP_SEED = 20260522
BOOTSTRAP_RESAMPLES = 1000
MIN_BOOTSTRAP_CLUSTERS = 30
HORIZONS = (1, 3, 6, 12, 24)
TOL = 0.05
SENSITIVITY_GRID = (0.85, 1.00, 1.15)


def mean(xs: Iterable[float]) -> float:
    vals = list(xs)
    return sum(vals) / len(vals) if vals else 0.0


def quantile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    vals = sorted(xs)
    idx = min(len(vals) - 1, max(0, int(round((len(vals) - 1) * p))))
    return vals[idx]


def paired_lift_ci(
    pairs: list[tuple[str, float, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    if not pairs:
        return {"clusters": 0, "scenario_pairs": 0, "mean": None, "lo": None, "hi": None}
    clusters: dict[str, list[tuple[float, float]]] = {}
    for cluster, treated, baseline in pairs:
        clusters.setdefault(cluster, []).append((treated, baseline))
    cluster_items = sorted(clusters.items())
    treated_total = sum(t for _, t, _ in pairs)
    baseline_total = sum(b for _, _, b in pairs)
    center = (treated_total - baseline_total) / baseline_total if abs(baseline_total) > 1e-12 else None
    rng = random.Random(seed)
    draws = []
    n = len(cluster_items)
    for _ in range(resamples):
        treated = 0.0
        baseline = 0.0
        for _ in range(n):
            _, cluster_pairs = cluster_items[rng.randrange(n)]
            treated += sum(t for t, _ in cluster_pairs)
            baseline += sum(b for _, b in cluster_pairs)
        if abs(baseline) > 1e-12:
            draws.append((treated - baseline) / baseline)
    return {"clusters": n, "scenario_pairs": len(pairs), "mean": center, "lo": quantile(draws, 0.025), "hi": quantile(draws, 0.975)}


def paired_diff_ci(
    pairs: list[tuple[str, float, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    if not pairs:
        return {"clusters": 0, "scenario_pairs": 0, "mean": None, "lo": None, "hi": None}
    clusters: dict[str, list[float]] = {}
    diffs = []
    for cluster, treated, baseline in pairs:
        diff = treated - baseline
        diffs.append(diff)
        clusters.setdefault(cluster, []).append(diff)
    center = mean(diffs)
    cluster_items = sorted(clusters.items())
    rng = random.Random(seed)
    draws = []
    n = len(cluster_items)
    for _ in range(resamples):
        sample_diffs = []
        for _ in range(n):
            _, cluster_diffs = cluster_items[rng.randrange(n)]
            sample_diffs.extend(cluster_diffs)
        draws.append(mean(sample_diffs))
    return {"clusters": n, "scenario_pairs": len(pairs), "mean": center, "lo": quantile(draws, 0.025), "hi": quantile(draws, 0.975)}


def context_profile(context_id: int) -> dict[str, float]:
    base = 1.05 + 0.018 * (context_id % 11) + 0.006 * (context_id // 11)
    support = 120 + 37 * ((context_id * 19) % 23)
    response = 0.14 + 0.015 * (context_id % 7)
    return {"base": base, "support": support, "response": response}


def scenario_target(
    profile: Mapping[str, float],
    scenario: str,
    step: int,
    registry: Mapping[str, Mapping[str, float | str]] = SCENARIO_REGISTRY,
) -> float:
    spec = registry[scenario]
    base = float(profile["base"])
    shifted = base + float(spec["target_level_shift"])
    if scenario in {"matched", "null_stationary"}:
        return shifted + 0.015 * math.sin(step / 5.0)
    if scenario == "fpa_response_bias":
        return shifted + 0.02 * math.sin(step / 4.0)
    if scenario == "hybrid":
        return shifted + 0.01 * math.cos(step / 3.0)
    if scenario == "abrupt_shift":
        return shifted + (float(spec["abrupt_after"]) if step >= 3 else 0.0)
    if scenario == "unsupported_mismatch":
        return shifted
    raise ValueError(scenario)


def latent_bundle(
    profile: Mapping[str, float],
    scenario: str,
    rng: random.Random,
    registry: Mapping[str, Mapping[str, float | str]] = SCENARIO_REGISTRY,
) -> dict[str, float]:
    spec = registry[scenario]
    true0 = scenario_target(profile, scenario, 0, registry)
    support = float(profile["support"])
    response_bias = float(profile["response"])
    return {
        "true0": true0,
        "support": support,
        "response_bias": response_bias,
        "historical_noise": rng.gauss(0.0, 0.018),
        "global_noise": rng.gauss(0.0, 0.025),
        "contextual_noise": rng.gauss(0.0, 0.018 + 5.0 / (support + 50.0)),
        "response_noise": rng.gauss(0.0, 0.020),
        "history_shift": float(spec["history_shift"]),
        "global_shift": float(spec["global_shift"]),
        "context_shift": float(spec["context_shift"]),
        "response_factor": float(spec["response_factor"]),
        **{f"outcome_noise_{i}": rng.gauss(0.0, 0.018) for i in range(HORIZONS[-1])},
    }


def initial_state(profile: Mapping[str, float], init: str, bundle: Mapping[str, float]) -> tuple[float, bool]:
    true0 = float(bundle["true0"])
    support = float(bundle["support"])
    response_bias = float(bundle["response_bias"])
    historical = true0 + float(bundle["history_shift"]) + float(bundle["historical_noise"])
    global_flat = true0 + float(bundle["global_shift"]) + float(bundle["global_noise"])
    response = true0 + float(bundle["context_shift"]) + float(bundle["response_noise"])
    contextual = response - float(bundle["response_factor"]) * response_bias
    mismatch_z = abs(contextual - global_flat) / 0.16
    abstain = mismatch_z > 1.65
    weight = support / (support + 100.0)
    guarded = global_flat if abstain else weight * response + (1.0 - weight) * global_flat
    states = {
        "historical_stationary": historical,
        "global_flat_idvc": global_flat,
        "contextual_idvc": contextual,
        "response_idvc": response,
        "guarded_idvc": guarded,
        "oracle": true0,
    }
    return states[init], abstain if init == "guarded_idvc" else False


def simulate_policy(
    profile: Mapping[str, float],
    scenario: str,
    start: float,
    bundle: Mapping[str, float],
    registry: Mapping[str, Mapping[str, float | str]] = SCENARIO_REGISTRY,
) -> dict[str, object]:
    state = start
    contacts_curve: list[float] = []
    violations: list[float] = []
    cumulative_contacts = 0.0
    time_to_target = HORIZONS[-1]
    for step in range(HORIZONS[-1]):
        target = scenario_target(profile, scenario, step, registry)
        err = state - target
        reward = max(0.0, 1.0 - 1.35 * abs(err) + float(bundle.get(f"outcome_noise_{step}", 0.0)))
        cumulative_contacts += reward
        violation = max(0.0, abs(err) - TOL)
        violations.append(violation)
        if violation <= 1e-12 and time_to_target == HORIZONS[-1]:
            time_to_target = step
        if step + 1 in HORIZONS:
            contacts_curve.append(cumulative_contacts)
        state -= 0.24 * err
    early_auc = mean(contacts_curve)
    return {
        "early_auc": early_auc,
        "contacts_curve": contacts_curve,
        "violation_auc": mean(violations[h - 1] for h in HORIZONS),
        "time_to_target": time_to_target,
    }


def run_bridge(
    seeds: int,
    contexts: int,
    seed: int,
    registry: Mapping[str, Mapping[str, float | str]] = SCENARIO_REGISTRY,
    include_runs: bool = True,
) -> dict[str, object]:
    runs = []
    scenarios = tuple(registry)
    for offset in range(seeds):
        rng = random.Random(seed + offset)
        for context_id in range(contexts):
            profile = context_profile(context_id)
            campaign_id = f"ctx{context_id:03d}_seed{offset:03d}"
            for scenario in scenarios:
                bundle = latent_bundle(profile, scenario, rng, registry)
                for init in INITIALIZATIONS:
                    start, abstained = initial_state(profile, init, bundle)
                    result = simulate_policy(profile, scenario, start, bundle, registry)
                    runs.append(
                        {
                            "seed": seed + offset,
                            "context_id": context_id,
                            "campaign_id": campaign_id,
                            "scenario": scenario,
                            "initialization": init,
                            "abstained": abstained,
                            **result,
                        }
                    )
    return summarize(runs, seeds, contexts, seed, registry, include_runs=include_runs)


def summarize(
    runs: list[dict[str, object]],
    seeds: int,
    contexts: int,
    seed: int,
    registry: Mapping[str, Mapping[str, float | str]],
    include_runs: bool = True,
) -> dict[str, object]:
    primary_scenarios = tuple(name for name, spec in registry.items() if spec["role"] == "primary")
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in runs:
        grouped.setdefault((str(row["scenario"]), str(row["initialization"])), []).append(row)
    summary = []
    for (scenario, init), items in sorted(grouped.items()):
        baseline = grouped.get((scenario, COMPARATOR), [])
        baseline_auc = mean(float(x["early_auc"]) for x in baseline)
        auc = mean(float(x["early_auc"]) for x in items)
        summary.append(
            {
                "scenario": scenario,
                "initialization": init,
                "runs": len(items),
                "early_auc_mean": auc,
                "early_auc_lift_vs_historical": (auc - baseline_auc) / baseline_auc if baseline_auc > 0 else None,
                "violation_auc_mean": mean(float(x["violation_auc"]) for x in items),
                "time_to_target_median": quantile([float(x["time_to_target"]) for x in items], 0.5),
                "abstention_rate": mean(1.0 if x["abstained"] else 0.0 for x in items),
            }
        )

    by_key: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in runs:
        by_key[(str(row["scenario"]), str(row["campaign_id"]), str(row["initialization"]))] = row
    primary_pairs = []
    primary_violation_pairs = []
    def collect_pairs(scenarios: Iterable[str], policy: str, comparator: str, metric: str) -> list[tuple[str, float, float]]:
        out: list[tuple[str, float, float]] = []
        for scenario_name in scenarios:
            campaign_ids = sorted({str(row["campaign_id"]) for row in runs if row["scenario"] == scenario_name})
            for campaign_id in campaign_ids:
                treated = by_key[(scenario_name, campaign_id, policy)]
                baseline = by_key[(scenario_name, campaign_id, comparator)]
                out.append((campaign_id, float(treated[metric]), float(baseline[metric])))
        return out

    for scenario in primary_scenarios:
        campaign_ids = sorted({str(row["campaign_id"]) for row in runs if row["scenario"] == scenario})
        for campaign_id in campaign_ids:
            treated = by_key[(scenario, campaign_id, PRIMARY_POLICY)]
            baseline = by_key[(scenario, campaign_id, COMPARATOR)]
            primary_pairs.append((campaign_id, float(treated["early_auc"]), float(baseline["early_auc"])))
            primary_violation_pairs.append((campaign_id, float(treated["violation_auc"]), float(baseline["violation_auc"])))
    lift_ci = paired_lift_ci(primary_pairs)
    violation_ci = paired_diff_ci(primary_violation_pairs, seed=BOOTSTRAP_SEED + 5)
    mismatch_guard = [
        row
        for row in runs
        if row["scenario"] == "unsupported_mismatch" and row["initialization"] == PRIMARY_POLICY
    ]
    null_lift_ci = paired_lift_ci(collect_pairs(["null_stationary"], PRIMARY_POLICY, COMPARATOR, "early_auc"), seed=BOOTSTRAP_SEED + 7)
    unsupported_blind_vs_global = paired_lift_ci(collect_pairs(["unsupported_mismatch"], "contextual_idvc", "global_flat_idvc", "early_auc"), seed=BOOTSTRAP_SEED + 8)
    unsupported_guard_vs_historical = paired_lift_ci(collect_pairs(["unsupported_mismatch"], PRIMARY_POLICY, COMPARATOR, "early_auc"), seed=BOOTSTRAP_SEED + 9)
    negative_controls = {
        "null_stationary_guarded_vs_historical": null_lift_ci,
        "unsupported_contextual_vs_global": unsupported_blind_vs_global,
        "unsupported_guarded_vs_historical": unsupported_guard_vs_historical,
        "unsupported_guard_abstention_rate": mean(1.0 if row["abstained"] else 0.0 for row in mismatch_guard),
        "pass": (
            isinstance(null_lift_ci.get("hi"), float)
            and null_lift_ci["hi"] <= 0.02
            and isinstance(unsupported_blind_vs_global.get("hi"), float)
            and unsupported_blind_vs_global["hi"] < 0.0
            and isinstance(unsupported_guard_vs_historical.get("hi"), float)
            and unsupported_guard_vs_historical["hi"] <= 0.02
            and mean(1.0 if row["abstained"] else 0.0 for row in mismatch_guard) >= 0.95
        ),
    }
    pass_gate = (
        isinstance(lift_ci.get("clusters"), int)
        and lift_ci["clusters"] >= MIN_BOOTSTRAP_CLUSTERS
        and isinstance(lift_ci.get("lo"), float)
        and lift_ci["lo"] > 0.0
        and isinstance(violation_ci.get("hi"), float)
        and violation_ci["hi"] <= 0.0
        and mean(1.0 if row["abstained"] else 0.0 for row in mismatch_guard) >= 0.95
        and bool(negative_controls["pass"])
    )
    gate = {
        "bridge_pass": pass_gate,
        "primary_policy": PRIMARY_POLICY,
        "primary_comparator": COMPARATOR,
        "primary_scenarios": list(primary_scenarios),
        "contact_lift_ci": lift_ci,
        "violation_diff_ci": violation_ci,
        "mismatch_abstention_rate": mean(1.0 if row["abstained"] else 0.0 for row in mismatch_guard),
        "negative_controls": negative_controls,
        "uncertainty_scope": "cluster bootstrap over synthetic campaign/context clusters conditional on the frozen scenario registry; not empirical BAT uncertainty",
        "minimum_bootstrap_clusters": MIN_BOOTSTRAP_CLUSTERS,
        "required_manuscript_consequence": (
            "Bridge may be reported as BAT-shaped known-transform synthetic mechanism evidence, not public-BAT deployment lift."
            if pass_gate
            else "Bridge gate failed; do not use it as positive decision evidence."
        ),
    }
    return {
        "generated_by": "experiments/run_supported_bridge.py",
        "bridge_type": "BAT-shaped semi-synthetic supported bridge",
        "claim_boundary": "Mechanism evidence with BAT-shaped support and injected known response transforms; not unchanged public-BAT deployment lift.",
        "scenario_registry": registry,
        "seed": seed,
        "seeds": seeds,
        "contexts": contexts,
        "horizons": list(HORIZONS),
        "scenarios": list(registry),
        "initializations": list(INITIALIZATIONS),
        "runs": runs if include_runs else [],
        "summary": summary,
        "gate_status": gate,
    }


def scaled_registry(shift_multiplier: float, response_multiplier: float) -> dict[str, dict[str, float | str]]:
    registry: dict[str, dict[str, float | str]] = {}
    for name, spec in SCENARIO_REGISTRY.items():
        item: dict[str, float | str] = {}
        for key, value in spec.items():
            if key == "response_factor":
                item[key] = float(value) * response_multiplier
            elif key in {"history_shift", "global_shift", "context_shift", "target_level_shift", "abrupt_after"}:
                item[key] = float(value) * shift_multiplier
            else:
                item[key] = value
        registry[name] = item
    return registry


def run_sensitivity(seeds: int, contexts: int, seed: int) -> dict[str, object]:
    rows = []
    for shift_multiplier in SENSITIVITY_GRID:
        for response_multiplier in SENSITIVITY_GRID:
            payload = run_bridge(
                seeds=seeds,
                contexts=contexts,
                seed=seed,
                registry=scaled_registry(shift_multiplier, response_multiplier),
                include_runs=False,
            )
            gate = payload["gate_status"]
            lift = gate["contact_lift_ci"]
            violation = gate["violation_diff_ci"]
            rows.append(
                {
                    "shift_multiplier": shift_multiplier,
                    "response_multiplier": response_multiplier,
                    "bridge_pass": gate["bridge_pass"],
                    "contact_lift_lo": lift["lo"],
                    "contact_lift_mean": lift["mean"],
                    "violation_diff_hi": violation["hi"],
                    "negative_controls_pass": gate["negative_controls"]["pass"],
                }
            )
    return {
        "grid": list(SENSITIVITY_GRID),
        "rows": rows,
        "all_pass": all(bool(row["bridge_pass"]) for row in rows),
        "min_contact_lift_lo": min(float(row["contact_lift_lo"]) for row in rows if isinstance(row["contact_lift_lo"], float)),
        "max_violation_diff_hi": max(float(row["violation_diff_hi"]) for row in rows if isinstance(row["violation_diff_hi"], float)),
    }


def markdown_table(rows: list[list[object]]) -> str:
    if not rows:
        return ""
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    out = []
    header = "| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(rows[0])) + " |"
    out.append(header)
    out.append("| " + " | ".join("-" * widths[i] for i in range(len(widths))) + " |")
    for row in rows[1:]:
        out.append("| " + " | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)) + " |")
    return "\n".join(out)


def render_report(payload: Mapping[str, object]) -> str:
    rows = [["scenario", "initialization", "runs", "early_auc", "lift_vs_hist", "violation_auc", "ttt", "abstain"]]
    for row in payload["summary"]:
        rows.append(
            [
                row["scenario"],
                row["initialization"],
                row["runs"],
                f"{row['early_auc_mean']:.4f}",
                f"{row['early_auc_lift_vs_historical']:.4f}" if row["early_auc_lift_vs_historical"] is not None else "NA",
                f"{row['violation_auc_mean']:.4f}",
                row["time_to_target_median"],
                f"{row['abstention_rate']:.3f}",
            ]
        )
    gate = payload["gate_status"]
    sensitivity = payload.get("sensitivity", {})
    sensitivity_line = ""
    if isinstance(sensitivity, Mapping) and sensitivity:
        sensitivity_line = (
            f"- Sensitivity grid pass: `{sensitivity.get('all_pass')}`; "
            f"min lower lift CI `{sensitivity.get('min_contact_lift_lo')}`; "
            f"max violation upper CI `{sensitivity.get('max_violation_diff_hi')}`"
        )
    return "\n".join(
        [
            "# Supported BAT-Shaped Bridge",
            "",
            f"- Claim boundary: {payload['claim_boundary']}",
            f"- Seeds: `{payload['seeds']}`",
            f"- Contexts: `{payload['contexts']}`",
            f"- Bridge pass: `{gate['bridge_pass']}`",
            f"- Primary contact lift CI: `{gate['contact_lift_ci']}`",
            f"- Primary violation diff CI: `{gate['violation_diff_ci']}`",
            f"- Uncertainty scope: {gate['uncertainty_scope']}",
            f"- Mismatch abstention rate: `{gate['mismatch_abstention_rate']:.3f}`",
            f"- Negative controls: `{gate['negative_controls']}`",
            sensitivity_line,
            "",
            markdown_table(rows),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=100)
    parser.add_argument("--contexts", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260522)
    parser.add_argument("--no-sensitivity", action="store_true")
    parser.add_argument("--out", default="experiments/results/supported_bridge.json")
    parser.add_argument("--report", default="experiments/results/supported_bridge.md")
    args = parser.parse_args()

    payload = run_bridge(seeds=args.seeds, contexts=args.contexts, seed=args.seed)
    if not args.no_sensitivity:
        payload["sensitivity"] = run_sensitivity(seeds=args.seeds, contexts=args.contexts, seed=args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    Path(args.report).write_text(render_report(payload), encoding="utf-8")
    print(f"Wrote {args.out}")
    print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
