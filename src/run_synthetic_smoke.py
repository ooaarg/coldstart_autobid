#!/usr/bin/env python3
"""Dependency-free synthetic validation smoke tests.

The goal is not to replace the full experimental section. It is to make the
paper's claims executable immediately and to catch broken assumptions before
running BAT-scale jobs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
from dataclasses import dataclass
from typing import Iterable, Sequence


EPS = 1e-12


@dataclass
class Row:
    z: float
    v: float
    mu: float
    y_truth: float
    b_fpa: float
    b_hybrid: float
    theta_s: float
    theta_alpha: float
    psi_fpa: float
    psi_hybrid: float


def theta(z: float) -> tuple[float, float]:
    """Smooth contextual dual surface used as synthetic ground truth."""
    s = 1.0 + 0.25 * math.sin(2.0 * math.pi * z)
    alpha = 0.35 + 0.18 * math.cos(2.0 * math.pi * z)
    return s, min(0.95, max(0.03, alpha))


def margin(v: float, mu: float, z: float, cpc: float) -> float:
    s, alpha = theta(z)
    return s * v + alpha * cpc * mu


def psi_fpa(b: float, z: float) -> float:
    """Smooth positive response with a guaranteed monotone phi."""
    scale = 0.18 + 0.05 * math.sin(2.0 * math.pi * z)
    return scale * math.log1p(max(b, 0.0))


def dpsi_fpa(b: float, z: float) -> float:
    scale = 0.18 + 0.05 * math.sin(2.0 * math.pi * z)
    return scale / (1.0 + max(b, 0.0))


def ddpsi_fpa(b: float, z: float) -> float:
    scale = 0.18 + 0.05 * math.sin(2.0 * math.pi * z)
    return -scale / (1.0 + max(b, 0.0)) ** 2


def lambda_hybrid(z: float) -> float:
    return 0.25 + 0.45 * z


def invert_phi(m: float, z: float, lam: float = 1.0) -> float:
    """Solve b + lam * psi_fpa(b,z) = m by bisection."""
    lo = 0.0
    hi = max(1.0, m + 1.0)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        val = mid + lam * psi_fpa(mid, z)
        if val < m:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def generate_rows(n: int, seed: int) -> list[Row]:
    rng = random.Random(seed)
    rows: list[Row] = []
    cpc = 2.0
    for _ in range(n):
        z = rng.random()
        ctr = 0.02 + 0.18 * rng.random()
        cvr = 0.03 + 0.22 * rng.random()
        v = ctr * cvr * 100.0
        mu = ctr
        m = margin(v, mu, z, cpc)
        noise = rng.gauss(0.0, 0.01)
        b = invert_phi(max(EPS, m), z)
        lam = lambda_hybrid(z)
        bh = invert_phi(max(EPS, m), z, lam=lam)
        rows.append(
            Row(
                z=z,
                v=v,
                mu=mu,
                y_truth=m + noise,
                b_fpa=b + noise,
                b_hybrid=bh + noise,
                theta_s=theta(z)[0],
                theta_alpha=theta(z)[1],
                psi_fpa=psi_fpa(max(0.0, b), z),
                psi_hybrid=lam * psi_fpa(max(0.0, bh), z),
            )
        )
    return rows


def solve_2x2(a00: float, a01: float, a11: float, b0: float, b1: float) -> tuple[float, float]:
    det = a00 * a11 - a01 * a01
    if abs(det) < EPS:
        return float("nan"), float("nan")
    return (b0 * a11 - b1 * a01) / det, (a00 * b1 - a01 * b0) / det


def fit_linear(rows: Sequence[Row], response: Sequence[float], cpc: float) -> tuple[float, float]:
    a00 = sum(r.v * r.v for r in rows)
    a01 = sum(r.v * cpc * r.mu for r in rows)
    a11 = sum((cpc * r.mu) ** 2 for r in rows)
    b0 = sum(r.v * y for r, y in zip(rows, response))
    b1 = sum(cpc * r.mu * y for r, y in zip(rows, response))
    return solve_2x2(a00, a01, a11, b0, b1)


def mse(values: Iterable[float]) -> float:
    vals = list(values)
    return sum(v * v for v in vals) / max(1, len(vals))


def quantile(values: Sequence[float], p: float) -> float:
    vals = sorted(values)
    if not vals:
        return float("nan")
    idx = min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))
    return vals[idx]


def local_bins(rows: Sequence[Row], bins: int = 5) -> list[list[Row]]:
    out = [[] for _ in range(bins)]
    for r in rows:
        idx = min(bins - 1, int(r.z * bins))
        out[idx].append(r)
    return out


def contextual_theta_recovery(rows: Sequence[Row], response_attr: str, cpc: float) -> dict[str, float]:
    errs = []
    for bucket in local_bins(rows):
        if len(bucket) < 20:
            continue
        resp = [getattr(r, response_attr) for r in bucket]
        s_hat, a_hat = fit_linear(bucket, resp, cpc)
        if math.isnan(s_hat):
            continue
        for r in bucket:
            errs.append((s_hat - r.theta_s) ** 2 + (a_hat - r.theta_alpha) ** 2)
    return {"msre_theta": mse(errs), "bins_used": len(errs)}


def transformed_fpa_recovery(rows: Sequence[Row], cpc: float) -> dict[str, float]:
    raw_s, raw_a = fit_linear(rows, [r.b_fpa for r in rows], cpc)
    corr_s, corr_a = fit_linear(rows, [r.b_fpa + r.psi_fpa for r in rows], cpc)
    truth_resp = [r.y_truth for r in rows]
    truth_s, truth_a = fit_linear(rows, truth_resp, cpc)
    raw_tcl = mse(r.b_fpa - (raw_s * r.v + raw_a * cpc * r.mu) for r in rows)
    corr_tcl = mse((r.b_fpa + r.psi_fpa) - (corr_s * r.v + corr_a * cpc * r.mu) for r in rows)
    oracle_tcl = mse(r.y_truth - (truth_s * r.v + truth_a * cpc * r.mu) for r in rows)
    raw_margin_error = mse(r.b_fpa - r.y_truth for r in rows)
    corrected_margin_error = mse((r.b_fpa + r.psi_fpa) - r.y_truth for r in rows)
    return {
        "raw_bid_scale_tcl": raw_tcl,
        "response_corrected_tcl": corr_tcl,
        "truthful_oracle_tcl": oracle_tcl,
        "raw_margin_error_against_truth": raw_margin_error,
        "corrected_margin_error_against_truth": corrected_margin_error,
        "raw_theta_l2": math.sqrt((raw_s - truth_s) ** 2 + (raw_a - truth_a) ** 2),
        "corrected_theta_l2": math.sqrt((corr_s - truth_s) ** 2 + (corr_a - truth_a) ** 2),
    }


def monotonicity(rows: Sequence[Row]) -> dict[str, float]:
    margins = [1.0 + dpsi_fpa(max(0.0, r.b_fpa), r.z) for r in rows]
    hybrid = [1.0 + lambda_hybrid(r.z) * dpsi_fpa(max(0.0, r.b_hybrid), r.z) for r in rows]
    return {
        "fpa_min_1_plus_dpsi": min(margins),
        "fpa_violation_rate": sum(m <= 0.0 for m in margins) / len(margins),
        "hybrid_min_1_plus_dpsi": min(hybrid),
        "hybrid_violation_rate": sum(m <= 0.0 for m in hybrid) / len(hybrid),
    }


def rank_one_curvature(rows: Sequence[Row], cpc: float) -> dict[str, float]:
    ratios = []
    chis = []
    for r in rows[:: max(1, len(rows) // 250)]:
        th = [r.theta_s, r.theta_alpha]
        denom = (1.0 + dpsi_fpa(max(0.0, r.b_fpa), r.z)) ** 3
        chi = -ddpsi_fpa(max(0.0, r.b_fpa), r.z) / denom
        # Hessian = chi * theta theta^T. Its nonzero eigenvalue is chi*||theta||^2.
        h00 = chi * th[0] * th[0]
        h01 = chi * th[0] * th[1]
        h11 = chi * th[1] * th[1]
        tr = h00 + h11
        det = h00 * h11 - h01 * h01
        disc = max(0.0, tr * tr - 4.0 * det)
        eig1 = abs(0.5 * (tr + math.sqrt(disc)))
        eig2 = abs(0.5 * (tr - math.sqrt(disc)))
        ratios.append(eig1 / max(EPS, eig1 + eig2))
        chis.append(chi)
    return {
        "rank_one_ratio_median": statistics.median(ratios),
        "rank_one_ratio_p05": quantile(ratios, 0.05),
        "chi_median": statistics.median(chis),
    }


def weak_identification(rows: Sequence[Row], cpc: float) -> dict[str, float]:
    x0 = [r.v for r in rows]
    x1 = [cpc * r.mu for r in rows]
    a00 = sum(v * v for v in x0) / len(rows)
    a01 = sum(v * m for v, m in zip(x0, x1)) / len(rows)
    a11 = sum(m * m for m in x1) / len(rows)
    tr = a00 + a11
    det = a00 * a11 - a01 * a01
    disc = max(0.0, tr * tr - 4.0 * det)
    eig_max = 0.5 * (tr + math.sqrt(disc))
    eig_min = 0.5 * (tr - math.sqrt(disc))
    return {
        "gram_lambda_min": eig_min,
        "gram_condition_number": eig_max / max(EPS, eig_min),
    }


def deployment_smoke(rows: Sequence[Row]) -> dict[str, float]:
    # Proxy deployment calculations: calibrated init starts closer to the known
    # synthetic target; EB shrinkage reduces posterior variance.
    target = statistics.mean(r.theta_s for r in rows)
    default = 0.75
    calibrated = statistics.mean(r.theta_s for r in rows[: max(30, len(rows) // 10)])
    default_regret = (default - target) ** 2
    calibrated_regret = (calibrated - target) ** 2
    category_precision = 20.0
    prior_precision = 8.0
    posterior_var = 1.0 / (category_precision + prior_precision)
    category_var = 1.0 / category_precision
    return {
        "default_init_squared_error": default_regret,
        "calibrated_init_squared_error": calibrated_regret,
        "init_error_ratio": calibrated_regret / max(EPS, default_regret),
        "cold_start_posterior_variance_ratio": posterior_var / category_var,
    }


def run(n: int, seed: int) -> dict[str, object]:
    cpc = 2.0
    rows = generate_rows(n, seed)
    result = {
        "n": n,
        "seed": seed,
        "truthful_contextual": contextual_theta_recovery(rows, "y_truth", cpc),
        "fpa_response": transformed_fpa_recovery(rows, cpc),
        "monotonicity": monotonicity(rows),
        "rank_one_curvature": rank_one_curvature(rows, cpc),
        "weak_identification": weak_identification(rows, cpc),
        "deployment": deployment_smoke(rows),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=20260513)
    parser.add_argument("--out", default="experiments/results/synthetic_smoke.json")
    args = parser.parse_args()

    result = run(args.n, args.seed)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
