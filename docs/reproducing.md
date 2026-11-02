# Configuration and reproduction

Use Python 3.10+ and install `requirements.txt`. Run commands from the repository
root. The default `python -m experiments` runs warm start with the paper's
100 seeds and 100 controller updates, then draws its plots.

## Change an experiment

Edit `config.yaml`. Start with these controls:

| Setting | Effect |
| --- | --- |
| `tasks` | Which experiments run, in order. |
| `output_dir` | Where each task's gallery, figures, and data are saved. |
| `seeds`, `contexts`, `horizon` | Experiment size. |
| `gain`, `tolerance` | Controller updates and violation threshold. |
| `guard_z`, `shrinkage` | Transfer guard and strength of shrinkage. |
| `sensitivity_grid` | Bridge shift/response multipliers. |
| `max_rows`, `min_category_rows`, `min_cell_rows` | BAT row cap and calibration/plot support. |

To keep the original configuration, create a small `trial.yaml`:

```yaml
tasks: [warm_start]
output_dir: outputs/faster-controller
warm_start:
  gain: 0.4
```

```bash
python -m experiments --config trial.yaml
```

Open `outputs/faster-controller/warm_start/index.html`. The gallery includes the
parameters used. A rerun replaces files in that run's output folder; choose a
new `output_dir` to keep multiple runs. Relative paths use the working directory.

Useful shortcuts:

```bash
python -m experiments --print-config
python -m experiments warm_start --gain 0.4 --output-dir outputs/trial
python -m experiments supported_bridge --seeds 3 --contexts 12 --no-sensitivity
python -m experiments bat_calibration --max-rows 2000
```

Precedence is **CLI > custom YAML > repository YAML**. `--help` lists options.
`plots: false` skips figures; `progress: false` suppresses stage messages and
bars. Both also accept `--no-plots` / `--no-progress`. The final output location
is always printed. Legacy per-task `--out`, `--report`, and BAT `--out-dir` still
work. Individual `experiments.*` entry points use the same pipeline.

## Reproduce the paper plots

Set `tasks: [warm_start, bat_calibration]` and retain the
checked-in parameters. Warm start generates `warm_start_effect_forest.pdf`;
BAT generates `bat_selected_category_hour_dual_surfaces_clean.pdf`. These share
the paper's plotting routines. Changing parameters reruns the experiment and
replots its outputs, so the resulting figures are experimental variants.

Add `supported_bridge` to run the experiment reported in the camera-ready's
*Supported mechanism evidence* table and text. Its comparison and sensitivity
plots are additional repository visualizations, not camera-ready figures.

BAT surfaces are accumulated in the same CSV pass as calibration. Sparse cells
are masked, and a panel explains when no category meets the paper's hour-support
criteria. Small row-capped checks may therefore have no surface to display.
The static method illustration is conceptual, so it is not regenerated per run.

The JSON and detailed Markdown report are saved beside the figures. Reference
artifacts in `experiments/results/` are preserved by the default output path.
Scenario definitions, admissibility bounds, and evidence gates remain in the
source; they define the protocol. See [evaluation.md](evaluation.md).

## BAT inputs

Local files are preferred at `experiments/data/bat/raw/{vcg,fpa}/{stats,campaigns}.csv`.
Otherwise the runner streams public `AvitoTech/BAT` CSVs; it does not cache the
stream. Status messages distinguish local reads from streaming. For repeated
runs, provide local paths using `vcg_stats`, `vcg_campaigns`, `fpa_stats`, and
`fpa_campaigns` in the BAT config section. These fields also accept URLs.

Full BAT and bridge sensitivity runs are much slower than warm start. Use
`max_rows` for a BAT check and fewer seeds/contexts for a bridge check; these
are not full paper reproductions. BAT uses the declared proxy
`AuctionWinBidSurplus / max(AuctionCount, 1)` and enforces admissible dual fits.

## Tests and supplementary tools

Tests are optional when running experiments. Run them when changing the code:

```bash
pip install pytest
python -m pytest -q
```

The suite checks configuration, progress, plots, and scientific validity. It runs
all three tasks with small local CSV fixtures; no download is needed. Pytest
only collects `tests/`, excluding local backups. For a quick config-to-plot check,
use `python -m pytest -q tests/test_plot_pipeline.py`.

Supplementary analysis remains under `src/`:
`bat_cold_start_runner` for chronological replay, `run_full_synthetic` for
identification diagnostics, and `generate_paper_artifacts` for the complete
reference tables/figures. These tools retain their own `--help` interfaces.
`python -m src.run_all` aliases the main configured pipeline.
