#!/usr/bin/env python3
"""Deterministic tests for cold-start frontier utilities."""

from __future__ import annotations

from src.bat_cold_start_runner import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    FIXED_HORIZONS,
    HISTORICAL_POLICY,
    MIN_BOOTSTRAP_CLUSTERS,
    PRIMARY_COMPARATOR,
    PRIMARY_POLICY,
    SCALAR_GRID,
    VIOLATION_MULTIPLIER,
    gate_status,
    paired_bootstrap_ci,
    paired_bootstrap_lift_ci,
    select_frontier_scales,
    support_label,
)


def assert_close(actual: float | None, expected: float, tol: float = 1e-12) -> None:
    assert actual is not None
    assert abs(actual - expected) <= tol, (actual, expected)


def test_support_strata() -> None:
    assert support_label(10, 3.0) == "low_ok"
    assert support_label(500, 3.0) == "medium_ok"
    assert support_label(5001, 3.0) == "high_ok"
    assert support_label(5001, None) == "high_weak"
    assert support_label(5001, 100001.0) == "high_weak"


def test_protocol_constants_are_frozen() -> None:
    assert tuple(FIXED_HORIZONS) == ("first_period", "first_3", "first_6", "first_12", "first_24")
    assert SCALAR_GRID == (0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00)
    assert BOOTSTRAP_SEED == 20260522
    assert BOOTSTRAP_RESAMPLES == 1000
    assert MIN_BOOTSTRAP_CLUSTERS == 30
    assert VIOLATION_MULTIPLIER == 1.05
    assert PRIMARY_POLICY == "shrunk_contextual_idvc"
    assert PRIMARY_COMPARATOR == HISTORICAL_POLICY


def test_frontier_selects_best_feasible_scale() -> None:
    rows = [
        {"policy": HISTORICAL_POLICY, "scale": 1.0, "contacts_early_auc": 100.0, "budget_violation_auc": 10.0},
        {"policy": "contextual_admissible_idvc", "scale": 1.0, "contacts_early_auc": 110.0, "budget_violation_auc": 10.5},
        {"policy": "contextual_admissible_idvc", "scale": 2.0, "contacts_early_auc": 130.0, "budget_violation_auc": 30.0},
    ]
    selected = select_frontier_scales(rows)
    assert selected["contextual_admissible_idvc"]["scale"] == 1.0
    assert selected["contextual_admissible_idvc"]["selected_from_feasible_set"] is True
    assert selected[HISTORICAL_POLICY]["scale"] == 1.0
    assert selected[HISTORICAL_POLICY]["comparator_locked"] is True


def test_frontier_records_infeasible_selection() -> None:
    rows = [
        {"policy": HISTORICAL_POLICY, "scale": 1.0, "contacts_early_auc": 100.0, "budget_violation_auc": 10.0},
        {"policy": "flat_admissible_idvc", "scale": 1.0, "contacts_early_auc": 110.0, "budget_violation_auc": 20.0},
        {"policy": "flat_admissible_idvc", "scale": 2.0, "contacts_early_auc": 120.0, "budget_violation_auc": 30.0},
    ]
    selected = select_frontier_scales(rows)
    assert selected["flat_admissible_idvc"]["scale"] == 2.0
    assert selected["flat_admissible_idvc"]["selected_from_feasible_set"] is False


def test_bootstrap_is_reproducible() -> None:
    pairs = [(2.0, 1.0), (4.0, 2.0), (8.0, 4.0)]
    first = paired_bootstrap_ci(pairs, seed=7, resamples=25)
    second = paired_bootstrap_ci(pairs, seed=7, resamples=25)
    assert first == second
    assert_close(first["mean"], 7.0 / 3.0)
    lift = paired_bootstrap_lift_ci(pairs, seed=7, resamples=25)
    assert_close(lift["mean"], 1.0)


def test_gate_status_semantics() -> None:
    passing = {
        "paired_bootstrap_vs_historical": {
            "policies": {
                PRIMARY_POLICY: {
                    "contact_lift": {"n": 30, "lo": 0.01, "hi": 0.03},
                    "budget_violation_auc_diff": {"lo": -1.0, "hi": 0.0},
                }
            }
        }
    }
    assert gate_status(passing)["unchanged_bat_pass"] is True
    failing = {
        "paired_bootstrap_vs_historical": {
            "policies": {
                PRIMARY_POLICY: {
                    "contact_lift": {"n": 30, "lo": -0.01, "hi": 0.03},
                    "budget_violation_auc_diff": {"lo": -1.0, "hi": 1.0},
                }
            }
        }
    }
    assert gate_status(failing)["unchanged_bat_pass"] is False
    ineligible = gate_status(passing, evidentiary_run=False, ineligible_reason="smoke")
    assert ineligible["unchanged_bat_pass"] is False
    assert ineligible["evidentiary_run"] is False


def main() -> int:
    test_support_strata()
    test_protocol_constants_are_frozen()
    test_frontier_selects_best_feasible_scale()
    test_frontier_records_infeasible_selection()
    test_bootstrap_is_reproducible()
    test_gate_status_semantics()
    print("cold-start frontier tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
