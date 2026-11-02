"""The conceptual model diagram shared by the manuscript and README."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def plot_idvc_workflow_surface_panel(figures_dir: Path) -> None:
    # Keep the workflow legible at column width without spending vertical space
    # on a large gap between its two rows.
    fig, ax = plt.subplots(figsize=(3.35, 1.38))
    ax.set_xlim(0, 1)
    ax.set_ylim(0.08, 0.99)
    ax.axis("off")

    def box(
        x: float,
        y: float,
        w: float,
        h: float,
        text: str,
        face: str,
        edge: str = "#4b5563",
    ) -> None:
        patch = mpatches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.018",
            linewidth=0.8,
            edgecolor=edge,
            facecolor=face,
        )
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.7)

    def arrow(start: tuple[float, float], end: tuple[float, float]) -> None:
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops={"arrowstyle": "-|>", "lw": 0.9, "color": "#4b5563", "shrinkA": 2, "shrinkB": 2},
        )

    box(0.02, 0.58, 0.25, 0.21, "historical logs\n$(z_i,f_i,Y_i)$", "#edf2f7")
    box(0.38, 0.58, 0.25, 0.21, "fit admissible\n$\\hat\\Theta(z)$", "#e8f3ec")
    box(0.73, 0.58, 0.25, 0.21, "dual surface\n$s>0,\\;0\\leq\\alpha\\leq1$", "#e8f3ec")
    box(0.02, 0.10, 0.25, 0.21, "new ad + constraints\n$(z_1,v_1,C_1\\mu_1)$", "#fff3df")
    box(0.38, 0.10, 0.25, 0.21, "margin\n$\\hat m_1=f_1^\\top\\hat\\Theta(z_1)$", "#fff3df")
    box(0.73, 0.10, 0.25, 0.21, "first bid\n$\\hat m_1$ or $\\hat\\phi_z^{-1}(\\hat m_1)$", "#f2ecf8")
    arrow((0.27, 0.685), (0.38, 0.685))
    arrow((0.63, 0.685), (0.73, 0.685))
    arrow((0.85, 0.58), (0.54, 0.31))
    arrow((0.27, 0.205), (0.38, 0.205))
    arrow((0.63, 0.205), (0.73, 0.205))
    ax.text(0.02, 0.97, "Cold-start initialization path", fontsize=8.5, weight="bold", va="top")
    fig.tight_layout(pad=0.2)
    figures_dir.mkdir(parents=True, exist_ok=True)
    # Crop to the artists rather than the full Matplotlib canvas.  This removes
    # the otherwise visible strip below the lower row when embedded in LaTeX.
    fig.savefig(
        figures_dir / "idvc_workflow_surface_panel.png",
        dpi=220,
        bbox_inches="tight",
        pad_inches=0.015,
    )
    fig.savefig(
        figures_dir / "idvc_workflow_surface_panel.pdf",
        bbox_inches="tight",
        pad_inches=0.015,
    )
    plt.close(fig)
