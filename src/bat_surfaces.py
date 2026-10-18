"""Accumulate admissible category-hour surfaces during the BAT calibration pass."""

import math
import statistics
from collections import Counter, defaultdict

from src.experiment_utils import OLS2Accumulator


class CategoryHourSurface:
    def __init__(self):
        self.cells = defaultdict(OLS2Accumulator)
        self.category_counts = Counter()

    def add(self, bat, campaign):
        category = (campaign or {}).get("logical_category")
        hour = hour_from_period(bat.period)
        y, _ = bat.y
        if not category or hour is None or any(value is None for value in (y, bat.v, bat.mu, bat.contact_price_bin)):
            return
        x0, x1 = bat.v, bat.contact_price_bin * bat.mu
        if abs(x0) <= 1e-12 and abs(x1) <= 1e-12:
            return
        self.cells[(category, hour)].add(x0, x1, y)
        self.category_counts[category] += 1

    def result(self, top_categories, min_cell_rows):
        return {"min_cell_rows": min_cell_rows,
                "surface": surface_from_cells(self.cells, self.category_counts, top_categories, min_cell_rows)}

def hour_from_period(period: str) -> int | None:
    try:
        return int(float(period) // 3600) % 24
    except (TypeError, ValueError):
        return None


def category_sort_key(category: str) -> tuple[object, ...]:
    out: list[object] = []
    for part in category.split("."):
        try:
            out.append(int(part))
        except ValueError:
            out.append(part)
    return tuple(out)


def surface_from_cells(
    cells: dict[tuple[str, int], OLS2Accumulator],
    category_counts: dict[str, int],
    top_categories: int,
    min_cell_rows: int,
) -> dict[str, object]:
    categories = [
        category
        for category, _ in sorted(category_counts.items(), key=lambda item: (-item[1], category_sort_key(item[0])))[:top_categories]
    ]
    surface: dict[str, object] = {
        "categories": categories,
        "hours": list(range(24)),
        "s": [],
        "alpha": [],
        "n": [],
    }
    s_rows: list[list[float | None]] = []
    alpha_rows: list[list[float | None]] = []
    n_rows: list[list[int]] = []
    for category in categories:
        row_s: list[float | None] = []
        row_alpha: list[float | None] = []
        row_n: list[int] = []
        for hour in range(24):
            acc = cells.get((category, hour))
            if acc is None or acc.n < min_cell_rows:
                row_s.append(None)
                row_alpha.append(None)
                row_n.append(0)
                continue
            s_hat, alpha_hat = acc.admissible_coefficients()
            row_s.append(float(s_hat) if s_hat is not None else None)
            row_alpha.append(float(alpha_hat) if alpha_hat is not None else None)
            row_n.append(acc.n)
        s_rows.append(row_s)
        alpha_rows.append(row_alpha)
        n_rows.append(row_n)
    surface["s"] = s_rows
    surface["alpha"] = alpha_rows
    surface["n"] = n_rows
    return surface


def select_categories(surface: dict[str, object], coord: str, min_hours: int, limit: int) -> list[tuple[str, int, int, float, float]]:
    categories = list(surface["categories"])
    n_rows = list(surface["n"])
    values = list(surface[coord])
    selected: list[tuple[str, int, int, float, float]] = []
    for idx, category in enumerate(categories):
        supported = [
            value
            for value, n in zip(values[idx], n_rows[idx])
            if n and value is not None
        ]
        if coord == "s":
            supported = [math.log10(max(float(value), 1e-8)) for value in supported]
        if len(supported) < min_hours:
            continue
        span = max(supported) - min(supported)
        std = statistics.pstdev(supported) if len(supported) > 1 else 0.0
        selected.append((category, idx, len(supported), span, std))
    return sorted(selected, key=lambda item: (-item[3], -item[2], item[0]))[:limit]
