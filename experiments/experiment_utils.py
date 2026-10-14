"""Small standard-library utilities for BAT-scale streaming experiments."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import statistics
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import DefaultDict, Iterable, Iterator, Mapping, Sequence


EPS = 1e-12
ADMISSIBLE_S_MIN = 1e-8
ADMISSIBLE_ALPHA_MIN = 0.0
ADMISSIBLE_ALPHA_MAX = 1.0
USER_AGENT = "codex-bat-runner/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def write_json(path: str, payload: Mapping[str, object]) -> None:
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def open_text_stream(source: str, timeout: int = 120) -> io.TextIOBase:
    """Open a local or HTTP(S) CSV source as text without materializing it."""
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": USER_AGENT})
        raw = urllib.request.urlopen(req, timeout=timeout)
        if source.endswith(".gz"):
            return io.TextIOWrapper(gzip.GzipFile(fileobj=raw), encoding="utf-8", newline="")
        return io.TextIOWrapper(raw, encoding="utf-8", newline="")
    if source.endswith(".gz"):
        return gzip.open(source, mode="rt", encoding="utf-8", newline="")
    return open(source, mode="r", encoding="utf-8", newline="")


def iter_csv_rows(source: str, timeout: int = 120) -> Iterator[dict[str, str]]:
    with open_text_stream(source, timeout=timeout) as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            yield row


def sniff_columns(source: str, timeout: int = 120) -> list[str]:
    with open_text_stream(source, timeout=timeout) as fh:
        reader = csv.reader(fh)
        return next(reader, [])


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if not math.isfinite(out):
        return None
    return out


def parse_key(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def quantile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, int(round(p * (len(vals) - 1)))))
    return vals[idx]


@dataclass
class NumericSummary:
    count: int = 0
    missing: int = 0
    total: float = 0.0
    min_value: float | None = None
    max_value: float | None = None
    samples: list[float] = field(default_factory=list)
    sample_limit: int = 5000

    def add(self, value: float | None) -> None:
        if value is None:
            self.missing += 1
            return
        self.count += 1
        self.total += value
        self.min_value = value if self.min_value is None else min(self.min_value, value)
        self.max_value = value if self.max_value is None else max(self.max_value, value)
        if len(self.samples) < self.sample_limit:
            self.samples.append(value)

    def to_json(self) -> dict[str, float | int | None]:
        return {
            "count": self.count,
            "missing": self.missing,
            "mean": self.total / self.count if self.count else None,
            "min": self.min_value,
            "p05": quantile(self.samples, 0.05),
            "median": quantile(self.samples, 0.50),
            "p95": quantile(self.samples, 0.95),
            "max": self.max_value,
        }


@dataclass
class OLS2Accumulator:
    n: int = 0
    sx0x0: float = 0.0
    sx0x1: float = 0.0
    sx1x1: float = 0.0
    sx0y: float = 0.0
    sx1y: float = 0.0
    syy: float = 0.0
    sy: float = 0.0
    y_min: float | None = None
    y_max: float | None = None

    def add(self, x0: float, x1: float, y: float) -> None:
        self.n += 1
        self.sx0x0 += x0 * x0
        self.sx0x1 += x0 * x1
        self.sx1x1 += x1 * x1
        self.sx0y += x0 * y
        self.sx1y += x1 * y
        self.syy += y * y
        self.sy += y
        self.y_min = y if self.y_min is None else min(self.y_min, y)
        self.y_max = y if self.y_max is None else max(self.y_max, y)

    def merge(self, other: "OLS2Accumulator") -> None:
        self.n += other.n
        self.sx0x0 += other.sx0x0
        self.sx0x1 += other.sx0x1
        self.sx1x1 += other.sx1x1
        self.sx0y += other.sx0y
        self.sx1y += other.sx1y
        self.syy += other.syy
        self.sy += other.sy
        if other.y_min is not None:
            self.y_min = other.y_min if self.y_min is None else min(self.y_min, other.y_min)
        if other.y_max is not None:
            self.y_max = other.y_max if self.y_max is None else max(self.y_max, other.y_max)

    def coefficients(self) -> tuple[float | None, float | None]:
        det = self.sx0x0 * self.sx1x1 - self.sx0x1 * self.sx0x1
        if self.n < 2 or abs(det) <= EPS:
            return None, None
        beta0 = (self.sx0y * self.sx1x1 - self.sx1y * self.sx0x1) / det
        beta1 = (self.sx0x0 * self.sx1y - self.sx0x1 * self.sx0y) / det
        return beta0, beta1

    def _sse(self, beta0: float, beta1: float) -> float:
        sse = (
            self.syy
            - 2.0 * beta0 * self.sx0y
            - 2.0 * beta1 * self.sx1y
            + beta0 * beta0 * self.sx0x0
            + 2.0 * beta0 * beta1 * self.sx0x1
            + beta1 * beta1 * self.sx1x1
        )
        return max(0.0, sse)

    def admissible_coefficients(
        self,
        s_min: float = ADMISSIBLE_S_MIN,
        alpha_min: float = ADMISSIBLE_ALPHA_MIN,
        alpha_max: float = ADMISSIBLE_ALPHA_MAX,
    ) -> tuple[float | None, float | None]:
        """Exact least-squares fit over s >= s_min and alpha in [0, 1].

        The feasible set is a half-strip. For a convex quadratic in two
        variables, the optimum is either the unconstrained solution when
        feasible, one of the three active boundaries, or a corner.
        """
        if self.n == 0:
            return None, None
        candidates: list[tuple[float, float]] = []
        beta0, beta1 = self.coefficients()
        if (
            beta0 is not None
            and beta1 is not None
            and beta0 >= s_min
            and alpha_min <= beta1 <= alpha_max
        ):
            candidates.append((beta0, beta1))
        for alpha in (alpha_min, alpha_max):
            if self.sx0x0 > EPS:
                s = (self.sx0y - alpha * self.sx0x1) / self.sx0x0
                candidates.append((max(s_min, s), alpha))
            else:
                candidates.append((s_min, alpha))
        if self.sx1x1 > EPS:
            alpha = (self.sx1y - s_min * self.sx0x1) / self.sx1x1
            alpha = min(alpha_max, max(alpha_min, alpha))
            candidates.append((s_min, alpha))
        candidates.append((s_min, alpha_min))
        candidates.append((s_min, alpha_max))
        best = min(candidates, key=lambda pair: self._sse(pair[0], pair[1]))
        return best

    def admissibility_diagnostics(
        self,
        s_min: float = ADMISSIBLE_S_MIN,
        alpha_min: float = ADMISSIBLE_ALPHA_MIN,
        alpha_max: float = ADMISSIBLE_ALPHA_MAX,
    ) -> dict[str, object]:
        beta0, beta1 = self.coefficients()
        s_hat, alpha_hat = self.admissible_coefficients(s_min, alpha_min, alpha_max)
        unconstrained = self.score(beta0, beta1)
        constrained = self.score(s_hat, alpha_hat)
        return {
            "unconstrained_beta_v": beta0,
            "unconstrained_beta_cpc_mu": beta1,
            "unconstrained_s_below_min": bool(beta0 is not None and beta0 < s_min),
            "unconstrained_alpha_below_zero": bool(beta1 is not None and beta1 < alpha_min),
            "unconstrained_alpha_above_one": bool(beta1 is not None and beta1 > alpha_max),
            "admissible_beta_v": s_hat,
            "admissible_beta_cpc_mu": alpha_hat,
            "admissible_active_s_min": bool(s_hat is not None and abs(s_hat - s_min) <= 1e-10),
            "admissible_active_alpha_min": bool(alpha_hat is not None and abs(alpha_hat - alpha_min) <= 1e-10),
            "admissible_active_alpha_max": bool(alpha_hat is not None and abs(alpha_hat - alpha_max) <= 1e-10),
            "unconstrained_tcl_mse": unconstrained.get("tcl_mse"),
            "admissible_tcl_mse": constrained.get("tcl_mse"),
            "admissible_tcl_delta": (
                constrained["tcl_mse"] - unconstrained["tcl_mse"]
                if isinstance(constrained.get("tcl_mse"), float)
                and isinstance(unconstrained.get("tcl_mse"), float)
                else None
            ),
        }

    def gram_eigen(self) -> tuple[float | None, float | None, float | None]:
        if self.n == 0:
            return None, None, None
        a = self.sx0x0 / self.n
        b = self.sx0x1 / self.n
        d = self.sx1x1 / self.n
        trace = a + d
        det = a * d - b * b
        disc = max(0.0, trace * trace - 4.0 * det)
        eig_max = 0.5 * (trace + math.sqrt(disc))
        eig_min = 0.5 * (trace - math.sqrt(disc))
        condition = eig_max / eig_min if eig_min and eig_min > EPS else None
        return eig_min, eig_max, condition

    def fit_stats(self) -> dict[str, object]:
        beta0, beta1 = self.coefficients()
        eig_min, eig_max, condition = self.gram_eigen()
        if beta0 is None or beta1 is None:
            sse = None
            mse = None
            r2 = None
        else:
            sse = (
                self.syy
                - 2.0 * beta0 * self.sx0y
                - 2.0 * beta1 * self.sx1y
                + beta0 * beta0 * self.sx0x0
                + 2.0 * beta0 * beta1 * self.sx0x1
                + beta1 * beta1 * self.sx1x1
            )
            sse = max(0.0, sse)
            mse = sse / max(1, self.n)
            y_bar = self.sy / self.n if self.n else 0.0
            total = self.syy - self.n * y_bar * y_bar
            r2 = 1.0 - sse / total if total > EPS else None
        return {
            "n": self.n,
            "beta_v": beta0,
            "beta_cpc_mu": beta1,
            "tcl_mse": mse,
            "sse": sse,
            "r2": r2,
            "y_mean": self.sy / self.n if self.n else None,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "gram_lambda_min": eig_min,
            "gram_lambda_max": eig_max,
            "gram_condition_number": condition,
            "admissible": self.admissibility_diagnostics(),
        }

    def score(self, beta0: float | None, beta1: float | None) -> dict[str, object]:
        if beta0 is None or beta1 is None or self.n == 0:
            return {"n": self.n, "sse": None, "tcl_mse": None}
        sse = self._sse(beta0, beta1)
        return {"n": self.n, "sse": sse, "tcl_mse": sse / self.n}

    def score_admissible(self) -> dict[str, object]:
        return self.score(*self.admissible_coefficients())


@dataclass
class MeanAccumulator:
    n: int = 0
    sy: float = 0.0
    syy: float = 0.0

    def add(self, y: float) -> None:
        self.n += 1
        self.sy += y
        self.syy += y * y

    def merge(self, other: "MeanAccumulator") -> None:
        self.n += other.n
        self.sy += other.sy
        self.syy += other.syy

    def mean(self) -> float | None:
        return self.sy / self.n if self.n else None

    def score(self, mean: float | None) -> dict[str, object]:
        if mean is None or self.n == 0:
            return {"n": self.n, "sse": None, "tcl_mse": None}
        sse = self.syy - 2.0 * mean * self.sy + self.n * mean * mean
        sse = max(0.0, sse)
        return {"n": self.n, "sse": sse, "tcl_mse": sse / self.n}


@dataclass
class BatRow:
    campaign_id: str
    item_id: str
    period: str
    contact_price_bin: float | None
    visibility_surplus: float | None
    clicks_surplus: float | None
    contacts_surplus: float | None
    win_bid_surplus: float | None
    ctr: float | None
    cr: float | None
    auction_count: float | None
    platform_num: float | None = None
    platform_p: float | None = None

    @property
    def v(self) -> float | None:
        if self.ctr is None or self.cr is None:
            return None
        return self.ctr * self.cr

    @property
    def mu(self) -> float | None:
        return self.ctr

    @property
    def y(self) -> tuple[float | None, str]:
        if self.win_bid_surplus is not None:
            denom = self.auction_count if self.auction_count is not None else 1.0
            return self.win_bid_surplus / max(denom, 1.0), "win_bid_per_auction"
        return self.contact_price_bin, "contact_price_bin_fallback"


def bat_row_from_csv(row: Mapping[str, str]) -> BatRow:
    return BatRow(
        campaign_id=parse_key(row.get("campaign_id")),
        item_id=parse_key(row.get("item_id")),
        period=parse_key(row.get("period")),
        contact_price_bin=parse_float(row.get("contact_price_bin")),
        visibility_surplus=parse_float(row.get("AuctionVisibilitySurplus")),
        clicks_surplus=parse_float(row.get("AuctionClicksSurplus")),
        contacts_surplus=parse_float(row.get("AuctionContactsSurplus")),
        win_bid_surplus=parse_float(row.get("AuctionWinBidSurplus")),
        ctr=parse_float(row.get("CTRPredicts")),
        cr=parse_float(row.get("CRPredicts")),
        auction_count=parse_float(row.get("AuctionCount")),
        platform_num=parse_float(row.get("x_platfrom_num")),
        platform_p=parse_float(row.get("platform_p")),
    )


def load_campaign_metadata(
    source: str,
    max_rows: int | None = None,
    timeout: int = 120,
) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, object]]:
    meta: dict[tuple[str, str], dict[str, str]] = {}
    categories = Counter()
    rows_seen = 0
    rows_loaded = 0
    for row in iter_csv_rows(source, timeout=timeout):
        rows_seen += 1
        campaign_id = parse_key(row.get("campaign_id"))
        item_id = parse_key(row.get("item_id"))
        if campaign_id and item_id:
            record = {
                "logical_category": parse_key(row.get("logical_category")),
                "microcat_ext": parse_key(row.get("microcat_ext")),
                "region_id": parse_key(row.get("region_id")),
            }
            meta[(campaign_id, item_id)] = record
            rows_loaded += 1
            if record["logical_category"]:
                categories[record["logical_category"]] += 1
        if max_rows is not None and rows_seen >= max_rows:
            break
    report = {
        "rows_seen": rows_seen,
        "rows_loaded": rows_loaded,
        "unique_keys": len(meta),
        "logical_category_count": len(categories),
        "top_logical_categories": categories.most_common(10),
        "truncated": max_rows is not None and rows_seen >= max_rows,
    }
    return meta, report


def bounded_context_label(
    metadata: Mapping[str, str] | None,
    fallback: str,
    category_field: str = "logical_category",
) -> str:
    if metadata:
        value = parse_key(metadata.get(category_field))
        if value:
            return f"{category_field}:{value}"
    return fallback


def stable_period_fold(period: str, folds: int = 5) -> int:
    text = parse_key(period)
    if not text:
        return 0
    try:
        # BAT periods are timestamp-like blocks; grouping before modulo keeps
        # nearby rows together instead of independently hashing each row.
        block = int(float(text) // 3600)
        return block % folds
    except ValueError:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % folds


def price_context_label(context: str, contact_price_bin: float | None) -> str:
    if contact_price_bin is None:
        price = "missing"
    elif abs(contact_price_bin - round(contact_price_bin)) < 1e-9:
        price = str(int(round(contact_price_bin)))
    else:
        price = f"{contact_price_bin:.6g}"
    return f"{context}|price:{price}"


def group_mean_score(
    train_groups: Mapping[str, MeanAccumulator],
    test_groups: Mapping[str, MeanAccumulator],
    fallback_mean: float | None,
) -> dict[str, object]:
    total_sse = 0.0
    total_n = 0
    evaluated_groups = 0
    fallback_groups = 0
    per_group = []
    for label, acc in test_groups.items():
        train_mean = train_groups[label].mean() if label in train_groups else None
        if train_mean is None:
            train_mean = fallback_mean
            fallback_groups += 1
        score = acc.score(train_mean)
        if isinstance(score.get("sse"), float):
            evaluated_groups += 1
            total_sse += score["sse"]
            total_n += acc.n
            per_group.append({"group": label, "n": acc.n, "tcl_mse": score["tcl_mse"]})
    return {
        "n": total_n,
        "sse": total_sse if total_n else None,
        "tcl_mse": total_sse / total_n if total_n else None,
        "evaluated_groups": evaluated_groups,
        "fallback_groups": fallback_groups,
        "per_group": per_group,
    }


def context_standard_error(per_context: Sequence[dict[str, object]]) -> float | None:
    values = [
        float(item["tcl_mse"])
        for item in per_context
        if isinstance(item.get("tcl_mse"), (float, int)) and item.get("n", 0)
    ]
    if len(values) < 2:
        return None
    return statistics.stdev(values) / math.sqrt(len(values))


SUPPORT_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("0", 0, 0),
    ("1-9", 1, 9),
    ("10-99", 10, 99),
    ("100-499", 100, 499),
    ("500+", 500, None),
)


def support_bucket(support: int) -> str:
    for label, lo, hi in SUPPORT_BUCKETS:
        if support >= lo and (hi is None or support <= hi):
            return label
    return "0"


@dataclass
class HeldoutAccumulator:
    min_category_rows: int
    folds: int = 5
    test_fold: int = 4
    train_y: MeanAccumulator = field(default_factory=MeanAccumulator)
    test_y: MeanAccumulator = field(default_factory=MeanAccumulator)
    train_price_context: DefaultDict[str, MeanAccumulator] = field(default_factory=lambda: defaultdict(MeanAccumulator))
    test_price_context: DefaultDict[str, MeanAccumulator] = field(default_factory=lambda: defaultdict(MeanAccumulator))
    train_flat: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    test_flat: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    train_categories: DefaultDict[str, OLS2Accumulator] = field(default_factory=lambda: defaultdict(OLS2Accumulator))
    test_categories: DefaultDict[str, OLS2Accumulator] = field(default_factory=lambda: defaultdict(OLS2Accumulator))
    train_response_proxy: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    test_response_proxy: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    test_response_proxy_contexts: DefaultDict[str, OLS2Accumulator] = field(default_factory=lambda: defaultdict(OLS2Accumulator))

    def add(self, bat: BatRow, context: str, x0: float, x1: float, y: float) -> None:
        is_test = stable_period_fold(bat.period, self.folds) == self.test_fold
        price_label = price_context_label(context, bat.contact_price_bin)
        if is_test:
            self.test_y.add(y)
            self.test_price_context[price_label].add(y)
            self.test_flat.add(x0, x1, y)
            self.test_categories[context].add(x0, x1, y)
            if bat.win_bid_surplus is not None and bat.contact_price_bin is not None:
                self.test_response_proxy.add(bat.win_bid_surplus, bat.contact_price_bin, y)
                self.test_response_proxy_contexts[context].add(bat.win_bid_surplus, bat.contact_price_bin, y)
        else:
            self.train_y.add(y)
            self.train_price_context[price_label].add(y)
            self.train_flat.add(x0, x1, y)
            self.train_categories[context].add(x0, x1, y)
            if bat.win_bid_surplus is not None and bat.contact_price_bin is not None:
                self.train_response_proxy.add(bat.win_bid_surplus, bat.contact_price_bin, y)

    def _score_by_context(
        self,
        model: str,
        flat_beta: tuple[float | None, float | None],
        flat_admissible_beta: tuple[float | None, float | None],
    ) -> tuple[float, int, list[dict[str, object]], int]:
        total_sse = 0.0
        total_n = 0
        fallback_contexts = 0
        per_context = []
        global_mean = self.train_y.mean()
        for context, test_acc in self.test_categories.items():
            if model == "global_mean":
                score = MeanAccumulator(test_acc.n, test_acc.sy, test_acc.syy).score(global_mean)
            elif model == "flat_unconstrained_affine_proxy":
                score = test_acc.score(*flat_beta)
            elif model == "flat_admissible_idvc":
                score = test_acc.score(*flat_admissible_beta)
            elif model == "contextual_unconstrained_affine_proxy":
                train_acc = self.train_categories.get(context)
                beta = train_acc.coefficients() if train_acc is not None and train_acc.n >= self.min_category_rows else flat_beta
                if train_acc is None or train_acc.n < self.min_category_rows:
                    fallback_contexts += 1
                score = test_acc.score(*beta)
            elif model == "contextual_admissible_idvc":
                train_acc = self.train_categories.get(context)
                beta = train_acc.admissible_coefficients() if train_acc is not None and train_acc.n >= self.min_category_rows else flat_admissible_beta
                if train_acc is None or train_acc.n < self.min_category_rows:
                    fallback_contexts += 1
                score = test_acc.score(*beta)
            else:
                raise ValueError(model)
            if isinstance(score.get("sse"), float):
                total_sse += score["sse"]
                total_n += test_acc.n
                per_context.append({"context": context, "n": test_acc.n, "tcl_mse": score["tcl_mse"]})
        return total_sse, total_n, per_context, fallback_contexts

    def _model_report(
        self,
        model: str,
        flat_beta: tuple[float | None, float | None],
        flat_admissible_beta: tuple[float | None, float | None],
    ) -> dict[str, object]:
        total_sse, total_n, per_context, fallback_contexts = self._score_by_context(model, flat_beta, flat_admissible_beta)
        return {
            "model": model,
            "test_rows": total_n,
            "test_tcl_mse": total_sse / total_n if total_n else None,
            "context_block_se": context_standard_error(per_context),
            "context_blocks": len(per_context),
            "fallback_contexts": fallback_contexts,
        }

    def _bucket_rows_from_scores(
        self,
        model: str,
        support_scope: str,
        scores: Iterable[tuple[str, int, dict[str, object], bool]],
    ) -> list[dict[str, object]]:
        buckets: dict[str, dict[str, object]] = {}
        for label, lo, hi in SUPPORT_BUCKETS:
            buckets[label] = {
                "model": model,
                "support_scope": support_scope,
                "support_bucket": label,
                "support_min": lo,
                "support_max": hi,
                "test_rows": 0,
                "sse": 0.0,
                "context_blocks": 0,
                "fallback_blocks": 0,
                "per_context": [],
            }
        for block, support, score, used_fallback in scores:
            sse = score.get("sse")
            tcl_mse = score.get("tcl_mse")
            n = score.get("n", 0)
            if not isinstance(sse, float) or not isinstance(n, int) or n <= 0:
                continue
            bucket = buckets[support_bucket(support)]
            bucket["test_rows"] = int(bucket["test_rows"]) + n
            bucket["sse"] = float(bucket["sse"]) + sse
            bucket["context_blocks"] = int(bucket["context_blocks"]) + 1
            if used_fallback:
                bucket["fallback_blocks"] = int(bucket["fallback_blocks"]) + 1
            bucket["per_context"].append({"context": block, "n": n, "tcl_mse": tcl_mse})

        rows = []
        for label, _, _ in SUPPORT_BUCKETS:
            bucket = buckets[label]
            test_rows = int(bucket["test_rows"])
            if test_rows <= 0:
                continue
            per_context = bucket.pop("per_context")
            sse = float(bucket.pop("sse"))
            bucket["test_tcl_mse"] = sse / test_rows
            bucket["context_block_se"] = context_standard_error(per_context)
            rows.append(bucket)
        return rows

    def _category_price_support_rows(self) -> list[dict[str, object]]:
        train_global_mean = self.train_y.mean()
        scores = []
        for label, test_acc in self.test_price_context.items():
            train_acc = self.train_price_context.get(label)
            support = train_acc.n if train_acc is not None else 0
            train_mean = train_acc.mean() if train_acc is not None else None
            used_fallback = train_mean is None
            if train_mean is None:
                train_mean = train_global_mean
            scores.append((label, support, test_acc.score(train_mean), used_fallback))
        return self._bucket_rows_from_scores("category_price_mean", "category_price_cell", scores)

    def _context_support_rows(
        self,
        model: str,
        flat_beta: tuple[float | None, float | None],
        flat_admissible_beta: tuple[float | None, float | None],
    ) -> list[dict[str, object]]:
        scores = []
        for context, test_acc in self.test_categories.items():
            train_acc = self.train_categories.get(context)
            support = train_acc.n if train_acc is not None else 0
            if model == "flat_unconstrained_affine_proxy":
                beta = flat_beta
                used_fallback = False
            elif model == "flat_admissible_idvc":
                beta = flat_admissible_beta
                used_fallback = False
            elif model == "contextual_unconstrained_affine_proxy":
                if train_acc is not None and train_acc.n >= self.min_category_rows:
                    beta = train_acc.coefficients()
                    used_fallback = False
                else:
                    beta = flat_beta
                    used_fallback = True
            elif model == "contextual_admissible_idvc":
                if train_acc is not None and train_acc.n >= self.min_category_rows:
                    beta = train_acc.admissible_coefficients()
                    used_fallback = False
                else:
                    beta = flat_admissible_beta
                    used_fallback = True
            else:
                raise ValueError(model)
            scores.append((context, support, test_acc.score(*beta), used_fallback))
        return self._bucket_rows_from_scores(model, "context_cell", scores)

    def _response_proxy_support_rows(self, response_beta: tuple[float | None, float | None]) -> list[dict[str, object]]:
        scores = []
        for context, test_acc in self.test_response_proxy_contexts.items():
            train_acc = self.train_categories.get(context)
            support = train_acc.n if train_acc is not None else 0
            scores.append((context, support, test_acc.score(*response_beta), False))
        rows = self._bucket_rows_from_scores("fpa_response_proxy", "context_cell", scores)
        for row in rows:
            row["proxy_features"] = "AuctionWinBidSurplus_total + contact_price_bin"
        return rows

    def _support_stratified_reports(
        self,
        flat_beta: tuple[float | None, float | None],
        flat_admissible_beta: tuple[float | None, float | None],
        response_beta: tuple[float | None, float | None],
    ) -> list[dict[str, object]]:
        rows = []
        rows.extend(self._category_price_support_rows())
        rows.extend(self._context_support_rows("flat_unconstrained_affine_proxy", flat_beta, flat_admissible_beta))
        rows.extend(self._context_support_rows("flat_admissible_idvc", flat_beta, flat_admissible_beta))
        rows.extend(self._context_support_rows("contextual_unconstrained_affine_proxy", flat_beta, flat_admissible_beta))
        rows.extend(self._context_support_rows("contextual_admissible_idvc", flat_beta, flat_admissible_beta))
        rows.extend(self._response_proxy_support_rows(response_beta))
        return rows

    def to_json(self) -> dict[str, object]:
        flat_beta = self.train_flat.coefficients()
        flat_admissible_beta = self.train_flat.admissible_coefficients()
        response_beta = self.train_response_proxy.coefficients()
        train_global_mean = self.train_y.mean()
        price_context = group_mean_score(self.train_price_context, self.test_price_context, train_global_mean)
        models = [
            self._model_report("global_mean", flat_beta, flat_admissible_beta),
            {
                "model": "category_price_mean",
                "test_rows": price_context["n"],
                "test_tcl_mse": price_context["tcl_mse"],
                "context_block_se": context_standard_error(price_context["per_group"]),
                "context_blocks": price_context["evaluated_groups"],
                "fallback_groups": price_context["fallback_groups"],
            },
            self._model_report("flat_unconstrained_affine_proxy", flat_beta, flat_admissible_beta),
            self._model_report("flat_admissible_idvc", flat_beta, flat_admissible_beta),
            self._model_report("contextual_unconstrained_affine_proxy", flat_beta, flat_admissible_beta),
            self._model_report("contextual_admissible_idvc", flat_beta, flat_admissible_beta),
        ]
        response_score = self.test_response_proxy.score(*response_beta)
        if response_score["tcl_mse"] is not None:
            models.append(
                {
                    "model": "fpa_response_proxy",
                    "test_rows": response_score["n"],
                    "test_tcl_mse": response_score["tcl_mse"],
                    "context_block_se": None,
                    "context_blocks": None,
                    "proxy_features": "AuctionWinBidSurplus_total + contact_price_bin",
                }
            )
        return {
            "split": {
                "method": "period_block_mod_5",
                "folds": self.folds,
                "test_fold": self.test_fold,
                "train_rows": self.train_y.n,
                "test_rows": self.test_y.n,
            },
            "support_buckets": [
                {"bucket": label, "min_train_support": lo, "max_train_support": hi}
                for label, lo, hi in SUPPORT_BUCKETS
            ],
            "train_flat": self.train_flat.fit_stats(),
            "models": models,
            "support_stratified": self._support_stratified_reports(flat_beta, flat_admissible_beta, response_beta),
        }


@dataclass
class BatAccumulator:
    flat: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    categories: DefaultDict[str, OLS2Accumulator] = field(default_factory=lambda: defaultdict(OLS2Accumulator))
    numeric: DefaultDict[str, NumericSummary] = field(default_factory=lambda: defaultdict(NumericSummary))
    y_sources: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    row_count: int = 0
    usable_count: int = 0
    campaign_matches: int = 0
    campaign_misses: int = 0
    platform_rows: int = 0
    response_proxy: OLS2Accumulator = field(default_factory=OLS2Accumulator)
    response_ratio_summary: NumericSummary = field(default_factory=NumericSummary)
    response_ratio_histogram: Counter = field(default_factory=Counter)
    response_ratios: list[float] = field(default_factory=list)
    heldout: HeldoutAccumulator | None = None

    def ensure_heldout(self, min_category_rows: int) -> HeldoutAccumulator:
        if self.heldout is None or self.heldout.min_category_rows != min_category_rows:
            self.heldout = HeldoutAccumulator(min_category_rows=min_category_rows)
        return self.heldout

    def add(
        self,
        bat: BatRow,
        campaign: Mapping[str, str] | None = None,
        context_fallback: str = "unmatched",
    ) -> None:
        self.row_count += 1
        values = {
            "contact_price_bin": bat.contact_price_bin,
            "AuctionVisibilitySurplus": bat.visibility_surplus,
            "AuctionClicksSurplus": bat.clicks_surplus,
            "AuctionContactsSurplus": bat.contacts_surplus,
            "AuctionWinBidSurplus": bat.win_bid_surplus,
            "CTRPredicts": bat.ctr,
            "CRPredicts": bat.cr,
            "AuctionCount": bat.auction_count,
            "v": bat.v,
            "mu": bat.mu,
            "x_platfrom_num": bat.platform_num,
            "platform_p": bat.platform_p,
        }
        for name, value in values.items():
            self.numeric[name].add(value)
        if bat.platform_num is not None or bat.platform_p is not None:
            self.platform_rows += 1

        y, y_source = bat.y
        self.y_sources[y_source] += 1
        if campaign is None:
            self.campaign_misses += 1
        else:
            self.campaign_matches += 1
        if bat.v is None or bat.mu is None or bat.contact_price_bin is None or y is None:
            self.skipped["missing_model_feature"] += 1
            return
        x0 = bat.v
        x1 = bat.contact_price_bin * bat.mu
        if abs(x0) <= EPS and abs(x1) <= EPS:
            self.skipped["zero_design_row"] += 1
            return
        label = bounded_context_label(campaign, context_fallback)
        self.usable_count += 1
        self.flat.add(x0, x1, y)
        self.categories[label].add(x0, x1, y)
        if self.heldout is not None:
            self.heldout.add(bat, label, x0, x1, y)

        if bat.win_bid_surplus is not None and bat.contact_price_bin is not None:
            raw_bid = bat.win_bid_surplus
            self.response_proxy.add(raw_bid, bat.contact_price_bin, y)
            if abs(bat.contact_price_bin) > EPS:
                ratio = y / bat.contact_price_bin
                self.response_ratio_summary.add(ratio)
                self.response_ratio_histogram[ratio_bin(ratio)] += 1
                if len(self.response_ratios) < 50000:
                    self.response_ratios.append(ratio)

    def contextual_report(self, min_rows: int) -> dict[str, object]:
        used = []
        skipped = []
        aggregate = OLS2Accumulator()
        unconstrained_sse = 0.0
        admissible_sse = 0.0
        contextual_n = 0
        violation_counts = Counter()
        weak_design_counts = Counter()
        for label, acc in self.categories.items():
            if acc.n >= min_rows:
                stats = acc.fit_stats()
                used.append({"category": label, **stats})
                aggregate.merge(acc)
                condition = stats.get("gram_condition_number")
                if condition is None:
                    weak_design_counts["condition_missing"] += 1
                elif isinstance(condition, (float, int)) and condition > 1e6:
                    weak_design_counts["condition_gt_1e6"] += 1
                if isinstance(stats.get("sse"), float):
                    unconstrained_sse += stats["sse"]
                    contextual_n += acc.n
                admissible_score = acc.score_admissible()
                if isinstance(admissible_score.get("sse"), float):
                    admissible_sse += admissible_score["sse"]
                diagnostics = stats.get("admissible", {})
                if isinstance(diagnostics, Mapping):
                    for key in (
                        "unconstrained_s_below_min",
                        "unconstrained_alpha_below_zero",
                        "unconstrained_alpha_above_one",
                        "admissible_active_s_min",
                        "admissible_active_alpha_min",
                        "admissible_active_alpha_max",
                    ):
                        if diagnostics.get(key):
                            violation_counts[key] += 1
            else:
                skipped.append({"category": label, "n": acc.n})
        used.sort(key=lambda x: (-int(x["n"]), str(x["category"])))
        skipped.sort(key=lambda x: (-int(x["n"]), str(x["category"])))
        return {
            "min_rows": min_rows,
            "bins_total": len(self.categories),
            "bins_used": len(used),
            "bins_skipped": len(skipped),
            "pooled_used_stats": aggregate.fit_stats() if aggregate.n else None,
            "contextual_tcl_mse": unconstrained_sse / contextual_n if contextual_n else None,
            "contextual_unconstrained_tcl_mse": unconstrained_sse / contextual_n if contextual_n else None,
            "contextual_admissible_tcl_mse": admissible_sse / contextual_n if contextual_n else None,
            "contextual_admissible_tcl_delta": (
                (admissible_sse - unconstrained_sse) / contextual_n if contextual_n else None
            ),
            "contextual_rows": contextual_n,
            "admissibility_violation_counts": dict(violation_counts),
            "weak_design_counts": dict(weak_design_counts),
            "used_bins": used,
            "top_bins": used[:25],
            "skipped_bins": skipped,
            "top_skipped_bins": skipped[:25],
        }

    def response_report(self) -> dict[str, object]:
        ratio_median = statistics.median(self.response_ratios) if self.response_ratios else None
        ratio_summary = self.response_ratio_summary.to_json()
        return {
            "proxy_fit": self.response_proxy.fit_stats(),
            "proxy_features": "AuctionWinBidSurplus_total + contact_price_bin",
            "proxy_target": "AuctionWinBidSurplus / max(AuctionCount, 1)",
            "y_over_contact_price_bin_mean": ratio_summary["mean"],
            "y_over_contact_price_bin_median": ratio_median,
            "ratio_sample_count": self.response_ratio_summary.count,
            "ratio_summary": ratio_summary,
            "ratio_histogram": dict(sorted(self.response_ratio_histogram.items(), key=lambda kv: ratio_bin_order(kv[0]))),
            "interpretation": (
                "Proxy-only diagnostic: public BAT exposes realized surplus and contact-price bins, "
                "not the full first-price response curve. The proxy fit uses total win-bid surplus "
                "and contact-price-bin covariates to diagnose response dependence; it is not a "
                "structural response decomposition."
            ),
        }

    def to_json(self, min_category_rows: int) -> dict[str, object]:
        return {
            "rows_seen": self.row_count,
            "usable_rows": self.usable_count,
            "skipped_rows": dict(self.skipped),
            "y_sources": dict(self.y_sources),
            "campaign_matches": self.campaign_matches,
            "campaign_misses": self.campaign_misses,
            "platform_rows": self.platform_rows,
            "feature_summaries": {k: v.to_json() for k, v in sorted(self.numeric.items())},
            "flat_ols": self.flat.fit_stats(),
            "contextual_bins": self.contextual_report(min_category_rows),
            "heldout_baselines": self.heldout.to_json() if self.heldout is not None else None,
        }


def schema_report(
    observed_columns: Sequence[str],
    required_columns: Sequence[str],
    optional_columns: Sequence[str] = (),
) -> dict[str, object]:
    observed = set(observed_columns)
    required = set(required_columns)
    optional = set(optional_columns)
    return {
        "observed_columns": list(observed_columns),
        "required_columns": list(required_columns),
        "optional_columns": list(optional_columns),
        "missing_required": sorted(required - observed),
        "missing_optional": sorted(optional - observed),
        "extra_columns": sorted(observed - required - optional),
        "valid": not bool(required - observed),
    }


def markdown_table(rows: Iterable[Sequence[object]]) -> str:
    rows = list(rows)
    if not rows:
        return ""
    header = rows[0]
    sep = ["---"] * len(header)
    out = ["| " + " | ".join(str(x) for x in header) + " |"]
    out.append("| " + " | ".join(sep) + " |")
    for row in rows[1:]:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def fmt(value: object, digits: int = 6) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        if not math.isfinite(value):
            return "NA"
        return f"{value:.{digits}g}"
    return str(value)


RATIO_BINS = [
    ("0", 0.0, 0.0),
    ("(0,0.01]", 0.0, 0.01),
    ("(0.01,0.05]", 0.01, 0.05),
    ("(0.05,0.1]", 0.05, 0.1),
    ("(0.1,0.25]", 0.1, 0.25),
    ("(0.25,0.5]", 0.25, 0.5),
    ("(0.5,1]", 0.5, 1.0),
    ("(1,2]", 1.0, 2.0),
    ("(2,5]", 2.0, 5.0),
    (">5", 5.0, float("inf")),
]


def ratio_bin(value: float) -> str:
    if value <= 0.0:
        return "0"
    for label, lo, hi in RATIO_BINS[1:]:
        if lo < value <= hi:
            return label
    return ">5"


def ratio_bin_order(label: str) -> int:
    labels = [x[0] for x in RATIO_BINS]
    return labels.index(label) if label in labels else len(labels)
