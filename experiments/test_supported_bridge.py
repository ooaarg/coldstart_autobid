#!/usr/bin/env python3
"""Deterministic smoke tests for the supported bridge."""

from __future__ import annotations

from run_supported_bridge import (
    COMPARATOR,
    MIN_BOOTSTRAP_CLUSTERS,
    PRIMARY_POLICY,
    PRIMARY_SCENARIOS,
    paired_diff_ci,
    paired_lift_ci,
    run_bridge,
    run_sensitivity,
)


def test_supported_bridge_gate_passes_on_smoke() -> None:
    payload = run_bridge(seeds=3, contexts=12, seed=20260522)
    gate = payload["gate_status"]
    assert gate["primary_policy"] == PRIMARY_POLICY
    assert gate["primary_comparator"] == COMPARATOR
    assert gate["primary_scenarios"] == list(PRIMARY_SCENARIOS)
    assert gate["contact_lift_ci"]["clusters"] >= MIN_BOOTSTRAP_CLUSTERS
    assert gate["bridge_pass"] is True
    assert gate["contact_lift_ci"]["lo"] > 0.0
    assert gate["violation_diff_ci"]["hi"] <= 0.0
    assert gate["mismatch_abstention_rate"] >= 0.95
    assert gate["negative_controls"]["pass"] is True
    assert gate["negative_controls"]["unsupported_guarded_vs_historical"]["hi"] <= 0.02
    assert "not empirical BAT uncertainty" in gate["uncertainty_scope"]


def test_bridge_gate_fails_with_too_few_clusters() -> None:
    payload = run_bridge(seeds=1, contexts=3, seed=20260522)
    assert payload["gate_status"]["contact_lift_ci"]["clusters"] < MIN_BOOTSTRAP_CLUSTERS
    assert payload["gate_status"]["bridge_pass"] is False


def test_paired_ci_fail_modes() -> None:
    negative_pairs = [(f"c{i}", 1.0, 2.0) for i in range(40)]
    lift = paired_lift_ci(negative_pairs, seed=3, resamples=50)
    assert lift["hi"] < 0.0
    worse_violation = [(f"c{i}", 2.0, 1.0) for i in range(40)]
    diff = paired_diff_ci(worse_violation, seed=3, resamples=50)
    assert diff["lo"] > 0.0


def test_sensitivity_grid_passes_on_smoke() -> None:
    sensitivity = run_sensitivity(seeds=3, contexts=12, seed=20260522)
    assert sensitivity["all_pass"] is True
    assert sensitivity["min_contact_lift_lo"] > 0.0
    assert sensitivity["max_violation_diff_hi"] <= 0.0


def main() -> int:
    test_supported_bridge_gate_passes_on_smoke()
    test_bridge_gate_fails_with_too_few_clusters()
    test_paired_ci_fail_modes()
    test_sensitivity_grid_passes_on_smoke()
    print("supported bridge tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
