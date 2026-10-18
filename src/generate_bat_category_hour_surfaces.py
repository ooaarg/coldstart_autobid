#!/usr/bin/env python3
"""Generate public-BAT category-by-hour proxy dual surface figures."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.bat_surfaces import CategoryHourSurface, surface_from_cells, select_categories

from src.experiment_utils import OLS2Accumulator, bat_row_from_csv, iter_csv_rows, load_campaign_metadata


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


def load_category_hour_cells(stats_path: str, campaigns_path: str, timeout: int) -> tuple[dict[tuple[str, int], OLS2Accumulator], dict[str, int], dict[str, object]]:
    campaign_meta, campaign_report = load_campaign_metadata(campaigns_path, timeout=timeout)
    accumulator = CategoryHourSurface()
    rows_seen = matched_rows = 0
    for row in iter_csv_rows(stats_path, timeout=timeout):
        rows_seen += 1
        bat = bat_row_from_csv(row)
        campaign = campaign_meta.get((bat.campaign_id, bat.item_id))
        matched_rows += bool(campaign)
        accumulator.add(bat, campaign)
    report = {
        "rows_seen": rows_seen,
        "matched_rows": matched_rows,
        "usable_rows": sum(accumulator.category_counts.values()),
        "campaign_report": campaign_report,
    }
    return accumulator.cells, accumulator.category_counts, report


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
    auctions = list(payload)
    fig, axes = plt.subplots(1, len(auctions), figsize=(3.625 * len(auctions), 2.85), squeeze=False)
    panels = []
    for ax, auction in zip(axes[0], auctions):
        surface = payload[auction]["surface"]
        coord = "alpha" if auction == "vcg" else "s"
        selection = select_categories(surface, coord, min_hours=20 if auction == "vcg" else 24, limit=5)
        panels.append((ax, surface, coord, selection,
                       f"{auction.upper()} proxy: " + (r"$\hat\alpha$" if coord == "alpha" else r"$\log_{10}\hat s$") + " by category-hour",
                       "viridis" if coord == "alpha" else "magma",
                       0.0 if coord == "alpha" else None,
                       1.0 if coord == "alpha" else None,
                       r"$\hat\alpha$" if coord == "alpha" else r"$\log_{10}\hat s$"))
    for ax, surface, coord, selection, title, cmap_name, vmin, vmax, colorbar_label in panels:
        ax.grid(False)
        if not selection:
            ax.set_title(title)
            ax.text(0.5, 0.5, "Not enough supported category-hours\nTry more rows or a lower min_cell_rows", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            continue
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
        cmap = plt.get_cmap(cmap_name).with_extremes(bad="#eeeeee")
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
        "Selection: 20 supported hours (VCG), 24 (FPA), then largest variation.\n"
        + "Masked below min_cell_rows: " + ", ".join(f"{auction.upper()}={payload[auction]['min_cell_rows']}" for auction in auctions),
        ha="center",
        fontsize=6.7,
    )
    fig.tight_layout(rect=[0, 0.14, 1, 1], pad=0.35)
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
