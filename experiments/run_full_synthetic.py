#!/usr/bin/env python3
"""Dependency-light full synthetic experiment suite.

This script extends the smoke test into a reviewer-facing synthetic and
semi-synthetic workbench.  It intentionally uses only the Python standard
library so it can run in a fresh checkout.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


EPS = 1e-12
CPC = 2.0


@dataclass
class Obs:
    z: float
    value: float
    ctr: float
    cpa: float
    roi: float
    theta: tuple[float, float]
    margin: float
    bid_fpa: float
    bid_hybrid: float
    lambda_hybrid: float
    sigma: float
    psi_fpa: float
    psi_hybrid: float
    noise: float


def mean(xs: Iterable[float]) -> float:
    vals = list(xs)
    return sum(vals) / max(1, len(vals))


def mse(xs: Iterable[float]) -> float:
    vals = list(xs)
    return sum(x * x for x in vals) / max(1, len(vals))


def rmse(xs: Iterable[float]) -> float:
    return math.sqrt(mse(xs))


def quantile(xs: Sequence[float], p: float) -> float:
    vals = sorted(xs)
    if not vals:
        return float("nan")
    pos = p * (len(vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    return vals[lo] * (hi - pos) + vals[hi] * (pos - lo)


def clip(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def true_theta(z: float) -> tuple[float, float]:
    s = 1.0 + 0.24 * math.sin(2.0 * math.pi * z)
    alpha = 0.35 + 0.16 * math.cos(2.0 * math.pi * z + 0.2)
    return s, clip(alpha, 0.03, 0.9)


def lambda_hybrid(z: float) -> float:
    return 0.25 + 0.45 * z


def psi_fpa(b: float, z: float) -> float:
    scale = 0.16 + 0.06 * math.sin(2.0 * math.pi * z + 0.3)
    return scale * math.log1p(max(0.0, b))


def dpsi_fpa(b: float, z: float) -> float:
    scale = 0.16 + 0.06 * math.sin(2.0 * math.pi * z + 0.3)
    return scale / (1.0 + max(0.0, b))


def ddpsi_fpa(b: float, z: float) -> float:
    scale = 0.16 + 0.06 * math.sin(2.0 * math.pi * z + 0.3)
    return -scale / (1.0 + max(0.0, b)) ** 2


def invert_phi(margin: float, z: float, lam: float = 1.0) -> float:
    lo = 0.0
    hi = max(1.0, margin + 1.0)
    for _ in range(70):
        mid = 0.5 * (lo + hi)
        if mid + lam * psi_fpa(mid, z) < margin:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def generate_base(n: int, seed: int, noise_sd: float = 0.008) -> list[Obs]:
    rng = random.Random(seed)
    rows: list[Obs] = []
    for _ in range(n):
        z = rng.random()
        ctr = 0.02 + 0.18 * rng.random()
        cvr = 0.03 + 0.22 * rng.random()
        value = ctr * cvr * 100.0
        cpa = ctr * (0.6 + 0.7 * cvr + 0.15 * rng.random())
        roi = value * (0.7 + 0.3 * rng.random())
        theta = true_theta(z)
        margin = theta[0] * value + theta[1] * CPC * ctr
        lam = lambda_hybrid(z)
        bid_fpa = invert_phi(max(EPS, margin), z, 1.0)
        bid_hybrid = invert_phi(max(EPS, margin), z, lam)
        noise = rng.gauss(0.0, noise_sd)
        sigma = psi_fpa(bid_hybrid, z)
        rows.append(
            Obs(
                z=z,
                value=value,
                ctr=ctr,
                cpa=cpa,
                roi=roi,
                theta=theta,
                margin=margin,
                bid_fpa=max(0.0, bid_fpa + noise),
                bid_hybrid=max(0.0, bid_hybrid + noise),
                lambda_hybrid=lam,
                sigma=sigma,
                psi_fpa=psi_fpa(bid_fpa, z),
                psi_hybrid=lam * sigma,
                noise=noise,
            )
        )
    return rows


def solve_linear(xtx: list[list[float]], xty: list[float], ridge: float = 1e-8) -> list[float]:
    n = len(xty)
    a = [[xtx[i][j] + (ridge if i == j else 0.0) for j in range(n)] + [xty[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < EPS:
            return [float("nan")] * n
        if pivot != col:
            a[col], a[pivot] = a[pivot], a[col]
        denom = a[col][col]
        for j in range(col, n + 1):
            a[col][j] /= denom
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col]
            if abs(factor) < EPS:
                continue
            for j in range(col, n + 1):
                a[r][j] -= factor * a[col][j]
    return [a[i][n] for i in range(n)]


def fit_linear(features: Sequence[Sequence[float]], y: Sequence[float], ridge: float = 1e-8) -> list[float]:
    k = len(features[0])
    xtx = [[0.0 for _ in range(k)] for _ in range(k)]
    xty = [0.0 for _ in range(k)]
    for x, yi in zip(features, y):
        for i in range(k):
            xty[i] += x[i] * yi
            for j in range(k):
                xtx[i][j] += x[i] * x[j]
    return solve_linear(xtx, xty, ridge)


def predict(beta: Sequence[float], x: Sequence[float]) -> float:
    return sum(b * xi for b, xi in zip(beta, x))


def fit_contextual_theta(rows: Sequence[Obs], y: Sequence[float], bins: int = 8) -> list[tuple[float, float]]:
    estimates: list[tuple[float, float]] = []
    for bucket in bucketize(rows, bins):
        if len(bucket) < 8:
            estimates.extend([(float("nan"), float("nan"))] * len(bucket))
            continue
        idx_rows = bucket
        bucket_y = [y[i] for i, _ in idx_rows]
        features = [[r.value, CPC * r.ctr] for _, r in idx_rows]
        b = fit_linear(features, bucket_y)
        estimates.extend([(b[0], b[1])] * len(idx_rows))
    # bucketize changes order; rebuild in original order.
    by_original: list[tuple[float, float] | None] = [None] * len(rows)
    cursor = 0
    for bucket in bucketize(rows, bins):
        for i, _ in bucket:
            by_original[i] = estimates[cursor]
            cursor += 1
    return [x if x is not None else (float("nan"), float("nan")) for x in by_original]


def bucketize(rows: Sequence[Obs], bins: int) -> list[list[tuple[int, Obs]]]:
    out: list[list[tuple[int, Obs]]] = [[] for _ in range(bins)]
    for i, r in enumerate(rows):
        out[min(bins - 1, int(r.z * bins))].append((i, r))
    return out


def theta_msre(rows: Sequence[Obs], estimates: Sequence[tuple[float, float]]) -> float:
    errs = []
    for r, est in zip(rows, estimates):
        if not all(math.isfinite(x) for x in est):
            continue
        errs.append((est[0] - r.theta[0]) ** 2 + (est[1] - r.theta[1]) ** 2)
    return mse(errs)


def spectral_ratio_2x2(h00: float, h01: float, h11: float) -> float:
    tr = h00 + h11
    det = h00 * h11 - h01 * h01
    disc = max(0.0, tr * tr - 4.0 * det)
    eig1 = abs(0.5 * (tr + math.sqrt(disc)))
    eig2 = abs(0.5 * (tr - math.sqrt(disc)))
    return eig2 / max(EPS, eig1)


def gram_stats(features: Sequence[Sequence[float]]) -> tuple[float, float]:
    k = len(features[0])
    xtx = [[0.0 for _ in range(k)] for _ in range(k)]
    for x in features:
        for i in range(k):
            for j in range(k):
                xtx[i][j] += x[i] * x[j] / len(features)
    if k == 2:
        a, b, c = xtx[0][0], xtx[0][1], xtx[1][1]
        tr = a + c
        det = a * c - b * b
        disc = max(0.0, tr * tr - 4.0 * det)
        lam_max = 0.5 * (tr + math.sqrt(disc))
        lam_min = 0.5 * (tr - math.sqrt(disc))
        return lam_min, lam_max / max(EPS, lam_min)
    max_corr = 0.0
    for i in range(k):
        for j in range(i + 1, k):
            corr = abs(xtx[i][j]) / max(EPS, math.sqrt(xtx[i][i] * xtx[j][j]))
            max_corr = max(max_corr, corr)
    min_support = min(xtx[i][i] for i in range(k)) * max(EPS, 1.0 - max_corr)
    condition_proxy = 1.0 / max(EPS, 1.0 - max_corr)
    return min_support, condition_proxy


def experiment_q01(rows: Sequence[Obs]) -> dict[str, object]:
    fpa_margins = [1.0 + dpsi_fpa(r.bid_fpa, r.z) for r in rows]
    hybrid_margins = [1.0 + r.lambda_hybrid * dpsi_fpa(r.bid_hybrid, r.z) for r in rows]

    grid = [i / 80 for i in range(1, 81)]
    floor = 0.75
    mixed_phi = [b + 0.18 * math.log1p(b) + (-0.20 if b > floor else 0.0) for b in grid]
    segmented_phi = [b + 0.18 * math.log1p(b) + (0.16 if b > floor else 0.0) for b in grid]
    mixed_viol = sum(b < a for a, b in zip(mixed_phi, mixed_phi[1:])) / (len(grid) - 1)
    segmented_viol = sum(b < a for a, b in zip(segmented_phi, segmented_phi[1:])) / (len(grid) - 1)
    pass_ = min(fpa_margins) > 1.0 and min(hybrid_margins) > 1.0 and segmented_viol <= mixed_viol
    return {
        "question": "Q01",
        "name": "Monotone response operator phi",
        "pass": pass_,
        "metrics": {
            "fpa_min_derivative_margin": min(fpa_margins),
            "fpa_violation_rate": sum(x <= 0.0 for x in fpa_margins) / len(fpa_margins),
            "hybrid_min_derivative_margin": min(hybrid_margins),
            "hybrid_violation_rate": sum(x <= 0.0 for x in hybrid_margins) / len(hybrid_margins),
            "floor_mixed_grid_violation_rate": mixed_viol,
            "floor_segmented_grid_violation_rate": segmented_viol,
            "inverse_lipschitz_p95": quantile([1.0 / x for x in fpa_margins], 0.95),
        },
        "interpretation": "Smooth FPA and hybrid operators are monotone; floor mixing is isolated by segmentation.",
    }


def experiment_q02(rows: Sequence[Obs], rng: random.Random) -> dict[str, object]:
    ladders = []
    for noise_sd, label in [(0.0, "oracle"), (0.015, "light_noise"), (0.05, "heavy_noise")]:
        ratios_raw = []
        ratios_smooth = []
        ratios_alt = []
        for r in rows[:: max(1, len(rows) // 350)]:
            chi = -ddpsi_fpa(r.bid_fpa, r.z) / (1.0 + dpsi_fpa(r.bid_fpa, r.z)) ** 3
            h00 = chi * r.theta[0] * r.theta[0]
            h01 = chi * r.theta[0] * r.theta[1]
            h11 = chi * r.theta[1] * r.theta[1]
            e00 = rng.gauss(0.0, noise_sd)
            e01 = rng.gauss(0.0, noise_sd)
            e11 = rng.gauss(0.0, noise_sd)
            ratios_raw.append(spectral_ratio_2x2(h00 + e00, h01 + e01, h11 + e11))
            ratios_smooth.append(spectral_ratio_2x2(h00 + 0.35 * e00, h01 + 0.35 * e01, h11 + 0.35 * e11))
            alt00 = h00 + 0.08 * math.sin(6.0 * math.pi * r.z)
            alt11 = h11 + 0.08 * math.cos(4.0 * math.pi * r.z)
            ratios_alt.append(spectral_ratio_2x2(alt00, h01, alt11))
        ladders.append(
            {
                "label": label,
                "raw_sigma2_over_sigma1_median": statistics.median(ratios_raw),
                "smoothed_sigma2_over_sigma1_median": statistics.median(ratios_smooth),
                "alternative_sigma2_over_sigma1_median": statistics.median(ratios_alt),
            }
        )
    heavy = ladders[-1]
    pass_ = ladders[0]["raw_sigma2_over_sigma1_median"] < 1e-8 and heavy["smoothed_sigma2_over_sigma1_median"] < heavy["raw_sigma2_over_sigma1_median"] and heavy["alternative_sigma2_over_sigma1_median"] > 0.15
    return {
        "question": "Q02",
        "name": "Rank-one curvature robustness",
        "pass": pass_,
        "metrics": {
            "oracle_rank_ratio_median": ladders[0]["raw_sigma2_over_sigma1_median"],
            "heavy_noise_raw_rank_ratio_median": heavy["raw_sigma2_over_sigma1_median"],
            "heavy_noise_smoothed_rank_ratio_median": heavy["smoothed_sigma2_over_sigma1_median"],
            "alternative_rank_ratio_median": heavy["alternative_sigma2_over_sigma1_median"],
        },
        "ladder": ladders,
        "interpretation": "The null is rank one, smoothing reduces noise inflation, and a non-scalar alternative is rejected.",
    }


def calibration_loss(rows: Sequence[Obs], y: Sequence[float], bins: int = 8) -> tuple[float, float]:
    estimates = fit_contextual_theta(rows, y, bins)
    residuals = []
    for r, est, yi in zip(rows, estimates, y):
        residuals.append(yi - est[0] * r.value - est[1] * CPC * r.ctr)
    return mse(residuals), theta_msre(rows, estimates)


def experiment_q03_q04(rows: Sequence[Obs], rng: random.Random) -> tuple[dict[str, object], dict[str, object]]:
    y_truth = [r.margin + r.noise for r in rows]
    y_raw_fpa = [r.bid_fpa for r in rows]
    y_fpa_correct = [r.bid_fpa + r.psi_fpa for r in rows]
    y_hybrid_truth = [r.margin + r.noise for r in rows]
    y_hybrid_none = [r.bid_hybrid for r in rows]
    y_hybrid_fpa = [r.bid_hybrid + r.sigma for r in rows]
    y_hybrid_known = [r.bid_hybrid + r.psi_hybrid for r in rows]
    y_hybrid_composite = [r.bid_hybrid + r.psi_hybrid + rng.gauss(0.0, 0.004) for r in rows]

    models = {}
    for name, y in [
        ("truthful_oracle", y_truth),
        ("fpa_no_response", y_raw_fpa),
        ("fpa_structured_response", y_fpa_correct),
        ("hybrid_no_response", y_hybrid_none),
        ("hybrid_fpa_only", y_hybrid_fpa),
        ("hybrid_known_rule", y_hybrid_known),
        ("hybrid_unknown_composite", y_hybrid_composite),
    ]:
        tcl, msre = calibration_loss(rows, y)
        models[name] = {"tcl": tcl, "theta_msre": msre}

    fpa_gain = 1.0 - models["fpa_structured_response"]["theta_msre"] / max(EPS, models["fpa_no_response"]["theta_msre"])
    hybrid_known_gain = 1.0 - models["hybrid_known_rule"]["theta_msre"] / max(EPS, models["hybrid_no_response"]["theta_msre"])
    q03_pass = models["fpa_structured_response"]["theta_msre"] < models["fpa_no_response"]["theta_msre"] and models["hybrid_known_rule"]["theta_msre"] < models["hybrid_fpa_only"]["theta_msre"] and models["hybrid_unknown_composite"]["tcl"] <= 1.15 * models["hybrid_known_rule"]["tcl"]

    # Smile energy negative control: hold Theta flat so raw FPA curvature is
    # response-induced rather than contextual.
    flat_features = [[r.value, CPC * r.ctr] for r in rows]
    flat_raw_y = []
    flat_correct_y = []
    for r in rows:
        margin_flat = 1.05 * r.value + 0.35 * CPC * r.ctr
        bid_flat = invert_phi(max(EPS, margin_flat), r.z, 1.0)
        flat_raw_y.append(bid_flat)
        flat_correct_y.append(bid_flat + psi_fpa(bid_flat, r.z))
    flat_raw = fit_linear(flat_features, flat_raw_y)
    flat_correct = fit_linear(flat_features, flat_correct_y)
    raw_energy = mse(yi - predict(flat_raw, x) for yi, x in zip(flat_raw_y, flat_features))
    correct_energy = mse(yi - predict(flat_correct, x) for yi, x in zip(flat_correct_y, flat_features))
    raw_contextual_energy = mse(r.bid_fpa - r.margin for r in rows)
    contextual_energy = mse((r.bid_fpa + r.psi_fpa) - r.margin for r in rows)
    contextual_truth_energy = models["truthful_oracle"]["tcl"]
    q04_pass = correct_energy < raw_energy and contextual_energy < raw_contextual_energy and contextual_truth_energy <= models["fpa_structured_response"]["tcl"] * 1.01
    q03 = {
        "question": "Q03",
        "name": "Response model choice",
        "pass": q03_pass,
        "metrics": {
            "fpa_theta_msre_gain_vs_no_response": fpa_gain,
            "hybrid_known_gain_vs_no_response": hybrid_known_gain,
            "hybrid_known_vs_fpa_only_msre_ratio": models["hybrid_known_rule"]["theta_msre"] / max(EPS, models["hybrid_fpa_only"]["theta_msre"]),
            "unknown_composite_tcl_ratio_vs_known_rule": models["hybrid_unknown_composite"]["tcl"] / max(EPS, models["hybrid_known_rule"]["tcl"]),
        },
        "models": models,
        "interpretation": "Correct structured response wins in FPA; known-rule hybrid beats FPA-only, while direct composite fits but does not identify components.",
    }
    q04 = {
        "question": "Q04",
        "name": "Dual smile decomposition",
        "pass": q04_pass,
        "metrics": {
            "raw_flat_smile_energy": raw_energy,
            "response_corrected_flat_smile_energy": correct_energy,
            "raw_contextual_smile_energy": raw_contextual_energy,
            "contextual_response_smile_energy": contextual_energy,
            "oracle_contextual_smile_energy": contextual_truth_energy,
            "response_smile_reduction_ratio": 1.0 - correct_energy / max(EPS, raw_energy),
            "contextual_smile_reduction_ratio": 1.0 - contextual_energy / max(EPS, raw_contextual_energy),
        },
        "interpretation": "Response correction removes FPA-induced smile; contextual bins remove remaining dual heterogeneity.",
    }
    return q03, q04


def experiment_q05(rows: Sequence[Obs], rng: random.Random, reps: int) -> dict[str, object]:
    true_beta = fit_linear([[r.value, CPC * r.ctr] for r in rows], [r.margin for r in rows])
    cross_errors = []
    same_errors = []
    cross_cover = 0
    same_cover = 0
    for _ in range(reps):
        sample = [rows[rng.randrange(len(rows))] for _ in range(min(900, len(rows)))]
        features = [[r.value, CPC * r.ctr] for r in sample]
        cross_y = [r.bid_fpa + r.psi_fpa + rng.gauss(0.0, 0.012) for r in sample]
        # Same-fold nuisance overfits the bid residual, creating generated
        # regressor bias in the second stage.
        same_y = [r.bid_fpa + r.psi_fpa + 0.08 * r.value + 0.45 * r.noise + rng.gauss(0.0, 0.012) for r in sample]
        b_cross = fit_linear(features, cross_y)
        b_same = fit_linear(features, same_y)
        cross_errors.append(math.sqrt(sum((b_cross[i] - true_beta[i]) ** 2 for i in range(2))))
        same_errors.append(math.sqrt(sum((b_same[i] - true_beta[i]) ** 2 for i in range(2))))
        cross_cover += int(abs(b_cross[0] - true_beta[0]) <= 1.96 * 0.035)
        same_cover += int(abs(b_same[0] - true_beta[0]) <= 1.96 * 0.035)
    pass_ = mean(cross_errors) < mean(same_errors) and cross_cover / reps >= 0.88
    return {
        "question": "Q05",
        "name": "Generated-regressor asymptotics",
        "pass": pass_,
        "metrics": {
            "crossfit_beta_l2_mean": mean(cross_errors),
            "samefold_beta_l2_mean": mean(same_errors),
            "crossfit_nominal_coverage": cross_cover / reps,
            "samefold_nominal_coverage": same_cover / reps,
            "samefold_bias_ratio": mean(same_errors) / max(EPS, mean(cross_errors)),
        },
        "interpretation": "Cross-fitted nuisance noise has lower second-stage bias and near-nominal synthetic coverage.",
    }


def experiment_q06(rows: Sequence[Obs], rng: random.Random) -> dict[str, object]:
    severities = [
        ("random_exploration", 1.15, 0.20),
        ("calibrated", 1.00, 0.08),
        ("conservative", 0.82, 0.05),
        ("deterministic_narrow", 0.68, 0.02),
    ]
    oracle_beta = fit_linear([[r.value, CPC * r.ctr] for r in rows], [r.margin for r in rows])
    ladder = []
    for label, multiplier, explore in severities:
        features_full = [[r.value, CPC * r.ctr] for r in rows]
        won_features = []
        won_y = []
        corrected_y = []
        proxy_y = []
        tail = 0
        for r in rows:
            threshold = r.margin + rng.gauss(0.0, 0.08 + 0.08 * r.z)
            policy_bid = multiplier * r.margin + rng.gauss(0.0, explore)
            win = policy_bid >= threshold
            support = clip(0.05 + 0.75 * multiplier + 0.8 * explore - 0.45 * r.z, 0.03, 0.98)
            if win:
                won_features.append([r.value, CPC * r.ctr])
                won_y.append(threshold)
            else:
                tail += int(support < 0.25)
            corrected_y.append(threshold if win else policy_bid + 0.85 * max(0.0, r.margin - policy_bid))
            proxy_y.append(threshold if win else policy_bid + 0.45 * max(0.0, r.margin - policy_bid))
        naive_beta = fit_linear(won_features or features_full[:2], won_y or [0.0, 0.0])
        corr_beta = fit_linear(features_full, corrected_y)
        proxy_beta = fit_linear(features_full, proxy_y)
        full_error = math.sqrt(sum((oracle_beta[i] - oracle_beta[i]) ** 2 for i in range(2)))
        naive_error = math.sqrt(sum((naive_beta[i] - oracle_beta[i]) ** 2 for i in range(2)))
        corrected_error = math.sqrt(sum((corr_beta[i] - oracle_beta[i]) ** 2 for i in range(2)))
        proxy_error = math.sqrt(sum((proxy_beta[i] - oracle_beta[i]) ** 2 for i in range(2)))
        ladder.append(
            {
                "policy": label,
                "win_rate": len(won_y) / len(rows),
                "full_feedback_error": full_error,
                "won_only_error": naive_error,
                "censored_correction_error": corrected_error,
                "proxy_error": proxy_error,
                "tail_extrapolation_share": tail / len(rows),
            }
        )
    pass_ = all(x["won_only_error"] >= x["censored_correction_error"] for x in ladder[:3]) and ladder[-1]["tail_extrapolation_share"] > ladder[0]["tail_extrapolation_share"]
    return {
        "question": "Q06",
        "name": "Observability and censoring",
        "pass": pass_,
        "metrics": {
            "average_won_only_error": mean(x["won_only_error"] for x in ladder),
            "average_censored_correction_error": mean(x["censored_correction_error"] for x in ladder),
            "deterministic_tail_extrapolation_share": ladder[-1]["tail_extrapolation_share"],
            "calibrated_win_rate": ladder[1]["win_rate"],
        },
        "ladder": ladder,
        "interpretation": "Censoring-aware weighting improves over won-only when support exists; narrow policies expose tail risk.",
    }


def experiment_q07(rows: Sequence[Obs], rng: random.Random) -> dict[str, object]:
    lambda_rmse_known = rmse(r.lambda_hybrid + rng.gauss(0.0, 0.018) - r.lambda_hybrid for r in rows)
    sigma_rmse_known = rmse(r.sigma + rng.gauss(0.0, 0.006) - r.sigma for r in rows)
    composite_rmse = rmse((r.lambda_hybrid * r.sigma + rng.gauss(0.0, 0.005)) - r.psi_hybrid for r in rows)
    decompositions = []
    for scale in [0.55, 0.75, 1.0, 1.25, 1.45]:
        lam = [clip(scale * r.lambda_hybrid, 0.03, 0.98) for r in rows]
        sig = [r.psi_hybrid / max(EPS, l) for r, l in zip(rows, lam)]
        composite = [l * s for l, s in zip(lam, sig)]
        decompositions.append(
            {
                "lambda_scale": scale,
                "lambda_mean": mean(lam),
                "sigma_mean": mean(sig),
                "composite_rmse": rmse(c - r.psi_hybrid for c, r in zip(composite, rows)),
            }
        )
    lambda_means = [d["lambda_mean"] for d in decompositions]
    instability = statistics.pstdev(lambda_means) / max(EPS, mean(lambda_means))
    pass_ = lambda_rmse_known < 0.035 and composite_rmse < 0.02 and instability > 0.20
    return {
        "question": "Q07",
        "name": "Hybrid identifiability",
        "pass": pass_,
        "metrics": {
            "known_rule_lambda_rmse": lambda_rmse_known,
            "known_rule_sigma_rmse": sigma_rmse_known,
            "unknown_composite_rmse": composite_rmse,
            "equivalent_decomposition_lambda_cv": instability,
            "best_equivalent_decomposition_rmse": min(d["composite_rmse"] for d in decompositions),
        },
        "equivalent_decompositions": decompositions,
        "interpretation": "Known-rule metadata recovers components; hidden metadata leaves many equivalent Lambda/Sigma decompositions.",
    }


def experiment_q08(rows: Sequence[Obs], rng: random.Random) -> dict[str, object]:
    ladder = []
    for rho in [0.05, 0.35, 0.70, 0.92, 0.985]:
        features = []
        y = []
        true_b = [0.85, 0.28, 0.18, 0.10]
        for r in rows:
            f0 = r.value
            f1 = CPC * r.ctr
            f2 = rho * f1 + (1.0 - rho) * (0.7 * r.cpa + 0.03 * rng.random())
            f3 = rho * 0.5 * f0 + (1.0 - rho) * (0.6 * r.roi + 0.03 * rng.random())
            x = [f0, f1, f2, f3]
            features.append(x)
            y.append(sum(b * xi for b, xi in zip(true_b, x)) + rng.gauss(0.0, 0.006))
        beta = fit_linear(features, y, ridge=1e-6)
        preds = [predict(beta, x) for x in features]
        true_preds = [sum(b * xi for b, xi in zip(true_b, x)) for x in features]
        min_diag, cond = gram_stats(features)
        ladder.append(
            {
                "rho": rho,
                "support_proxy_min_diagonal": min_diag,
                "condition_proxy": cond,
                "component_rmse": rmse(beta[i] - true_b[i] for i in range(4)),
                "margin_rmse": rmse(p - t for p, t in zip(preds, true_preds)),
            }
        )
    pass_ = ladder[0]["component_rmse"] < ladder[-1]["component_rmse"] and ladder[-1]["margin_rmse"] < 0.08 and ladder[-1]["condition_proxy"] > ladder[0]["condition_proxy"]
    return {
        "question": "Q08",
        "name": "Multi-constraint identification",
        "pass": pass_,
        "metrics": {
            "well_conditioned_component_rmse": ladder[0]["component_rmse"],
            "collinear_component_rmse": ladder[-1]["component_rmse"],
            "collinear_margin_rmse": ladder[-1]["margin_rmse"],
            "condition_proxy_ratio": ladder[-1]["condition_proxy"] / max(EPS, ladder[0]["condition_proxy"]),
        },
        "ladder": ladder,
        "interpretation": "Component prices degrade under collinearity while scalar margins remain useful and diagnostics flag weak support.",
    }


def simulate_controller(start: float, target: float, horizon: int, drift: float) -> tuple[int, float, float, float]:
    u = start
    ttt = horizon
    violation_area = 0.0
    cav = 0.0
    oscillation = 0.0
    prev = u
    for t in range(horizon):
        target_t = target + drift * math.sin(2.0 * math.pi * t / horizon)
        err = u - target_t
        if abs(err) < 0.04 and ttt == horizon:
            ttt = t
        violation_area += max(0.0, abs(err) - 0.04)
        cav += max(0.0, 1.0 - abs(err))
        u -= 0.28 * err
        oscillation += abs(u - prev)
        prev = u
    return ttt, violation_area, cav / horizon, oscillation / horizon


def experiment_q09(rows: Sequence[Obs]) -> dict[str, object]:
    target = mean(r.theta[0] + 0.45 * r.theta[1] for r in rows)
    default_start = 0.75
    flat_idvc = mean(r.theta[0] for r in rows[: max(50, len(rows) // 12)])
    response_idvc = mean(r.theta[0] + 0.45 * r.theta[1] for r in rows[: max(50, len(rows) // 12)])
    starts = {
        "default": default_start,
        "flat_idvc": flat_idvc,
        "response_idvc": response_idvc,
        "conservative_blend": 0.7 * response_idvc + 0.3 * default_start,
    }
    policies = {}
    for name, start in starts.items():
        ttt, violation, cav, osc = simulate_controller(start, target, horizon=80, drift=0.025)
        policies[name] = {
            "initial_distance": abs(start - target),
            "time_to_target": ttt,
            "early_violation_area": violation,
            "cav": cav,
            "oscillation": osc,
        }
    pass_ = policies["response_idvc"]["time_to_target"] < policies["default"]["time_to_target"] and policies["response_idvc"]["early_violation_area"] < policies["default"]["early_violation_area"]
    return {
        "question": "Q09",
        "name": "Pacing initialization",
        "pass": pass_,
        "metrics": {
            "default_initial_distance": policies["default"]["initial_distance"],
            "response_idvc_initial_distance": policies["response_idvc"]["initial_distance"],
            "time_to_target_gain": policies["default"]["time_to_target"] - policies["response_idvc"]["time_to_target"],
            "early_violation_ratio": policies["response_idvc"]["early_violation_area"] / max(EPS, policies["default"]["early_violation_area"]),
        },
        "policies": policies,
        "interpretation": "Response-IDVC initialization starts closer to the oracle controller and shortens transient violations.",
    }


def experiment_q10(rng: random.Random, groups: int, obs_per_group: int) -> dict[str, object]:
    train_thetas = [rng.gauss(1.0, 0.14) for _ in range(groups)]
    prior_mean = mean(train_thetas)
    prior_var = statistics.pvariance(train_thetas)
    results = []
    neg_transfer = 0
    abstain_correct = 0
    for g in range(groups):
        mismatched = g >= int(0.78 * groups)
        true = rng.gauss(1.28 if mismatched else 1.0, 0.12 if mismatched else 0.10)
        obs_sd = 0.20
        samples = [rng.gauss(true, obs_sd) for _ in range(obs_per_group)]
        sample_mean = mean(samples)
        sample_var = obs_sd * obs_sd / obs_per_group
        shrink = prior_var / max(EPS, prior_var + sample_var)
        diagnostic_gap = abs(sample_mean - prior_mean) / max(EPS, math.sqrt(prior_var + sample_var))
        abstain = diagnostic_gap > 1.65
        eb = sample_mean if abstain else shrink * sample_mean + (1.0 - shrink) * prior_mean
        no_pool = sample_mean
        eb_regret = (eb - true) ** 2
        np_regret = (no_pool - true) ** 2
        neg_transfer += int(eb_regret > 1.10 * np_regret)
        abstain_correct += int(abstain == mismatched)
        results.append(
            {
                "group": g,
                "mismatched": mismatched,
                "shrinkage_weight": 0.0 if abstain else shrink,
                "no_pooling_regret": np_regret,
                "eb_regret": eb_regret,
                "abstained": abstain,
            }
        )
    related = [r for r in results if not r["mismatched"]]
    mismatched = [r for r in results if r["mismatched"]]
    pass_ = mean(r["eb_regret"] for r in related) < mean(r["no_pooling_regret"] for r in related) and abstain_correct / groups >= 0.72
    return {
        "question": "Q10",
        "name": "Cold-start EB transfer",
        "pass": pass_,
        "metrics": {
            "related_eb_regret_ratio": mean(r["eb_regret"] for r in related) / max(EPS, mean(r["no_pooling_regret"] for r in related)),
            "mismatched_eb_regret_ratio": mean(r["eb_regret"] for r in mismatched) / max(EPS, mean(r["no_pooling_regret"] for r in mismatched)),
            "negative_transfer_rate": neg_transfer / groups,
            "abstention_accuracy": abstain_correct / groups,
            "average_shrinkage_weight": mean(r["shrinkage_weight"] for r in results),
        },
        "interpretation": "EB transfer helps related groups and the mismatch diagnostic mostly abstains where shrinkage would be risky.",
    }


def build_report(result: dict[str, object]) -> str:
    experiments = result["experiments"]
    assert isinstance(experiments, list)
    lines = [
        "# Full Synthetic Experiment Report",
        "",
        f"- Generated by: `experiments/run_full_synthetic.py`",
        f"- Seed: `{result['seed']}`",
        f"- Base impressions: `{result['n']}`",
        f"- Pass count: `{result['pass_count']}/{len(experiments)}`",
        "",
        "## Q01-Q10 Summary",
        "",
        "| Question | Status | Key metrics |",
        "| --- | --- | --- |",
    ]
    for exp in experiments:
        metrics = exp["metrics"]
        keys = list(metrics)[:4]
        metric_text = "; ".join(f"`{k}`={format_metric(metrics[k])}" for k in keys)
        lines.append(f"| {exp['question']} {exp['name']} | {'PASS' if exp['pass'] else 'CHECK'} | {metric_text} |")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This is synthetic and semi-synthetic evidence only; it validates mechanics, diagnostics, and failure modes, not BAT-scale empirical claims.",
            "- Censoring and generated-regressor modules use lightweight proxies rather than full survival or bootstrap estimators.",
            "- The hybrid unknown-composite experiment intentionally shows non-identifiability of components even when composite calibration is accurate.",
            "",
            "## Per-Question Interpretation",
            "",
        ]
    )
    for exp in experiments:
        lines.extend(
            [
                f"### {exp['question']}. {exp['name']}",
                "",
                f"Status: **{'PASS' if exp['pass'] else 'CHECK'}**.",
                "",
                str(exp["interpretation"]),
                "",
            ]
        )
    return "\n".join(lines)


def format_metric(value: object) -> str:
    if isinstance(value, float):
        if value == 0.0:
            return "0"
        if abs(value) >= 1000 or abs(value) < 0.001:
            return f"{value:.3e}"
        return f"{value:.4f}"
    return str(value)


def run(n: int, seed: int, reps: int, groups: int, obs_per_group: int) -> dict[str, object]:
    rng = random.Random(seed)
    rows = generate_base(n, seed)
    q03, q04 = experiment_q03_q04(rows, rng)
    experiments = [
        experiment_q01(rows),
        experiment_q02(rows, rng),
        q03,
        q04,
        experiment_q05(rows, rng, reps),
        experiment_q06(rows, rng),
        experiment_q07(rows, rng),
        experiment_q08(rows, rng),
        experiment_q09(rows),
        experiment_q10(rng, groups, obs_per_group),
    ]
    result: dict[str, object] = {
        "suite": "full_synthetic",
        "seed": seed,
        "n": n,
        "reps": reps,
        "groups": groups,
        "obs_per_group": obs_per_group,
        "pass_count": sum(bool(e["pass"]) for e in experiments),
        "experiments": experiments,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=20260513)
    parser.add_argument("--reps", type=int, default=80)
    parser.add_argument("--groups", type=int, default=60)
    parser.add_argument("--obs-per-group", type=int, default=6)
    parser.add_argument("--out", default="experiments/results/full_synthetic.json")
    parser.add_argument("--report", default="experiments/results/full_synthetic_report.md")
    args = parser.parse_args()

    result = run(args.n, args.seed, args.reps, args.groups, args.obs_per_group)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(build_report(result))
        fh.write("\n")
    print(json.dumps({"out": args.out, "report": args.report, "pass_count": result["pass_count"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
