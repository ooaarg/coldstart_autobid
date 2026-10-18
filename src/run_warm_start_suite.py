#!/usr/bin/env python3
"""Controlled warm-start experiments for implied-dual initialization.

The suite is intentionally dependency-light.  It isolates the paper's empirical
claim as controller x initialization x scenario: every initializer is evaluated
with the same stable residual controller, so differences are attributable to the
starting state rather than controller-specific tuning.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from dataclasses import dataclass
from typing import Iterable, Mapping

from src.config import (
    controller_gain, nonnegative_float, parse_config_args,
    positive_int, print_config, resolved_config,
)


from src.progress import status, track
from src.run_output import start_run, save_run


EPS = 1e-12


@dataclass(frozen=True)
class Settings:
    gain: float = 0.22
    tolerance: float = 0.05
    guard_z: float = 1.65
    shrinkage: float = 6.0


@dataclass(frozen=True)
class Scenario:
    name: str
    auction: str
    base: float
    historical_shift: float
    global_shift: float
    contextual_noise: float
    global_noise: float
    response_bias: float
    drift_amp: float
    step_time: int | None = None
    step_size: float = 0.0
    mismatch: bool = False
    lambda_hybrid: float = 0.0


def mean(xs: Iterable[float]) -> float:
    vals = list(xs)
    return sum(vals) / max(1, len(vals))


def quantile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    vals = sorted(xs)
    pos = p * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def scenario_target(scenario: Scenario, horizon: int) -> list[float]:
    out = []
    for t in range(horizon):
        target = scenario.base + scenario.drift_amp * math.sin(2.0 * math.pi * t / max(1, horizon))
        if scenario.step_time is not None and t >= scenario.step_time:
            target += scenario.step_size
        out.append(target)
    return out


def build_scenarios() -> list[Scenario]:
    return [
        Scenario("matched_stationary", "truthful", 1.18, -0.12, -0.08, 0.025, 0.035, 0.00, 0.00),
        Scenario("smooth_drift", "truthful", 1.16, -0.12, -0.08, 0.030, 0.035, 0.00, 0.14),
        Scenario("abrupt_shift", "truthful", 1.12, -0.16, -0.09, 0.045, 0.040, 0.00, 0.00, step_time=24, step_size=0.24),
        Scenario("mismatched_prior", "truthful", 1.28, -0.42, -0.06, 0.070, 0.035, 0.00, 0.03, mismatch=True),
        Scenario("fpa_blind_vs_response", "fpa", 1.22, -0.07, -0.10, 0.045, 0.040, -0.20, 0.06),
        Scenario("hybrid_lambda_grid", "hybrid", 1.20, -0.07, -0.09, 0.040, 0.040, -0.16, 0.08, lambda_hybrid=0.55),
    ]


def guarded_shrink(contextual: float, flat: float, support_n: int, mismatch_z: float, settings: Settings = Settings()) -> tuple[float, bool, float]:
    if mismatch_z > settings.guard_z:
        return flat, True, 0.0
    weight = support_n / (support_n + settings.shrinkage)
    return weight * contextual + (1.0 - weight) * flat, False, weight


def initialization_states(scenario: Scenario, targets: list[float], rng: random.Random, support_n: int, settings: Settings = Settings()) -> dict[str, dict[str, float | bool]]:
    true0 = targets[0]
    history = true0 + scenario.historical_shift + rng.gauss(0.0, 0.025)
    flat = scenario.base + scenario.global_shift + rng.gauss(0.0, scenario.global_noise)
    contextual = true0 + scenario.contextual_noise * rng.gauss(0.0, 1.0)
    if scenario.mismatch:
        contextual = true0 + scenario.historical_shift + scenario.contextual_noise * rng.gauss(0.0, 1.0)
    blind_contextual = contextual + scenario.response_bias
    response = contextual
    if scenario.auction == "hybrid":
        blind_contextual = contextual + scenario.lambda_hybrid * scenario.response_bias
        response = contextual + 0.15 * scenario.lambda_hybrid * scenario.response_bias
    mismatch_z = abs(blind_contextual - flat) / 0.18
    if scenario.mismatch:
        mismatch_z = max(mismatch_z, 2.1 + 0.4 * rng.random())
    shrunk, abstained, shrinkage_weight = guarded_shrink(blind_contextual, flat, support_n, mismatch_z, settings)
    return {
        "cold_default": {"state": 0.80, "abstained": False, "shrinkage_weight": 0.0},
        "global_flat_idvc": {"state": flat, "abstained": False, "shrinkage_weight": 0.0},
        "historical_stationary": {"state": history, "abstained": False, "shrinkage_weight": 0.0},
        "contextual_idvc": {"state": blind_contextual, "abstained": False, "shrinkage_weight": 1.0},
        "response_idvc": {"state": response, "abstained": False, "shrinkage_weight": 1.0},
        "shrunk_idvc": {"state": shrunk, "abstained": abstained, "shrinkage_weight": shrinkage_weight},
        "oracle_init": {"state": true0, "abstained": False, "shrinkage_weight": 1.0},
    }


def simulate(start: float, targets: list[float], gain: float = 0.22, tolerance: float = 0.05) -> dict[str, object]:
    u = start
    rewards: list[float] = []
    violations: list[float] = []
    distances: list[float] = []
    states: list[float] = []
    ttt = len(targets)
    oscillation = 0.0
    prev = u
    for t, target in enumerate(targets):
        err = u - target
        distance = abs(err)
        reward = max(0.0, 1.0 - 1.40 * distance)
        violation = max(0.0, distance - tolerance)
        if violation <= EPS and ttt == len(targets):
            ttt = t
        rewards.append(reward)
        violations.append(violation)
        distances.append(distance)
        states.append(u)
        u -= gain * err
        oscillation += abs(u - prev)
        prev = u
    cumulative = []
    running = 0.0
    for reward in rewards:
        running += reward
        cumulative.append(running)
    return {
        "reward_h": cumulative[-1],
        "early_auc": mean(cumulative),
        "time_to_target": ttt,
        "early_violation_area": sum(violations[: min(20, len(violations))]),
        "total_violation_area": sum(violations),
        "oscillation": oscillation / max(1, len(targets)),
        "distance_to_oracle_state": distances[0],
        "states": states,
        "cumulative_rewards": cumulative,
        "constraint_violations": violations,
    }


def run_one(seed: int, horizon: int, settings: Settings = Settings()) -> list[dict[str, object]]:
    rng = random.Random(seed)
    rows: list[dict[str, object]] = []
    for scenario in build_scenarios():
        targets = scenario_target(scenario, horizon)
        support_n = rng.randint(2, 18) if scenario.mismatch else rng.randint(12, 80)
        starts = initialization_states(scenario, targets, rng, support_n, settings)
        oracle_reward = None
        scenario_results: dict[str, dict[str, object]] = {}
        for init, meta in starts.items():
            result = simulate(float(meta["state"]), targets, settings.gain, settings.tolerance)
            if init == "oracle_init":
                oracle_reward = float(result["reward_h"])
            scenario_results[init] = result
        for init, result in scenario_results.items():
            rows.append(
                {
                    "seed": seed,
                    "scenario": scenario.name,
                    "auction": scenario.auction,
                    "initialization": init,
                    "support_n": support_n,
                    "mismatched": scenario.mismatch,
                    "abstained": bool(starts[init]["abstained"]),
                    "shrinkage_weight": starts[init]["shrinkage_weight"],
                    "reward_h": result["reward_h"],
                    "early_auc": result["early_auc"],
                    "time_to_target": result["time_to_target"],
                    "early_violation_area": result["early_violation_area"],
                    "total_violation_area": result["total_violation_area"],
                    "oscillation": result["oscillation"],
                    "distance_to_oracle_state": result["distance_to_oracle_state"],
                    "oracle_gap": (
                        (oracle_reward - float(result["reward_h"])) / max(EPS, oracle_reward)
                        if oracle_reward is not None
                        else None
                    ),
                    "cumulative_rewards": result["cumulative_rewards"],
                    "constraint_violations": result["constraint_violations"],
                    "controller_states": result["states"],
                }
            )
    return rows


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["scenario"]), str(row["initialization"])), []).append(row)
    summary_rows = []
    for (scenario, init), items in sorted(grouped.items()):
        historical_auc = mean(
            float(r["early_auc"])
            for r in rows
            if r["scenario"] == scenario and r["initialization"] == "historical_stationary"
        )
        oracle_reward = mean(
            float(r["reward_h"])
            for r in rows
            if r["scenario"] == scenario and r["initialization"] == "oracle_init"
        )
        reward_h = mean(float(r["reward_h"]) for r in items)
        early_auc = mean(float(r["early_auc"]) for r in items)
        summary_rows.append(
            {
                "scenario": scenario,
                "initialization": init,
                "runs": len(items),
                "reward_h_mean": reward_h,
                "reward_h_p10": quantile([float(r["reward_h"]) for r in items], 0.10),
                "reward_h_p90": quantile([float(r["reward_h"]) for r in items], 0.90),
                "early_auc_mean": early_auc,
                "early_auc_lift_vs_historical": (early_auc - historical_auc) / max(EPS, historical_auc),
                "time_to_target_median": statistics.median(float(r["time_to_target"]) for r in items),
                "early_violation_area_mean": mean(float(r["early_violation_area"]) for r in items),
                "oscillation_mean": mean(float(r["oscillation"]) for r in items),
                "distance_to_oracle_state_mean": mean(float(r["distance_to_oracle_state"]) for r in items),
                "oracle_gap_mean": (oracle_reward - reward_h) / max(EPS, oracle_reward),
                "abstention_rate": mean(1.0 if r["abstained"] else 0.0 for r in items),
                "average_shrinkage_weight": mean(float(r["shrinkage_weight"]) for r in items),
            }
        )
    negative_transfer = []
    for scenario in sorted({str(r["scenario"]) for r in rows}):
        seeds = sorted({int(r["seed"]) for r in rows if r["scenario"] == scenario})
        bad = 0
        total = 0
        for seed in seeds:
            contextual = next(r for r in rows if r["scenario"] == scenario and r["seed"] == seed and r["initialization"] == "contextual_idvc")
            flat = next(r for r in rows if r["scenario"] == scenario and r["seed"] == seed and r["initialization"] == "global_flat_idvc")
            if float(contextual["early_auc"]) < 0.98 * float(flat["early_auc"]):
                bad += 1
            total += 1
        negative_transfer.append({"scenario": scenario, "negative_transfer_rate": bad / max(1, total)})
    abstention_accuracy = mean(
        1.0 if bool(r["abstained"]) == bool(r["mismatched"]) else 0.0
        for r in rows
        if r["initialization"] == "shrunk_idvc"
    )
    return {
        "by_scenario_initialization": summary_rows,
        "negative_transfer": negative_transfer,
        "abstention_accuracy": abstention_accuracy,
    }


def render_report(payload: Mapping[str, object]) -> str:
    summary = payload["summary"]
    assert isinstance(summary, Mapping)
    rows = summary["by_scenario_initialization"]
    assert isinstance(rows, list)
    lines = [
        "# Warm-Start Suite",
        "",
        f"- Seeds: `{payload['seeds']}`",
        f"- Horizon: `{payload['horizon']}` synthetic controller updates",
        "- Controller: one stable residual controller shared by all initializations.",
        f"- Guard: abstain when mismatch z-score exceeds `{payload['config']['guard_z']}`; otherwise shrink with `n/(n+{payload['config']['shrinkage']:g})`.",
        "",
        "## Main Metrics",
        "",
        "| Scenario | Initialization | Early-AUC | Lift vs hist. | TTT | Early violation | Oracle gap | Abstain |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    preferred = {"historical_stationary", "contextual_idvc", "response_idvc", "shrunk_idvc", "oracle_init"}
    for row in rows:
        if row["initialization"] not in preferred:
            continue
        lines.append(
            "| {scenario} | {initialization} | {early_auc_mean:.3f} | {early_auc_lift_vs_historical:.3f} | "
            "{time_to_target_median:.1f} | {early_violation_area_mean:.3f} | {oracle_gap_mean:.3f} | {abstention_rate:.2f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Negative Transfer Diagnostics",
            "",
            "| Scenario | Negative-transfer rate |",
            "| --- | ---: |",
        ]
    )
    for row in summary["negative_transfer"]:
        lines.append(f"| {row['scenario']} | {row['negative_transfer_rate']:.3f} |")
    lines.extend(
        [
            "",
            f"Overall guarded-transfer abstention accuracy: `{summary['abstention_accuracy']:.3f}`.",
            "",
            "These are controlled synthetic/semi-synthetic results. They support the warm-start mechanism and failure modes, not a public-BAT FPA deployment claim.",
            "",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--horizon", type=positive_int, help="Controller updates per run")
    parser.add_argument("--seeds", type=positive_int, help="Number of independent seeds")
    parser.add_argument("--seed", type=int, help="First random seed")
    parser.add_argument("--gain", type=controller_gain, help="Residual controller gain (0 < gain < 2)")
    parser.add_argument("--tolerance", type=nonnegative_float, help="Distance tolerance for constraint violations")
    parser.add_argument("--guard-z", type=nonnegative_float, help="Mismatch threshold for abstention")
    parser.add_argument("--shrinkage", type=nonnegative_float, help="Prior support in n/(n+shrinkage)")
    parser.add_argument("--out", help="JSON output path")
    parser.add_argument("--report", help="Markdown report path")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return parse_config_args(build_parser(), "warm_start", argv)


def run(args: argparse.Namespace) -> int:
    started = start_run("warm_start", args)
    status(f"  Simulating {args.seeds} seeds × {args.horizon} controller updates...", args.progress)
    settings = Settings(gain=args.gain, tolerance=args.tolerance,
                        guard_z=args.guard_z, shrinkage=args.shrinkage)
    all_rows: list[dict[str, object]] = []
    for offset in track(range(args.seeds), "Warm start", unit="seed", enabled=args.progress):
        all_rows.extend(run_one(args.seed + offset, args.horizon, settings))
    payload: dict[str, object] = {
        "suite": "warm_start",
        "config": resolved_config(args),
        "seed": args.seed,
        "seeds": args.seeds,
        "horizon": args.horizon,
        "scenarios": [s.__dict__ for s in build_scenarios()],
        "runs": all_rows,
        "summary": summarize(all_rows),
    }
    return save_run("warm_start", args, payload, render_report(payload), started)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_config:
        print_config(args)
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
