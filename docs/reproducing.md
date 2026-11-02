# Configuration and reproduction

Use Python 3.10+ and install `requirements.txt`. Run commands from the repository
root. The default `python -m experiments` runs warm start with the reference
100 seeds and 100 controller updates, then draws effect sizes and first-32-step absolute state errors.
The [README](../README.md) records the model, every YAML parameter, and the
current evidence boundaries.

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
is always printed. Per-task `--out`, `--report`, and BAT `--out-dir` still
work. Individual `experiments.*` entry points use the same pipeline.

## Reproduce the paper plots

Set `tasks: [warm_start, bat_calibration]` and retain the
checked-in parameters. Warm start generates `warm_start_effect_forest.pdf`;
BAT generates `bat_selected_category_hour_dual_surfaces_clean.pdf`. These share
the manuscript's plotting routines. Changing parameters reruns the experiment and
replots its outputs, so the resulting figures are experimental variants.

Add `supported_bridge` to run the controlled scalar-state diagnostic. It does
not read BAT or fit a dual surface. Its comparison and sensitivity plots show
conditional simulation results, not auction-level decision evidence.

BAT surfaces are accumulated in the same CSV pass as calibration. Sparse cells
are masked, and a panel explains when no category meets the paper's hour-support
criteria. Small row-capped checks may therefore have no surface to display.
The static method illustration is conceptual; regenerate it with the paper
artifact generator. Manuscript sources and published reference figures are outside the scope of
code maintenance and must not be changed by this workflow.

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

## Essential paper artifacts

```bash
python -m src.generate_paper_artifacts \
  --bat experiments/results/bat_full_admissible.json \
  --cold-start experiments/results/bat_cold_start_frontier_full.json \
  --warm-start outputs/warm_start/results.json \
  --bridge outputs/supported_bridge/results.json \
  --out-dir outputs/paper
```

Run the two simulations first. This command reads existing JSON; it does not
rerun experiments. It writes evidence tables, a model diagram, held-out proxy
loss with the flexible reference, a seed-level effect forest, and state-error
curves. It no longer emits the old cumulative-reward lines or legacy dashboards.
The generator defaults to `outputs/paper/`; these are code-analysis outputs,
not replacements for figures of the submitted manuscript. Data-only reruns
also remove obsolete cumulative-reward files from their own output folder.
Old local experiment-output plots are archived under `outputs/archive-2026-11-02/`.
Original research figures under `experiments/results/figures/` have been restored.

The full chronological BAT replay is separate from calibration and can be much
more expensive. A capped calibration run is only a pipeline check; checking a
saved full replay is not equivalent to rerunning that replay.
