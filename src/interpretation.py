"""Short conclusions derived from each run, with explicit evidence boundaries."""

from __future__ import annotations


def observations(task: str, payload: dict) -> list[str]:
    if task == "warm_start":
        summary = payload["summary"]
        negative = {row["scenario"]: row["negative_transfer_rate"]
                    for row in summary["negative_transfer"]}
        return [
            "Initial states are prescribed around a known synthetic target; no dual surface is fitted here.",
            "Reward is max(0, 1 - 1.4 * absolute state error). Violation is excess state error above tolerance, not budget or CPC overspend.",
            f"Blind contextual transfer loses more than 2% against the global prior in {negative['fpa_blind_vs_response']:.1%} of FPA-bias runs and {negative['mismatched_prior']:.1%} of mismatched-prior runs.",
            "The mismatch negative control supplies the scenario label to the guard. Abstention accuracy is not a real-data detector score.",
            "Forest-plot intervals use independent seeds, averaging related scenarios within each seed. The comparator is the ex-post historical/global envelope.",
        ]
    if task == "supported_bridge":
        gate = payload["gate_status"]
        lift, violation = gate["contact_lift_ci"], gate["violation_diff_ci"]
        notes = [
            "Synthetic scalar states and additive response biases are specified by the scenario registry. This runner does not read BAT, fit (s, alpha), or invert an auction bid map.",
            f"Guarded vs historical early-AUC: {100 * lift['mean']:+.3f}% (95% cluster CI [{100 * lift['lo']:+.3f}, {100 * lift['hi']:+.3f}]%). State-violation difference: {violation['mean']:+.5f}.",
            f"Primary gate: {'PASS' if gate['bridge_pass'] else 'FAIL'}; negative controls: {'PASS' if gate['negative_controls']['pass'] else 'FAIL'}. These are conditional simulation results, not contact or deployment lift.",
        ]
        if "sensitivity" in payload:
            sensitivity = payload["sensitivity"]
            notes.append(f"Sensitivity: {sum(bool(row['bridge_pass']) for row in sensitivity['rows'])}/{len(sensitivity['rows'])} cells pass.")
        return notes
    notes = []
    if payload["mode"] != "full":
        notes.append("Row-capped pipeline check; these numbers do not replace the full-data reference results.")
    for auction, result in payload["auctions"].items():
        models = {row["model"]: row.get("test_tcl_mse")
                  for row in result.get("heldout_baselines", {}).get("models", [])}
        flat, contextual, flexible = (models.get(name) for name in
                                     ("flat_admissible_idvc", "contextual_admissible_idvc", "category_price_mean"))
        if all(value is not None for value in (flat, contextual, flexible)):
            notes.append(f"{auction.upper()} held-out proxy MSE: flat {flat:.4f}, contextual {contextual:.4f}, category-price mean {flexible:.4f} (lower is better).")
    notes.append("The target is AuctionWinBidSurplus / max(AuctionCount, 1), with a declared fallback. Admissibility does not make this proxy a structural dual label or establish bidding improvement.")
    return notes
