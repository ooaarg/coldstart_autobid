#!/usr/bin/env python3
"""Campaign-level cold-start replay for public BAT.

The replay is intentionally conservative about what BAT can identify. It uses
BAT surplus columns as public simulator-style proxy curves, splits campaigns by
start time, and evaluates first-period decisions for held-out campaigns.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping

from src.experiment_utils import (
    ADMISSIBLE_ALPHA_MAX,
    ADMISSIBLE_ALPHA_MIN,
    ADMISSIBLE_S_MIN,
    EPS,
    OLS2Accumulator,
    bat_row_from_csv,
    ensure_dir,
    fmt,
    iter_csv_rows,
    markdown_table,
    parse_float,
    parse_key,
    sniff_columns,
    utc_now,
    write_json,
)
from src.bat_runner import BASE_URL, FILES


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


FIXED_HORIZONS = {"first_period": 1, "first_3": 3, "first_6": 6, "first_12": 12, "first_24": 24}
SHARE_HORIZONS = {"first_5pct_lifetime": 0.05, "first_10pct_lifetime": 0.10, "first_20pct_lifetime": 0.20}
SCALAR_GRID = (0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00)
VIOLATION_MULTIPLIER = 1.05
BOOTSTRAP_SEED = 20260522
BOOTSTRAP_RESAMPLES = 1000
MIN_BOOTSTRAP_CLUSTERS = 30
HISTORICAL_POLICY = "historical_stationary_context_bin"
DEPLOYABLE_POLICIES = (
    "global_feasible_bin",
    HISTORICAL_POLICY,
    "flat_admissible_idvc",
    "contextual_admissible_idvc",
    "shrunk_contextual_idvc",
)
POLICY_NAMES = (*DEPLOYABLE_POLICIES, "oracle_ex_post_feasible_bin")
PRIMARY_POLICY = "shrunk_contextual_idvc"
PRIMARY_COMPARATOR = HISTORICAL_POLICY


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    item_id: str
    start: float
    end: float | None
    budget: float
    context: str
    planned_periods: int

    @property
    def key(self) -> tuple[str, str]:
        return self.campaign_id, self.item_id


@dataclass
class BinMetrics:
    bin_value: float
    visibility: float = 0.0
    clicks: float = 0.0
    contacts: float = 0.0
    win_bid: float = 0.0
    auctions: float = 0.0
    v_sum: float = 0.0
    cpc_mu_sum: float = 0.0
    rows: int = 0

    def add(self, bat) -> None:
        self.visibility += bat.visibility_surplus or 0.0
        self.clicks += bat.clicks_surplus or 0.0
        self.contacts += bat.contacts_surplus or 0.0
        self.win_bid += bat.win_bid_surplus or 0.0
        self.auctions += bat.auction_count or 0.0
        if bat.v is not None:
            self.v_sum += bat.v
        if bat.mu is not None and bat.contact_price_bin is not None:
            self.cpc_mu_sum += bat.contact_price_bin * bat.mu
        self.rows += 1

    @property
    def mean_v(self) -> float:
        return self.v_sum / self.rows if self.rows else 0.0

    @property
    def mean_cpc_mu(self) -> float:
        return self.cpc_mu_sum / self.rows if self.rows else 0.0


@dataclass
class Candidate:
    bin_value: float
    visibility: float
    clicks: float
    contacts: float
    spend: float
    auctions: float
    mean_v: float
    mean_cpc_mu: float


@dataclass
class PeriodState:
    campaign: Campaign
    period: str
    bins: dict[float, BinMetrics] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str, str]:
        return self.campaign.campaign_id, self.campaign.item_id, self.period

    def add(self, bat) -> None:
        if bat.contact_price_bin is None:
            return
        bucket = self.bins.get(bat.contact_price_bin)
        if bucket is None:
            bucket = BinMetrics(bin_value=bat.contact_price_bin)
            self.bins[bat.contact_price_bin] = bucket
        bucket.add(bat)

    def candidates(self, auction: str) -> list[Candidate]:
        out: list[Candidate] = []
        visibility = clicks = contacts = win_bid = auctions = 0.0
        for bin_value in sorted(self.bins):
            item = self.bins[bin_value]
            visibility += item.visibility
            clicks += item.clicks
            contacts += item.contacts
            win_bid += item.win_bid
            auctions += item.auctions
            if auction == "fpa":
                spend = (1.2 ** bin_value) * contacts
            else:
                spend = win_bid
            out.append(
                Candidate(
                    bin_value=bin_value,
                    visibility=visibility,
                    clicks=clicks,
                    contacts=contacts,
                    spend=spend,
                    auctions=auctions,
                    mean_v=item.mean_v,
                    mean_cpc_mu=item.mean_cpc_mu,
                )
            )
        return out


@dataclass
class PolicyAggregate:
    contacts: float = 0.0
    clicks: float = 0.0
    visibility: float = 0.0
    spend: float = 0.0
    budget: float = 0.0
    violation: float = 0.0
    periods: int = 0
    campaigns: set[tuple[str, str]] = field(default_factory=set)

    def add(self, state: PeriodState, candidate: Candidate, budget: float) -> None:
        self.contacts += candidate.contacts
        self.clicks += candidate.clicks
        self.visibility += candidate.visibility
        self.spend += candidate.spend
        self.budget += budget
        self.violation += max(0.0, candidate.spend - budget)
        self.periods += 1
        self.campaigns.add(state.campaign.key)

    def to_json(self, baseline_contacts: float | None = None) -> dict[str, object]:
        contact_lift = None
        if baseline_contacts is not None and abs(baseline_contacts) > EPS:
            contact_lift = (self.contacts - baseline_contacts) / baseline_contacts
        return {
            "campaigns": len(self.campaigns),
            "periods": self.periods,
            "contacts": self.contacts,
            "clicks": self.clicks,
            "visibility": self.visibility,
            "spend": self.spend,
            "budget": self.budget,
            "budget_violation_area": self.violation,
            "cost_per_contact": self.spend / self.contacts if self.contacts > EPS else None,
            "budget_utilization": self.spend / self.budget if self.budget > EPS else None,
            "contact_lift_vs_historical_stationary": contact_lift,
        }


def load_campaigns(source: str, max_campaigns: int | None, timeout: int) -> tuple[dict[tuple[str, str], Campaign], dict[str, object]]:
    campaigns: list[Campaign] = []
    rows_seen = 0
    skipped = Counter()
    for row in iter_csv_rows(source, timeout=timeout):
        rows_seen += 1
        campaign_id = parse_key(row.get("campaign_id"))
        item_id = parse_key(row.get("item_id"))
        start = parse_float(row.get("campaign_start"))
        end = parse_float(row.get("campaign_end"))
        budget = parse_float(row.get("auction_budget"))
        logical_category = parse_key(row.get("logical_category"))
        if not campaign_id or not item_id or start is None or budget is None:
            skipped["missing_required"] += 1
            continue
        if end is not None and end > start:
            planned_periods = max(1, int(math.ceil((end - start) / 3600.0)))
        else:
            planned_periods = 1
            skipped["missing_declared_duration"] += 1
        context = f"logical_category:{logical_category}" if logical_category else "logical_category:missing"
        campaigns.append(Campaign(campaign_id, item_id, start, end, budget, context, planned_periods))
    campaigns.sort(key=lambda c: (c.start, c.campaign_id, c.item_id))
    if max_campaigns is not None:
        campaigns = campaigns[:max_campaigns]
    meta = {campaign.key: campaign for campaign in campaigns}
    report = {
        "rows_seen": rows_seen,
        "campaigns_loaded": len(campaigns),
        "skipped": dict(skipped),
        "truncated_campaigns": max_campaigns is not None,
        "budget_schedule_rule": "declared campaign duration from campaign_start/campaign_end, measured in hourly periods",
        "planned_periods_min": min((c.planned_periods for c in campaigns), default=None),
        "planned_periods_max": max((c.planned_periods for c in campaigns), default=None),
    }
    return meta, report


def split_campaigns(campaigns: Mapping[tuple[str, str], Campaign]) -> dict[str, set[tuple[str, str]]]:
    ordered = sorted(campaigns.values(), key=lambda c: (c.start, c.campaign_id, c.item_id))
    n = len(ordered)
    n_train = int(math.floor(0.70 * n))
    n_val = int(math.floor(0.10 * n))
    train = ordered[:n_train]
    validation = ordered[n_train : n_train + n_val]
    test = ordered[n_train + n_val :]
    return {
        "train": {c.key for c in train},
        "validation": {c.key for c in validation},
        "train_validation": {c.key for c in train + validation},
        "test": {c.key for c in test},
    }


def add_fit_row(acc: OLS2Accumulator, bat) -> bool:
    y, _ = bat.y
    if bat.v is None or bat.mu is None or bat.contact_price_bin is None or y is None:
        return False
    x0 = bat.v
    x1 = bat.contact_price_bin * bat.mu
    if abs(x0) <= EPS and abs(x1) <= EPS:
        return False
    acc.add(x0, x1, y)
    return True


def collect_states_and_fits(
    auction: str,
    stats_source: str,
    campaigns: Mapping[tuple[str, str], Campaign],
    split: Mapping[str, set[tuple[str, str]]],
    max_stats_rows: int | None,
    timeout: int,
) -> dict[str, object]:
    train_keys = split["train"]
    validation_keys = split["validation"]
    test_keys = split["test"]
    flat_fit = OLS2Accumulator()
    context_fit: dict[str, OLS2Accumulator] = defaultdict(OLS2Accumulator)
    train_states: dict[tuple[str, str, str], PeriodState] = {}
    validation_states: dict[tuple[str, str, str], PeriodState] = {}
    test_states: dict[tuple[str, str, str], PeriodState] = {}
    rows_seen = 0
    matched = 0
    fit_rows = 0
    skipped = Counter()

    for row in iter_csv_rows(stats_source, timeout=timeout):
        rows_seen += 1
        bat = bat_row_from_csv(row)
        key = (bat.campaign_id, bat.item_id)
        campaign = campaigns.get(key)
        if campaign is None:
            skipped["campaign_not_in_split"] += 1
        else:
            matched += 1
            state_key = (bat.campaign_id, bat.item_id, bat.period)
            if key in train_keys:
                if add_fit_row(flat_fit, bat):
                    fit_rows += 1
                    add_fit_row(context_fit[campaign.context], bat)
                state = train_states.get(state_key)
                if state is None:
                    state = PeriodState(campaign=campaign, period=bat.period)
                    train_states[state_key] = state
                state.add(bat)
            elif key in validation_keys:
                state = validation_states.get(state_key)
                if state is None:
                    state = PeriodState(campaign=campaign, period=bat.period)
                    validation_states[state_key] = state
                state.add(bat)
            elif key in test_keys:
                state = test_states.get(state_key)
                if state is None:
                    state = PeriodState(campaign=campaign, period=bat.period)
                    test_states[state_key] = state
                state.add(bat)
        if max_stats_rows is not None and rows_seen >= max_stats_rows:
            break

    return {
        "flat_fit": flat_fit,
        "context_fit": context_fit,
        "train_states": train_states,
        "validation_states": validation_states,
        "test_states": test_states,
        "stream_report": {
            "rows_seen": rows_seen,
            "matched_rows": matched,
            "fit_rows": fit_rows,
            "train_period_states": len(train_states),
            "validation_period_states": len(validation_states),
            "test_period_states": len(test_states),
            "skipped": dict(skipped),
        },
    }


def period_budget(state: PeriodState) -> float:
    planned = max(1, state.campaign.planned_periods)
    return state.campaign.budget / planned


def nearest_candidate(candidates: list[Candidate], target: float) -> Candidate:
    return min(candidates, key=lambda c: (abs(c.bin_value - target), c.bin_value))


def candidate_at_or_below(candidates: list[Candidate], target_bin: float) -> Candidate:
    eligible = [candidate for candidate in candidates if candidate.bin_value <= target_bin + 1e-9]
    if eligible:
        return eligible[-1]
    return candidates[0]


def oracle_candidate(candidates: list[Candidate], budget: float) -> Candidate:
    feasible = [candidate for candidate in candidates if candidate.spend <= budget + 1e-9]
    pool = feasible if feasible else candidates
    return max(
        pool,
        key=lambda c: (
            c.contacts,
            -max(0.0, c.spend - budget),
            -c.spend,
            c.bin_value,
        ),
    )


def shrink_beta(
    context_beta: tuple[float | None, float | None] | None,
    flat_beta: tuple[float | None, float | None],
    context_rows: int,
    strength: float = 500.0,
) -> tuple[float | None, float | None]:
    if context_beta is None:
        return flat_beta
    if any(x is None for x in context_beta):
        return flat_beta
    if any(x is None for x in flat_beta):
        return context_beta
    weight = context_rows / (context_rows + strength) if context_rows > 0 else 0.0
    return (
        weight * float(context_beta[0]) + (1.0 - weight) * float(flat_beta[0]),
        weight * float(context_beta[1]) + (1.0 - weight) * float(flat_beta[1]),
    )


def train_fixed_bins(
    states: Iterable[PeriodState],
    auction: str,
    min_context_periods: int,
) -> dict[str, object]:
    by_context_bin: dict[str, dict[float, PolicyAggregate]] = defaultdict(lambda: defaultdict(PolicyAggregate))
    global_bin: dict[float, PolicyAggregate] = defaultdict(PolicyAggregate)
    context_periods = Counter()
    for state in states:
        candidates = state.candidates(auction)
        if not candidates:
            continue
        budget = period_budget(state)
        context_periods[state.campaign.context] += 1
        for candidate in candidates:
            by_context_bin[state.campaign.context][candidate.bin_value].add(state, candidate, budget)
            global_bin[candidate.bin_value].add(state, candidate, budget)

    def choose_bin(options: Mapping[float, PolicyAggregate]) -> float | None:
        feasible = [
            (bin_value, aggregate)
            for bin_value, aggregate in options.items()
            if aggregate.spend <= aggregate.budget + 1e-9
        ]
        pool = feasible if feasible else list(options.items())
        if not pool:
            return None
        return max(pool, key=lambda kv: (kv[1].contacts, -kv[1].violation, -kv[1].spend, kv[0]))[0]

    global_choice = choose_bin(global_bin)
    context_choices: dict[str, float] = {}
    fallbacks = 0
    for context, options in by_context_bin.items():
        if context_periods[context] >= min_context_periods:
            chosen = choose_bin(options)
            if chosen is not None:
                context_choices[context] = chosen
                continue
        fallbacks += 1
    return {
        "global_bin": global_choice,
        "context_bins": context_choices,
        "context_period_support": dict(context_periods),
        "fallback_contexts": fallbacks,
        "min_context_periods": min_context_periods,
    }


def idvc_candidate(auction: str, candidates: list[Candidate], beta: tuple[float | None, float | None]) -> Candidate:
    s, alpha = beta
    if s is None or alpha is None:
        return candidates[0]
    scored = []
    for candidate in candidates:
        target = s * candidate.mean_v + alpha * candidate.mean_cpc_mu
        comparable_bid = (1.2 ** candidate.bin_value) if auction == "fpa" else candidate.bin_value
        scored.append((abs(comparable_bid - target), candidate.bin_value, candidate))
    return min(scored, key=lambda item: (item[0], item[1]))[2]


def support_bucket(context_rows: int) -> str:
    if context_rows < 500:
        return "low"
    if context_rows <= 5000:
        return "medium"
    return "high"


def support_label(context_rows: int, gram_condition: float | None) -> str:
    weak = gram_condition is None or gram_condition > 1e5
    return f"{support_bucket(context_rows)}_{'weak' if weak else 'ok'}"


def display_ci_value(value: object, n: object) -> object:
    if not isinstance(n, int) or n < MIN_BOOTSTRAP_CLUSTERS:
        return "NA_insufficient_clusters"
    return value


def policy_candidate(
    policy: str,
    auction: str,
    candidates: list[Candidate],
    state: PeriodState,
    fixed_bins: Mapping[str, object],
    flat_beta: tuple[float | None, float | None],
    context_betas: Mapping[str, tuple[float | None, float | None]],
    context_rows: Mapping[str, int],
    scale: float,
    budget: float,
) -> tuple[Candidate, bool]:
    global_bin = fixed_bins.get("global_bin")
    context_bins = fixed_bins.get("context_bins", {})
    if not isinstance(context_bins, Mapping):
        context_bins = {}

    if policy == "global_feasible_bin":
        if global_bin is None:
            return candidates[0], True
        return candidate_at_or_below(candidates, float(global_bin) * scale), False

    if policy == HISTORICAL_POLICY:
        context_bin = context_bins.get(state.campaign.context)
        fallback = context_bin is None
        if context_bin is None:
            context_bin = global_bin
        if context_bin is None:
            return candidates[0], True
        return candidate_at_or_below(candidates, float(context_bin) * scale), fallback

    if policy == "flat_admissible_idvc":
        return idvc_candidate(auction, candidates, (flat_beta[0] * scale if flat_beta[0] is not None else None, flat_beta[1] * scale if flat_beta[1] is not None else None)), False

    if policy == "contextual_admissible_idvc":
        beta = context_betas.get(state.campaign.context)
        fallback = beta is None
        if beta is None:
            beta = flat_beta
        return idvc_candidate(auction, candidates, (beta[0] * scale if beta[0] is not None else None, beta[1] * scale if beta[1] is not None else None)), fallback

    if policy == "shrunk_contextual_idvc":
        beta = shrink_beta(context_betas.get(state.campaign.context), flat_beta, context_rows.get(state.campaign.context, 0))
        fallback = state.campaign.context not in context_betas
        return idvc_candidate(auction, candidates, (beta[0] * scale if beta[0] is not None else None, beta[1] * scale if beta[1] is not None else None)), fallback

    if policy == "oracle_ex_post_feasible_bin":
        return oracle_candidate(candidates, budget), False

    raise ValueError(f"unknown policy: {policy}")


def quantile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * p))))
    return ordered[idx]


def paired_bootstrap_ci(
    pairs: list[tuple[float, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float | int | None]:
    if not pairs:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    diffs = [treated - baseline for treated, baseline in pairs]
    mean_diff = sum(diffs) / len(diffs)
    rng = random.Random(seed)
    draws: list[float] = []
    n = len(diffs)
    for _ in range(resamples):
        draws.append(sum(diffs[rng.randrange(n)] for _ in range(n)) / n)
    return {"n": n, "mean": mean_diff, "lo": quantile(draws, 0.025), "hi": quantile(draws, 0.975)}


def paired_bootstrap_lift_ci(
    pairs: list[tuple[float, float]],
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, float | int | None]:
    if not pairs:
        return {"n": 0, "mean": None, "lo": None, "hi": None}
    treated_total = sum(t for t, _ in pairs)
    baseline_total = sum(b for _, b in pairs)
    mean_lift = (treated_total - baseline_total) / baseline_total if abs(baseline_total) > EPS else None
    rng = random.Random(seed)
    draws: list[float] = []
    n = len(pairs)
    for _ in range(resamples):
        sample_t = 0.0
        sample_b = 0.0
        for _ in range(n):
            treated, baseline = pairs[rng.randrange(n)]
            sample_t += treated
            sample_b += baseline
        if abs(sample_b) > EPS:
            draws.append((sample_t - sample_b) / sample_b)
    return {"n": n, "mean": mean_lift, "lo": quantile(draws, 0.025), "hi": quantile(draws, 0.975)}


def select_frontier_scales(
    frontier_rows: list[dict[str, object]],
    violation_multiplier: float = VIOLATION_MULTIPLIER,
) -> dict[str, dict[str, object]]:
    baseline_rows = [
        row
        for row in frontier_rows
        if row.get("policy") == HISTORICAL_POLICY and abs(float(row.get("scale", 1.0)) - 1.0) <= EPS
    ]
    baseline_violation = float(baseline_rows[0].get("budget_violation_auc", 0.0)) if baseline_rows else 0.0
    allowed_violation = baseline_violation * violation_multiplier + EPS
    selected: dict[str, dict[str, object]] = {}
    def as_float(value: object, default: float = 0.0) -> float:
        return float(value) if isinstance(value, (float, int)) else default

    for policy in DEPLOYABLE_POLICIES:
        if policy == PRIMARY_COMPARATOR:
            selected[policy] = {
                "scale": 1.0,
                "selected_from_feasible_set": True,
                "allowed_budget_violation_auc": allowed_violation,
                "validation_contacts_early_auc": baseline_rows[0].get("contacts_early_auc") if baseline_rows else None,
                "validation_budget_violation_auc": baseline_rows[0].get("budget_violation_auc") if baseline_rows else None,
                "validation_budget_utilization_auc": baseline_rows[0].get("budget_utilization_auc") if baseline_rows else None,
                "validation_cost_per_contact_auc": baseline_rows[0].get("cost_per_contact_auc") if baseline_rows else None,
                "comparator_locked": True,
            }
            continue
        rows = [row for row in frontier_rows if row.get("policy") == policy]
        feasible = [row for row in rows if float(row.get("budget_violation_auc", 0.0)) <= allowed_violation]
        pool = feasible if feasible else rows
        if not pool:
            continue
        best = max(
            pool,
            key=lambda row: (
                as_float(row.get("contacts_early_auc")),
                -as_float(row.get("budget_violation_auc")),
                -abs(as_float(row.get("budget_utilization_auc")) - 1.0),
                -as_float(row.get("scale"), 1.0),
            ),
        )
        selected[policy] = {
            "scale": best.get("scale"),
            "selected_from_feasible_set": best in feasible,
            "allowed_budget_violation_auc": allowed_violation,
            "validation_contacts_early_auc": best.get("contacts_early_auc"),
            "validation_budget_violation_auc": best.get("budget_violation_auc"),
            "validation_budget_utilization_auc": best.get("budget_utilization_auc"),
            "validation_cost_per_contact_auc": best.get("cost_per_contact_auc"),
        }
    return selected


def gate_status(
    evaluation: Mapping[str, object],
    evidentiary_run: bool = True,
    ineligible_reason: str | None = None,
) -> dict[str, object]:
    boot = evaluation.get("paired_bootstrap_vs_historical", {})
    policies = boot.get("policies", {}) if isinstance(boot, Mapping) else {}
    primary = policies.get(PRIMARY_POLICY) if isinstance(policies, Mapping) else None
    if not evidentiary_run:
        return {
            "primary_policy": PRIMARY_POLICY,
            "primary_comparator": PRIMARY_COMPARATOR,
            "evidentiary_run": False,
            "ineligible_reason": ineligible_reason or "Capped or non-final run.",
            "unchanged_bat_pass": False,
            "endpoint_lower_ci_positive": False,
            "constraint_upper_ci_nonpositive": False,
            "minimum_bootstrap_clusters": MIN_BOOTSTRAP_CLUSTERS,
            "bootstrap_clusters": None,
            "required_manuscript_consequence": "This is a smoke/non-evidentiary run; do not claim unchanged public-BAT decision lift.",
        }
    if not isinstance(primary, Mapping):
        return {
            "primary_policy": PRIMARY_POLICY,
            "primary_comparator": PRIMARY_COMPARATOR,
            "evidentiary_run": True,
            "unchanged_bat_pass": False,
            "endpoint_lower_ci_positive": False,
            "constraint_upper_ci_nonpositive": False,
            "minimum_bootstrap_clusters": MIN_BOOTSTRAP_CLUSTERS,
            "bootstrap_clusters": None,
            "required_manuscript_consequence": "No primary BAT frontier gate was computed; do not claim unchanged public-BAT decision lift.",
        }
    lift = primary.get("contact_lift", {})
    violation = primary.get("budget_violation_auc_diff", {})
    lift_lo = lift.get("lo") if isinstance(lift, Mapping) else None
    lift_n = lift.get("n") if isinstance(lift, Mapping) else None
    violation_hi = violation.get("hi") if isinstance(violation, Mapping) else None
    enough_clusters = isinstance(lift_n, int) and lift_n >= MIN_BOOTSTRAP_CLUSTERS
    endpoint_positive = enough_clusters and isinstance(lift_lo, (float, int)) and float(lift_lo) > 0.0
    constraint_ok = enough_clusters and isinstance(violation_hi, (float, int)) and float(violation_hi) <= 0.0
    unchanged_pass = endpoint_positive and constraint_ok
    return {
        "primary_policy": PRIMARY_POLICY,
        "primary_comparator": PRIMARY_COMPARATOR,
        "evidentiary_run": True,
        "primary_endpoint": "campaign-clustered total contact lift in fixed-horizon early-AUC over horizons 1,3,6,12,24",
        "endpoint_lower_ci_positive": endpoint_positive,
        "constraint_upper_ci_nonpositive": constraint_ok,
        "minimum_bootstrap_clusters": MIN_BOOTSTRAP_CLUSTERS,
        "bootstrap_clusters": lift_n,
        "unchanged_bat_pass": unchanged_pass,
        "contact_lift_ci": lift,
        "budget_violation_auc_diff_ci": violation,
        "required_manuscript_consequence": (
            "May report unchanged public-BAT constrained decision improvement for the primary contrast."
            if unchanged_pass
            else "Unchanged public BAT remains boundary evidence; do not claim public-BAT deployment lift."
        ),
    }


def evaluate_policies(
    auction: str,
    states: Mapping[tuple[str, str, str], PeriodState],
    fixed_bins: Mapping[str, object],
    flat_beta: tuple[float | None, float | None],
    context_betas: Mapping[str, tuple[float | None, float | None]],
    context_rows: Mapping[str, int],
    context_conditions: Mapping[str, float | None],
    min_context_rows: int,
    policy_scales: Mapping[str, float] | None = None,
    include_bootstrap: bool = False,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
) -> dict[str, object]:
    by_campaign: dict[tuple[str, str], list[PeriodState]] = defaultdict(list)
    for state in states.values():
        if state.bins:
            by_campaign[state.campaign.key].append(state)
    for states in by_campaign.values():
        states.sort(key=lambda s: float(s.period) if str(s.period).replace(".", "", 1).isdigit() else s.period)

    policy_scales = dict(policy_scales or {})
    for policy in POLICY_NAMES:
        policy_scales.setdefault(policy, 1.0)

    payload: dict[str, object] = {}
    horizon_specs: list[tuple[str, int | float, str]] = [
        (name, periods, "fixed_observed_periods") for name, periods in FIXED_HORIZONS.items()
    ]
    horizon_specs.extend((name, share, "observed_lifetime_share") for name, share in SHARE_HORIZONS.items())

    fixed_campaign_values: dict[str, dict[tuple[str, str], list[dict[str, float]]]] = {
        policy: defaultdict(list) for policy in POLICY_NAMES
    }

    for horizon_name, horizon_value, horizon_type in horizon_specs:
        aggregates = {name: PolicyAggregate() for name in POLICY_NAMES}
        support_aggregates: dict[str, dict[str, PolicyAggregate]] = defaultdict(lambda: {name: PolicyAggregate() for name in POLICY_NAMES})
        fallbacks = Counter()
        for campaign_key, campaign_states in by_campaign.items():
            if horizon_type == "observed_lifetime_share":
                horizon_periods = max(1, int(math.ceil(len(campaign_states) * float(horizon_value))))
            else:
                horizon_periods = int(horizon_value)
            campaign_aggregates = {name: PolicyAggregate() for name in POLICY_NAMES}
            for state in campaign_states[:horizon_periods]:
                candidates = state.candidates(auction)
                if not candidates:
                    continue
                budget = period_budget(state)
                stratum = support_label(context_rows.get(state.campaign.context, 0), context_conditions.get(state.campaign.context))
                for policy in POLICY_NAMES:
                    candidate, fallback = policy_candidate(
                        policy=policy,
                        auction=auction,
                        candidates=candidates,
                        state=state,
                        fixed_bins=fixed_bins,
                        flat_beta=flat_beta,
                        context_betas=context_betas,
                        context_rows=context_rows,
                        scale=float(policy_scales.get(policy, 1.0)),
                        budget=budget,
                    )
                    if fallback:
                        fallbacks[policy] += 1
                    aggregates[policy].add(state, candidate, budget)
                    support_aggregates[stratum][policy].add(state, candidate, budget)
                    campaign_aggregates[policy].add(state, candidate, budget)

            if horizon_type == "fixed_observed_periods":
                for policy, aggregate in campaign_aggregates.items():
                    fixed_campaign_values[policy][campaign_key].append(
                        {
                            "contacts": aggregate.contacts,
                            "budget_violation_area": aggregate.violation,
                            "spend": aggregate.spend,
                            "budget": aggregate.budget,
                            "cost_per_contact": aggregate.spend / aggregate.contacts if aggregate.contacts > EPS else 0.0,
                            "budget_utilization": aggregate.spend / aggregate.budget if aggregate.budget > EPS else 0.0,
                        }
                    )

        baseline = aggregates["historical_stationary_context_bin"].contacts
        payload[horizon_name] = {
            "horizon_type": horizon_type,
            "horizon_value": horizon_value,
            "policy_scales": {policy: policy_scales.get(policy, 1.0) for policy in POLICY_NAMES},
            "policies": {
                name: aggregate.to_json(baseline_contacts=baseline)
                for name, aggregate in aggregates.items()
            },
            "support_strata": {
                stratum: {
                    name: aggregate.to_json(baseline_contacts=support_aggregates[stratum][HISTORICAL_POLICY].contacts)
                    for name, aggregate in policies.items()
                }
                for stratum, policies in sorted(support_aggregates.items())
            },
            "fallback_decisions": dict(fallbacks),
            "min_context_rows": min_context_rows,
            "oracle_note": "oracle_ex_post_feasible_bin is a diagnostic upper reference chosen with test-period surplus curves.",
        }

    auc_rows: dict[str, dict[str, float | None]] = {}
    fixed_names = list(FIXED_HORIZONS)
    for policy in POLICY_NAMES:
        curves: dict[str, list[float]] = {
            "contacts": [],
            "budget_violation_area": [],
            "spend": [],
            "budget": [],
            "cost_per_contact": [],
            "budget_utilization": [],
        }
        baseline_curve: list[float] = []
        for h in fixed_names:
            if not (
                isinstance(payload.get(h), Mapping)
                and isinstance(payload[h].get("policies"), Mapping)
                and policy in payload[h]["policies"]
            ):
                continue
            metrics = payload[h]["policies"][policy]
            for key in curves:
                value = metrics.get(key)
                if isinstance(value, (float, int)):
                    curves[key].append(float(value))
            baseline_metrics = payload[h]["policies"].get(HISTORICAL_POLICY)
            if isinstance(baseline_metrics, Mapping) and isinstance(baseline_metrics.get("contacts"), (float, int)):
                baseline_curve.append(float(baseline_metrics["contacts"]))
        contacts_curve = curves["contacts"]
        if contacts_curve:
            auc = sum(contacts_curve) / len(contacts_curve)
            baseline_auc = sum(baseline_curve) / len(baseline_curve) if baseline_curve else None
            auc_rows[policy] = {
                "fixed_horizons": ",".join(fixed_names),
                "contacts_early_auc": auc,
                "contacts_early_auc_lift_vs_historical": (
                    (auc - baseline_auc) / baseline_auc
                    if baseline_auc is not None and abs(baseline_auc) > EPS
                    else None
                ),
                "budget_violation_auc": sum(curves["budget_violation_area"]) / len(curves["budget_violation_area"]) if curves["budget_violation_area"] else None,
                "spend_auc": sum(curves["spend"]) / len(curves["spend"]) if curves["spend"] else None,
                "budget_auc": sum(curves["budget"]) / len(curves["budget"]) if curves["budget"] else None,
                "cost_per_contact_auc": sum(curves["cost_per_contact"]) / len(curves["cost_per_contact"]) if curves["cost_per_contact"] else None,
                "budget_utilization_auc": sum(curves["budget_utilization"]) / len(curves["budget_utilization"]) if curves["budget_utilization"] else None,
            }
    payload["early_auc_fixed_horizons"] = auc_rows

    campaign_auc: dict[str, dict[str, dict[str, float]]] = {}
    for policy, by_key in fixed_campaign_values.items():
        campaign_auc[policy] = {}
        for campaign_key, horizon_values in by_key.items():
            if not horizon_values:
                continue
            contacts_auc = sum(v["contacts"] for v in horizon_values) / len(horizon_values)
            violation_auc = sum(v["budget_violation_area"] for v in horizon_values) / len(horizon_values)
            spend_auc = sum(v["spend"] for v in horizon_values) / len(horizon_values)
            budget_auc = sum(v["budget"] for v in horizon_values) / len(horizon_values)
            campaign_auc[policy]["|".join(campaign_key)] = {
                "contacts_early_auc": contacts_auc,
                "budget_violation_auc": violation_auc,
                "spend_auc": spend_auc,
                "budget_auc": budget_auc,
                "cost_per_contact_auc": spend_auc / contacts_auc if contacts_auc > EPS else 0.0,
                "budget_utilization_auc": spend_auc / budget_auc if budget_auc > EPS else 0.0,
            }

    if include_bootstrap and HISTORICAL_POLICY in campaign_auc:
        bootstrap: dict[str, object] = {}
        baseline_campaigns = campaign_auc[HISTORICAL_POLICY]
        denominator_campaigns = len(by_campaign)
        for policy in POLICY_NAMES:
            if policy == HISTORICAL_POLICY or policy not in campaign_auc:
                continue
            keys = sorted(set(campaign_auc[policy]) & set(baseline_campaigns))
            contact_pairs = [(campaign_auc[policy][key]["contacts_early_auc"], baseline_campaigns[key]["contacts_early_auc"]) for key in keys]
            violation_pairs = [(campaign_auc[policy][key]["budget_violation_auc"], baseline_campaigns[key]["budget_violation_auc"]) for key in keys]
            utilization_pairs = [(campaign_auc[policy][key]["budget_utilization_auc"], baseline_campaigns[key]["budget_utilization_auc"]) for key in keys]
            cpc_pairs = [(campaign_auc[policy][key]["cost_per_contact_auc"], baseline_campaigns[key]["cost_per_contact_auc"]) for key in keys]
            bootstrap[policy] = {
                "eligible_campaigns_with_public_stats": denominator_campaigns,
                "paired_campaigns": len(keys),
                "excluded_campaigns": max(0, denominator_campaigns - len(keys)),
                "inclusion_rule": "campaign has at least one evaluated public stats period for both the policy and historical comparator over fixed horizons",
                "contact_lift": paired_bootstrap_lift_ci(contact_pairs, seed=bootstrap_seed, resamples=bootstrap_resamples),
                "contact_auc_diff": paired_bootstrap_ci(contact_pairs, seed=bootstrap_seed + 1, resamples=bootstrap_resamples),
                "budget_violation_auc_diff": paired_bootstrap_ci(violation_pairs, seed=bootstrap_seed + 2, resamples=bootstrap_resamples),
                "budget_utilization_auc_diff": paired_bootstrap_ci(utilization_pairs, seed=bootstrap_seed + 3, resamples=bootstrap_resamples),
                "cost_per_contact_auc_diff": paired_bootstrap_ci(cpc_pairs, seed=bootstrap_seed + 4, resamples=bootstrap_resamples),
            }
        payload["paired_bootstrap_vs_historical"] = {
            "seed": bootstrap_seed,
            "resamples": bootstrap_resamples,
            "cluster": "campaign",
            "policies": bootstrap,
        }
    return payload


def frontier_rows(
    auction: str,
    validation_states: Mapping[tuple[str, str, str], PeriodState],
    fixed_bins: Mapping[str, object],
    flat_beta: tuple[float | None, float | None],
    context_betas: Mapping[str, tuple[float | None, float | None]],
    context_rows: Mapping[str, int],
    context_conditions: Mapping[str, float | None],
    min_context_rows: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for scale in SCALAR_GRID:
        scales = {policy: scale for policy in DEPLOYABLE_POLICIES}
        result = evaluate_policies(
            auction=auction,
            states=validation_states,
            fixed_bins=fixed_bins,
            flat_beta=flat_beta,
            context_betas=context_betas,
            context_rows=context_rows,
            context_conditions=context_conditions,
            min_context_rows=min_context_rows,
            policy_scales=scales,
        )
        auc = result.get("early_auc_fixed_horizons", {})
        if not isinstance(auc, Mapping):
            continue
        for policy in DEPLOYABLE_POLICIES:
            metrics = auc.get(policy)
            if not isinstance(metrics, Mapping):
                continue
            rows.append(
                {
                    "policy": policy,
                    "scale": scale,
                    "contacts_early_auc": metrics.get("contacts_early_auc"),
                    "contacts_early_auc_lift_vs_historical": metrics.get("contacts_early_auc_lift_vs_historical"),
                    "budget_violation_auc": metrics.get("budget_violation_auc"),
                    "budget_utilization_auc": metrics.get("budget_utilization_auc"),
                    "cost_per_contact_auc": metrics.get("cost_per_contact_auc"),
                }
            )
    return rows


def run_one_auction(
    auction: str,
    stats_source: str,
    campaign_source: str,
    max_campaigns: int | None,
    max_stats_rows: int | None,
    min_context_rows: int,
    min_context_periods: int,
    timeout: int,
) -> dict[str, object]:
    stats_columns = sniff_columns(stats_source, timeout=timeout)
    campaign_columns = sniff_columns(campaign_source, timeout=timeout)
    campaigns, campaign_report = load_campaigns(campaign_source, max_campaigns=max_campaigns, timeout=timeout)
    split = split_campaigns(campaigns)
    collected = collect_states_and_fits(
        auction=auction,
        stats_source=stats_source,
        campaigns=campaigns,
        split=split,
        max_stats_rows=max_stats_rows,
        timeout=timeout,
    )
    train_states = collected["train_states"]
    validation_states = collected["validation_states"]
    test_states = collected["test_states"]
    flat_fit: OLS2Accumulator = collected["flat_fit"]
    context_fit: Mapping[str, OLS2Accumulator] = collected["context_fit"]
    fixed_bins = train_fixed_bins(
        train_states.values(),
        auction=auction,
        min_context_periods=min_context_periods,
    )
    flat_beta = flat_fit.admissible_coefficients()
    context_betas: dict[str, tuple[float | None, float | None]] = {}
    context_rows: dict[str, int] = {}
    context_conditions: dict[str, float | None] = {}
    weak_design_contexts = 0
    violation_counts = Counter()
    for context, acc in context_fit.items():
        context_rows[context] = acc.n
        condition = acc.gram_eigen()[2]
        context_conditions[context] = condition
        if condition is None or condition > 1e5:
            weak_design_contexts += 1
        if acc.n < min_context_rows:
            continue
        stats = acc.fit_stats()
        diagnostics = stats.get("admissible", {})
        if isinstance(diagnostics, Mapping):
            for key in (
                "unconstrained_s_below_min",
                "unconstrained_alpha_below_zero",
                "unconstrained_alpha_above_one",
            ):
                if diagnostics.get(key):
                    violation_counts[key] += 1
        context_betas[context] = acc.admissible_coefficients()
    evaluation = evaluate_policies(
        auction=auction,
        states=test_states,
        fixed_bins=fixed_bins,
        flat_beta=flat_beta,
        context_betas=context_betas,
        context_rows=context_rows,
        context_conditions=context_conditions,
        min_context_rows=min_context_rows,
    )
    validation_frontier = frontier_rows(
        auction=auction,
        validation_states=validation_states,
        fixed_bins=fixed_bins,
        flat_beta=flat_beta,
        context_betas=context_betas,
        context_rows=context_rows,
        context_conditions=context_conditions,
        min_context_rows=min_context_rows,
    )
    selected = select_frontier_scales(validation_frontier)
    selected_scales = {
        policy: float(meta.get("scale", 1.0))
        for policy, meta in selected.items()
        if isinstance(meta, Mapping)
    }
    selected_evaluation = evaluate_policies(
        auction=auction,
        states=test_states,
        fixed_bins=fixed_bins,
        flat_beta=flat_beta,
        context_betas=context_betas,
        context_rows=context_rows,
        context_conditions=context_conditions,
        min_context_rows=min_context_rows,
        policy_scales=selected_scales,
        include_bootstrap=True,
        bootstrap_seed=BOOTSTRAP_SEED,
        bootstrap_resamples=BOOTSTRAP_RESAMPLES,
    )
    evidentiary_run = max_campaigns is None and max_stats_rows is None
    selected_gate = gate_status(
        selected_evaluation,
        evidentiary_run=evidentiary_run,
        ineligible_reason=None if evidentiary_run else "Acceptance-evidence runs require --max-campaigns and --max-stats-rows to be unset.",
    )
    return {
        "auction": auction,
        "stats_source": stats_source,
        "campaign_source": campaign_source,
        "stats_columns": stats_columns,
        "campaign_columns": campaign_columns,
        "campaign_report": campaign_report,
        "split": {name: len(keys) for name, keys in split.items()},
        "period_count_report": "not used for budget scheduling; declared campaign_start/campaign_end duration is used instead",
        "stream_report": collected["stream_report"],
        "max_campaigns": max_campaigns,
        "max_stats_rows": max_stats_rows,
        "truncated_stats": max_stats_rows is not None,
        "period_budget_rule": "auction_budget / declared planned duration in hourly periods from campaign_start/campaign_end",
        "vcg_spend_rule": "cumulative AuctionWinBidSurplus",
        "fpa_spend_rule": "1.2 ** contact_price_bin times cumulative AuctionContactsSurplus",
        "target_interpretation": (
            "Public BAT cold-start replay uses BAT surplus curves as simulator-style proxy outcomes; "
            "AuctionWinBidSurplus/AuctionCount is not treated as a raw winning-price label."
        ),
        "flat_admissible_fit": flat_fit.fit_stats().get("admissible"),
        "contextual_admissible_contexts": len(context_betas),
        "contextual_admissible_context_rows": context_rows,
        "contextual_gram_conditions": context_conditions,
        "shrunk_contextual_idvc_rule": "theta_shrunk = w * theta_context + (1-w) * theta_flat, w = n_context / (n_context + 500)",
        "contextual_weak_design_contexts": weak_design_contexts,
        "contextual_unconstrained_violation_counts": dict(violation_counts),
        "fixed_bin_policy": fixed_bins,
        "frontier_protocol": {
            "primary_endpoint": "mean fixed-horizon contacts early-AUC over first 1, 3, 6, 12, and 24 observed periods",
            "primary_contrast": f"{PRIMARY_POLICY} vs {PRIMARY_COMPARATOR}",
            "scalar_grid": list(SCALAR_GRID),
            "selection_split": "validation campaigns only",
            "test_split": "chronological final 20% campaigns",
            "final_run_required_limits": {"max_campaigns": None, "max_stats_rows": None},
            "constraint_rule": f"choose max validation early-AUC subject to budget-violation AUC <= {VIOLATION_MULTIPLIER}x historical_stationary at scale 1; if no scale is feasible choose best reported infeasible scale",
            "historical_comparator_rule": "historical_stationary_context_bin is locked at scale 1.00 for the primary paired CI and feasibility threshold",
            "period_budget_observability": "uses declared campaign_start/campaign_end duration from the campaign table; no test-period outcome count is used for budget scheduling",
            "bootstrap": {"cluster": "campaign", "seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES},
        },
        "validation_frontier": validation_frontier,
        "selected_policy_scales": selected,
        "gate_status": selected_gate,
        "frontier_selected_test": selected_evaluation,
        "cold_start": evaluation,
    }


def local_or_remote_source(args: argparse.Namespace, auction: str, kind: str) -> str:
    override = getattr(args, f"{auction}_{kind}")
    if override:
        return override
    local = LOCAL_DEFAULTS[auction][kind]
    if os.path.exists(local):
        return local
    return FILES[auction][kind]


def render_markdown(payload: Mapping[str, object]) -> str:
    rows = [["auction", "horizon", "policy", "campaigns", "contacts", "clicks", "spend", "budget viol.", "util.", "CPC", "contact lift"]]
    auc_rows = [["auction", "policy", "fixed horizons", "contacts early-AUC", "early-AUC lift", "viol. AUC", "util. AUC"]]
    frontier_rows_md = [["auction", "policy", "scale", "validation AUC", "validation viol.", "selected feasible"]]
    bootstrap_rows = [["auction", "policy", "evidentiary", "clusters", "min clusters", "resamples", "contact lift mean", "contact lift lo", "contact lift hi", "viol. diff mean", "viol. diff lo", "viol. diff hi", "ineligible reason"]]
    attrition_rows = [["auction", "split test campaigns", "public-stats campaigns", "paired primary clusters", "excluded from paired CI", "inclusion rule"]]
    support_rows = [["auction", "horizon", "stratum", "support rule", "policy", "campaigns", "fallbacks", "contacts", "contact lift", "budget viol.", "util."]]
    auctions = payload.get("auctions", {})
    if isinstance(auctions, Mapping):
        for auction, result in auctions.items():
            if not isinstance(result, Mapping):
                continue
            cold = result.get("cold_start", {})
            if not isinstance(cold, Mapping):
                continue
            for horizon, hres in cold.items():
                policies = hres.get("policies", {}) if isinstance(hres, Mapping) else {}
                if not isinstance(policies, Mapping):
                    continue
                for policy, metrics in policies.items():
                    if not isinstance(metrics, Mapping):
                        continue
                    rows.append(
                        [
                            str(auction).upper(),
                            horizon,
                            policy,
                            metrics.get("campaigns"),
                            fmt(metrics.get("contacts")),
                            fmt(metrics.get("clicks")),
                            fmt(metrics.get("spend")),
                            fmt(metrics.get("budget_violation_area")),
                            fmt(metrics.get("budget_utilization")),
                            fmt(metrics.get("cost_per_contact")),
                            fmt(metrics.get("contact_lift_vs_historical_stationary")),
                        ]
                    )
            auc = cold.get("early_auc_fixed_horizons", {}) if isinstance(cold, Mapping) else {}
            if isinstance(auc, Mapping):
                for policy, metrics in auc.items():
                    if not isinstance(metrics, Mapping):
                        continue
                    auc_rows.append(
                        [
                            str(auction).upper(),
                            policy,
                            metrics.get("fixed_horizons"),
                            fmt(metrics.get("contacts_early_auc")),
                            fmt(metrics.get("contacts_early_auc_lift_vs_historical")),
                            fmt(metrics.get("budget_violation_auc")),
                            fmt(metrics.get("budget_utilization_auc")),
                        ]
                    )
            selected = result.get("selected_policy_scales", {})
            if isinstance(selected, Mapping):
                for policy, meta in selected.items():
                    if not isinstance(meta, Mapping):
                        continue
                    frontier_rows_md.append(
                        [
                            str(auction).upper(),
                            policy,
                            fmt(meta.get("scale")),
                            fmt(meta.get("validation_contacts_early_auc")),
                            fmt(meta.get("validation_budget_violation_auc")),
                            meta.get("selected_from_feasible_set"),
                        ]
                    )
            selected_test = result.get("frontier_selected_test", {})
            if isinstance(selected_test, Mapping):
                boot = selected_test.get("paired_bootstrap_vs_historical", {})
                boot_policies = boot.get("policies", {}) if isinstance(boot, Mapping) else {}
                if isinstance(boot_policies, Mapping):
                    gate = result.get("gate_status", {})
                    evidentiary = gate.get("evidentiary_run") if isinstance(gate, Mapping) else None
                    ineligible = gate.get("ineligible_reason") if isinstance(gate, Mapping) else None
                    for policy, metrics in boot_policies.items():
                        if not isinstance(metrics, Mapping):
                            continue
                        lift = metrics.get("contact_lift", {})
                        viol = metrics.get("budget_violation_auc_diff", {})
                        n = lift.get("n") if isinstance(lift, Mapping) else None
                        bootstrap_rows.append(
                            [
                                str(auction).upper(),
                                policy,
                                evidentiary,
                                n,
                                MIN_BOOTSTRAP_CLUSTERS,
                                boot.get("resamples") if isinstance(boot, Mapping) else None,
                                fmt(lift.get("mean") if isinstance(lift, Mapping) else None),
                                fmt(display_ci_value(lift.get("lo"), n) if isinstance(lift, Mapping) else None),
                                fmt(display_ci_value(lift.get("hi"), n) if isinstance(lift, Mapping) else None),
                                fmt(viol.get("mean") if isinstance(viol, Mapping) else None),
                                fmt(display_ci_value(viol.get("lo"), n) if isinstance(viol, Mapping) else None),
                                fmt(display_ci_value(viol.get("hi"), n) if isinstance(viol, Mapping) else None),
                                ineligible,
                            ]
                        )
                    primary_boot = boot_policies.get(PRIMARY_POLICY)
                    if isinstance(primary_boot, Mapping):
                        split = result.get("split", {})
                        split_test = split.get("test") if isinstance(split, Mapping) else None
                        paired = primary_boot.get("paired_campaigns")
                        public_campaigns = primary_boot.get("eligible_campaigns_with_public_stats")
                        attrition_rows.append(
                            [
                                str(auction).upper(),
                                split_test,
                                public_campaigns,
                                paired,
                                primary_boot.get("excluded_campaigns"),
                                primary_boot.get("inclusion_rule"),
                            ]
                        )
                for horizon in FIXED_HORIZONS:
                    hres = selected_test.get(horizon)
                    strata = hres.get("support_strata", {}) if isinstance(hres, Mapping) else {}
                    if not isinstance(strata, Mapping):
                        continue
                    for stratum, policies in strata.items():
                        if not isinstance(policies, Mapping):
                            continue
                        for policy, metrics in policies.items():
                            if not isinstance(metrics, Mapping):
                                continue
                            support_rows.append(
                                [
                                    str(auction).upper(),
                                    horizon,
                                    stratum,
                                    "low<500; medium<=5000; high>5000; weak cond missing/>1e5",
                                    policy,
                                    metrics.get("campaigns"),
                                    hres.get("fallback_decisions", {}).get(policy) if isinstance(hres.get("fallback_decisions"), Mapping) else None,
                                    fmt(metrics.get("contacts")),
                                    fmt(metrics.get("contact_lift_vs_historical_stationary")),
                                    fmt(metrics.get("budget_violation_area")),
                                    fmt(metrics.get("budget_utilization")),
                                ]
                            )

    lines = [
        "# BAT Campaign Cold-Start Replay",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Dataset: [AvitoTech/BAT]({BASE_URL})",
        "- Split: campaigns sorted by `campaign_start`; first 70% train, next 10% validation, final 20% test.",
        "- Cold-start horizons: first 1, 3, 6, 12, and 24 observed periods, plus first 5%, 10%, and 20% of observed campaign lifetime.",
        "- Spend mapping: VCG uses cumulative `AuctionWinBidSurplus`; FPA uses `1.2 ** contact_price_bin` times cumulative contacts.",
        "- Budget mapping: per-period budget uses declared `campaign_start`/`campaign_end` duration from the BAT campaign table; no test-period outcome count is used for budget scheduling.",
        "- BAT surplus fields are simulator-style public proxy outcomes, not raw winning-price or raw payment logs.",
        "- `oracle_ex_post_feasible_bin` is a diagnostic upper reference chosen from test-period proxy surplus curves, not a deployable baseline.",
        "",
        "## Decision Metrics",
        "",
        markdown_table(rows),
        "",
        "## Early-AUC Over Fixed Horizons",
        "",
        markdown_table(auc_rows) if len(auc_rows) > 1 else "No early-AUC metrics were available.",
        "",
        "## Validation-Tuned Frontier",
        "",
        "The historical stationary fixed-bin baseline is locked at scale `1.00` for the primary comparator; scalar-tuned historical variants are not used as the primary comparator.",
        "",
        markdown_table(frontier_rows_md) if len(frontier_rows_md) > 1 else "No frontier selection was available.",
        "",
        "## Test Bootstrap For Selected Frontier",
        "",
        f"Paired intervals cluster by campaign with `{BOOTSTRAP_RESAMPLES}` resamples and require at least `{MIN_BOOTSTRAP_CLUSTERS}` campaign clusters for evidentiary CIs. Smoke/capped runs are non-evidentiary even when numeric diagnostics are present.",
        "",
        markdown_table(bootstrap_rows) if len(bootstrap_rows) > 1 else "No paired bootstrap was available.",
        "",
        "### Paired-CI Inclusion",
        "",
        "Campaign-level CIs use campaigns with at least one evaluated public-stats period for both the selected policy and the historical comparator over the fixed horizons; campaigns without public stats rows after the chronological split are counted as attrition, not as zero-outcome campaigns.",
        "",
        markdown_table(attrition_rows) if len(attrition_rows) > 1 else "No paired-CI inclusion diagnostics were available.",
        "",
        "## Gate Status",
        "",
        markdown_table([
            ["auction", "evidentiary", "primary policy", "pass", "endpoint CI ok", "constraint CI ok", "consequence"],
            *[
                [
                    str(auction).upper(),
                    result.get("gate_status", {}).get("evidentiary_run") if isinstance(result.get("gate_status"), Mapping) else None,
                    result.get("gate_status", {}).get("primary_policy") if isinstance(result.get("gate_status"), Mapping) else None,
                    result.get("gate_status", {}).get("unchanged_bat_pass") if isinstance(result.get("gate_status"), Mapping) else None,
                    result.get("gate_status", {}).get("endpoint_lower_ci_positive") if isinstance(result.get("gate_status"), Mapping) else None,
                    result.get("gate_status", {}).get("constraint_upper_ci_nonpositive") if isinstance(result.get("gate_status"), Mapping) else None,
                    result.get("gate_status", {}).get("required_manuscript_consequence") if isinstance(result.get("gate_status"), Mapping) else None,
                ]
                for auction, result in (auctions.items() if isinstance(auctions, Mapping) else [])
                if isinstance(result, Mapping)
            ],
        ]),
        "",
        "## Support-Stratified Selected Test Replay",
        "",
        "Support rule: low `<500` training rows, medium `500-5000`, high `>5000`; weak means Gram condition is missing or `>1e5`.",
        "",
        markdown_table(support_rows) if len(support_rows) > 1 else "No support-stratified replay was available.",
        "",
        "## Split And Fit Diagnostics",
        "",
    ]
    diag_rows = [["auction", "campaigns", "train", "validation", "test", "train states", "validation states", "test states", "flat s", "flat alpha", "ctx fits"]]
    if isinstance(auctions, Mapping):
        for auction, result in auctions.items():
            if not isinstance(result, Mapping):
                continue
            split = result.get("split", {})
            stream = result.get("stream_report", {})
            flat = result.get("flat_admissible_fit", {})
            diag_rows.append(
                [
                    str(auction).upper(),
                    result.get("campaign_report", {}).get("campaigns_loaded") if isinstance(result.get("campaign_report"), Mapping) else None,
                    split.get("train") if isinstance(split, Mapping) else None,
                    split.get("validation") if isinstance(split, Mapping) else None,
                    split.get("test") if isinstance(split, Mapping) else None,
                    stream.get("train_period_states") if isinstance(stream, Mapping) else None,
                    stream.get("validation_period_states") if isinstance(stream, Mapping) else None,
                    stream.get("test_period_states") if isinstance(stream, Mapping) else None,
                    fmt(flat.get("admissible_beta_v") if isinstance(flat, Mapping) else None),
                    fmt(flat.get("admissible_beta_cpc_mu") if isinstance(flat, Mapping) else None),
                    result.get("contextual_admissible_contexts"),
                ]
            )
    lines.extend([markdown_table(diag_rows), ""])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="experiments/results")
    parser.add_argument("--json-name", default="bat_cold_start.json")
    parser.add_argument("--md-name", default="bat_cold_start.md")
    parser.add_argument("--only", choices=["both", "vcg", "fpa"], default="both")
    parser.add_argument("--max-campaigns", type=int)
    parser.add_argument("--max-stats-rows", type=int)
    parser.add_argument("--min-context-rows", type=int, default=500)
    parser.add_argument("--min-context-periods", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--jobs", type=int, default=1, help="Parallel auction streams when --only=both; use 2 for local VCG/FPA parallelism.")
    parser.add_argument("--vcg-stats")
    parser.add_argument("--vcg-campaigns")
    parser.add_argument("--fpa-stats")
    parser.add_argument("--fpa-campaigns")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = ["vcg", "fpa"] if args.only == "both" else [args.only]
    payload: dict[str, object] = {
        "generated_at_utc": utc_now(),
        "base_url": BASE_URL,
        "max_campaigns": args.max_campaigns,
        "max_stats_rows": args.max_stats_rows,
        "min_context_rows": args.min_context_rows,
        "min_context_periods": args.min_context_periods,
        "jobs": args.jobs,
        "auctions": {},
    }
    if args.jobs > 1 and len(selected) > 1:
        with ProcessPoolExecutor(max_workers=min(args.jobs, len(selected))) as pool:
            futures = {
                pool.submit(
                    run_one_auction,
                    auction=auction,
                    stats_source=local_or_remote_source(args, auction, "stats"),
                    campaign_source=local_or_remote_source(args, auction, "campaigns"),
                    max_campaigns=args.max_campaigns,
                    max_stats_rows=args.max_stats_rows,
                    min_context_rows=args.min_context_rows,
                    min_context_periods=args.min_context_periods,
                    timeout=args.timeout,
                ): auction
                for auction in selected
            }
            for future in as_completed(futures):
                auction = futures[future]
                payload["auctions"][auction] = future.result()
    else:
        for auction in selected:
            payload["auctions"][auction] = run_one_auction(
                auction=auction,
                stats_source=local_or_remote_source(args, auction, "stats"),
                campaign_source=local_or_remote_source(args, auction, "campaigns"),
                max_campaigns=args.max_campaigns,
                max_stats_rows=args.max_stats_rows,
                min_context_rows=args.min_context_rows,
                min_context_periods=args.min_context_periods,
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
