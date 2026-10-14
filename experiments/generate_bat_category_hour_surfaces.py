#!/usr/bin/env python3
"""Generate public-BAT category-by-hour proxy dual surface figures."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from experiment_utils import OLS2Accumulator, bat_row_from_csv, iter_csv_rows, load_campaign_metadata


DEFAULT_SOURCES = {
    "vcg": {
        "stats": "experiments/data/bat/raw/vcg/stats.csv",
        "campaigns": "experiments/data/bat/raw/vcg/campaigns.csv",
    },
    "fpa": {
        "stats": "experiments/data/bat/raw/fpa/stats.csv",
        "campaigns": "experiments/data/bat/raw/fpa/campaigns.csv",
    },
}


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


def load_category_hour_cells(stats_path: str, campaigns_path: str, timeout: int) -> tuple[dict[tuple[str, int], OLS2Accumulator], dict[str, int], dict[str, object]]:
    campaign_meta, campaign_report = load_campaign_metadata(campaigns_path, timeout=timeout)
    cells: dict[tuple[str, int], OLS2Accumulator] = defaultdict(OLS2Accumulator)
    category_counts: dict[str, int] = defaultdict(int)
    rows_seen = 0
    matched_rows = 0
    usable_rows = 0

    for row in iter_csv_rows(stats_path, timeout=timeout):
        rows_seen += 1
        bat = bat_row_from_csv(row)
        campaign = campaign_meta.get((bat.campaign_id, bat.item_id))
        if not campaign:
            continue
        matched_rows += 1
        category = campaign.get("logical_category") or ""
        hour = hour_from_period(bat.period)
        y, _ = bat.y
        if (
            not category
            or hour is None
            or y is None
            or bat.v is None
            or bat.mu is None
            or bat.contact_price_bin is None
        ):
            continue
        x0 = bat.v
        x1 = bat.contact_price_bin * bat.mu
        if abs(x0) <= 1e-12 and abs(x1) <= 1e-12:
            continue
        cells[(category, hour)].add(x0, x1, y)
        category_counts[category] += 1
        usable_rows += 1

    report = {
        "rows_seen": rows_seen,
        "matched_rows": matched_rows,
        "usable_rows": usable_rows,
        "campaign_report": campaign_report,
    }
    return cells, category_counts, report


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


def plot_selected_surfaces(payload: dict[str, object], out_dir: Path) -> None:
    plt.rcParams.update(
        {
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "font.size": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
        }
    )
    vcg_surface = payload["vcg"]["surface"]
    fpa_surface = payload["fpa"]["surface"]
    vcg_selection = select_categories(vcg_surface, "alpha", min_hours=20, limit=5)
    fpa_selection = select_categories(fpa_surface, "s", min_hours=24, limit=5)

    fig, axes = plt.subplots(1, 2, figsize=(7.25, 2.55), sharex=True)
    panels = [
        (
            axes[0],
            vcg_surface,
            "alpha",
            vcg_selection,
            r"VCG proxy: $\hat\alpha$ by category-hour",
            "viridis",
            0.0,
            0.5,
            r"$\hat\alpha$",
        ),
        (
            axes[1],
            fpa_surface,
            "s",
            fpa_selection,
            r"FPA proxy: $\log_{10}\hat s$ by category-hour",
            "magma",
            None,
            None,
            r"$\log_{10}\hat s$",
        ),
    ]
    for ax, surface, coord, selection, title, cmap_name, vmin, vmax, colorbar_label in panels:
        labels = [f"{category} ({hours}/24h)" for category, _, hours, _, _ in selection]
        data = []
        support = []
        for _, idx, _, _, _ in selection:
            row = []
            support_row = []
            for value, n in zip(surface[coord][idx], surface["n"][idx]):
                support_row.append(n)
                if n and value is not None:
                    row.append(math.log10(max(float(value), 1e-8)) if coord == "s" else float(value))
                else:
                    row.append(np.nan)
            data.append(row)
            support.append(support_row)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad("#eeeeee")
        image = ax.imshow(
            np.ma.masked_invalid(np.array(data, dtype=float)),
            aspect="auto",
            interpolation="nearest",
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
        )
        ax.set_title(title)
        ax.set_yticks(np.arange(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_xticks([0, 6, 12, 18, 23])
        ax.set_xticklabels(["0", "6", "12", "18", "23"])
        ax.set_xlabel("hour of day from BAT period")
        ax.set_ylabel("logical category")
        colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.018)
        colorbar.set_label(colorbar_label, fontsize=7)
        colorbar.ax.tick_params(labelsize=6)
        support_array = np.array(support, dtype=float)
        for y in range(support_array.shape[0]):
            for x in range(support_array.shape[1]):
                if support_array[y, x] and support_array[y, x] < 10000:
                    ax.plot(x, y, marker=".", color="white", markersize=1.0, alpha=0.65)

    fig.text(
        0.5,
        0.02,
        "Rows selected for display: at least 20 supported hours, then largest within-day dual variation; gray cells have <5000 rows.",
        ha="center",
        fontsize=6.7,
    )
    fig.tight_layout(rect=[0, 0.07, 1, 1], pad=0.35)
    fig.savefig(out_dir / "bat_selected_category_hour_dual_surfaces_clean.png", dpi=220, bbox_inches="tight")
    fig.savefig(out_dir / "bat_selected_category_hour_dual_surfaces_clean.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="experiments/results")
    parser.add_argument("--top-categories", type=int, default=10)
    parser.add_argument("--min-cell-rows", type=int, default=5000)
    parser.add_argument("--timeout", type=int, default=120)
    for auction, sources in DEFAULT_SOURCES.items():
        parser.add_argument(f"--{auction}-stats", default=sources["stats"])
        parser.add_argument(f"--{auction}-campaigns", default=sources["campaigns"])
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {}
    for auction in ("vcg", "fpa"):
        cells, category_counts, report = load_category_hour_cells(
            getattr(args, f"{auction}_stats"),
            getattr(args, f"{auction}_campaigns"),
            timeout=args.timeout,
        )
        payload[auction] = {
            "report": report,
            "min_cell_rows": args.min_cell_rows,
            "surface": surface_from_cells(cells, category_counts, args.top_categories, args.min_cell_rows),
        }

    summary_path = out_dir / "bat_category_hour_dual_surface_summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    plot_selected_surfaces(payload, figures_dir)
    print(f"Wrote {summary_path} and {figures_dir / 'bat_selected_category_hour_dual_surfaces_clean.pdf'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
