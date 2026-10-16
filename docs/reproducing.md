# Reproducing the paper

Run commands from the repository root with Python 3.10 or newer. The experiment
runners use the standard library; only plotting requires additional packages.
The release is checked with Python 3.13.

## Main experiments

Each entry point uses the configuration of the corresponding paper experiment:

```bash
python3 -m experiments.warm_start
python3 -m experiments.supported_bridge
python3 -m experiments.bat_calibration
```

Warm start runs 100 seeds and 100 controller updates. The supported bridge runs
100 seeds, 60 contexts, the declared supported and negative-control scenarios,
and the 3-by-3 shift/response sensitivity grid. It is semi-synthetic and is
reported separately from unchanged public BAT.

The BAT case evaluates full VCG and FPA calibration with admissibility enforced.
It uses `AuctionWinBidSurplus / max(AuctionCount, 1)` as the declared benchmark
proxy target, not as a raw winning-price label. It does not establish public-BAT
deployment lift. The calibration split uses period-block folds; the separate
campaign replay uses chronological splits. See [the protocol](evaluation.md).

## BAT data

BAT runners stream the public `AvitoTech/BAT` CSVs when local files are absent.
Full runs process millions of rows. Local CSVs are detected at:

```text
experiments/data/bat/raw/vcg/stats.csv
experiments/data/bat/raw/vcg/campaigns.csv
experiments/data/bat/raw/fpa/stats.csv
experiments/data/bat/raw/fpa/campaigns.csv
```

Use `--vcg-stats`, `--vcg-campaigns`, `--fpa-stats`, and `--fpa-campaigns`
with the BAT entry point to supply other paths or URLs. Dataset access can be
checked separately with `python3 -m src.bat_download_check`.

## Outputs and reference results

All main entry points write JSON and Markdown reports under
`experiments/results/`. Selected reference results and figures are included in
the repository. The full warm-start result JSON can be regenerated with its
entry point. Raw CSVs, caches, and newly generated files are ignored by Git.

To preserve the included reference files, choose different output paths:

```bash
python3 -m experiments.warm_start --out experiments/results/my_warm_start.json --report experiments/results/my_warm_start.md
python3 -m experiments.supported_bridge --out experiments/results/my_bridge.json --report experiments/results/my_bridge.md
python3 -m experiments.bat_calibration --out-dir experiments/results/my_bat
```

Each entry point also supports `--help`.

## Figures and tables

Create a plotting environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The category/hour surface figure reads the BAT CSVs directly. It accepts the
same four CSV path options; its defaults are the local paths above:

```bash
.venv/bin/python -m src.generate_bat_category_hour_surfaces
```

Generate the paper workflow, warm-start forest plot, and experiment tables:

```bash
.venv/bin/python -m src.generate_paper_artifacts --bat experiments/results/bat_full_admissible.json --cold-start experiments/results/bat_cold_start_frontier_full.json --warm-start experiments/results/warm_start_suite.json --bridge experiments/results/supported_bridge.json --out-dir experiments/results
.venv/bin/python -m src.generate_artifact_manifest
```

These commands use the main outputs plus the included campaign-replay reference
JSON. The category/hour figure generator writes its own summary JSON and PDF.
The general artifact generator also supports the optional synthetic diagnostics
below via `--synthetic`; missing optional inputs are left out of the generated
summary. It writes CSV tables, PDF figures, a Markdown report, and local LaTeX
table fragments. The fragments are excluded from the code release.

The manifest records available output hashes and dependency versions. Changing
input or output paths requires passing the corresponding paths to the figure
generator; use `--help` to list them.

## Supplementary analyses

The implementation also retains the chronological BAT replay used to assess
benchmark limitations against historical stationary reuse:

```bash
python3 -m src.bat_cold_start_runner --jobs 2 --timeout 180 --json-name bat_cold_start_frontier_full.json --md-name bat_cold_start_frontier_full.md
```

This uses all campaigns and statistics by default. Do not use campaign or row
caps when reproducing the full-data results. Per-period budgets use declared
campaign start/end durations rather than observed future outcomes.

Additional synthetic calibration and identification diagnostics remain
available in the source directory:

```bash
python3 -m src.run_full_synthetic --n 5000
```

## Regression checks

```bash
python3 -m tests.test_cold_start_frontier
python3 -m tests.test_supported_bridge
```

These checks need no external data and do not replace the main experiment runs.
