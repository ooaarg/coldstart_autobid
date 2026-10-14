# Reproducing the experiments

Run all commands from the repository root. Synthetic, semi-synthetic, and BAT
runners use Python's standard library. Extra packages are needed only for
table and figure generation. The smoke checks have been verified with
Python 3.13.

## Synthetic and controlled experiments

Run each suite separately. The controlled warm-start results use 100 seeds;
the shorter quick-start smoke check is not a substitute for these runs.

```bash
python3 experiments/run_full_synthetic.py --n 5000 \
  --out experiments/results/full_synthetic.json \
  --report experiments/results/full_synthetic_report.md

python3 experiments/run_warm_start_suite.py --n 5000 --horizon 100 --seeds 100 \
  --out experiments/results/warm_start_suite.json \
  --report experiments/results/warm_start_suite.md

python3 experiments/run_supported_bridge.py --seeds 100 --contexts 60 \
  --out experiments/results/supported_bridge.json \
  --report experiments/results/supported_bridge.md
```

The bridge includes the declared sensitivity grid by default. Its known bid
maps are semi-synthetic; its results are reported separately from unchanged BAT.

## Public BAT experiments

The runners stream the public `AvitoTech/BAT` CSVs when local files are absent.
Full runs process millions of rows and need network access to the dataset.
Optionally check access first:

```bash
python3 experiments/bat_download_check.py --out experiments/results/bat_access.json
```

Reproduce the calibration diagnostics and the campaign replay with:

```bash
python3 experiments/bat_runner.py --full \
  --json-name bat_full_admissible.json --md-name bat_full_admissible.md

python3 experiments/bat_cold_start_runner.py --jobs 2 --timeout 180 \
  --json-name bat_cold_start_frontier_full.json \
  --md-name bat_cold_start_frontier_full.md
```

The runners use local CSVs automatically when present at
`experiments/data/bat/raw/{vcg,fpa}/{stats,campaigns}.csv`. Both BAT runners
also accept `--vcg-stats`, `--vcg-campaigns`, `--fpa-stats`, and
`--fpa-campaigns` to specify other files. Replay uses two processes when both
auctions have local files; remote streams run sequentially.

For a small calibration check, use `bat_runner.py --max-rows 2000` with
different output names. Replay limits `--max-campaigns` and `--max-stats-rows`
are also available. Capped runs are implementation checks, not the reported
full-data evidence. See the [evaluation protocol](ACCEPTANCE_PROTOCOL.md) for
the chronological split and locked historical comparator.

## Tables and figures

After generating the experiment outputs, install the plotting dependencies:

```bash
python3 -m venv experiments/.venv
experiments/.venv/bin/python -m pip install -r experiments/requirements.txt
```

Generate tables and figures with that environment:

```bash
experiments/.venv/bin/python experiments/generate_paper_artifacts.py \
  --bat experiments/results/bat_full_admissible.json \
  --cold-start experiments/results/bat_cold_start_frontier_full.json \
  --synthetic experiments/results/full_synthetic.json \
  --warm-start experiments/results/warm_start_suite.json \
  --bridge experiments/results/supported_bridge.json \
  --out-dir experiments/results

experiments/.venv/bin/python experiments/generate_bat_category_hour_surfaces.py

experiments/.venv/bin/python experiments/generate_artifact_manifest.py
```

The generator writes CSV tables, PDF figures, and `paper_artifacts.md`. It also
creates local LaTeX table fragments, which are excluded from the code release.
The category/hour figure script reads the local BAT CSVs at the paths above;
use its `--vcg-stats`, `--vcg-campaigns`, `--fpa-stats`, and `--fpa-campaigns`
options for other paths or URLs. It writes the category/hour surface summary
and `bat_selected_category_hour_dual_surfaces_clean.pdf`.
The manifest records available output hashes and package versions; missing
outputs are marked explicitly.

These commands overwrite matching output files. Use `--out`, `--report`,
`--json-name`, `--md-name`, or `--out-dir` to keep a separate run. An alternate
figure output directory must be paired with the corresponding input JSON paths.

## Tests and optional tools

The replay and bridge tests need no external data:

```bash
python3 experiments/test_cold_start_frontier.py
python3 experiments/test_supported_bridge.py
```

`run_all.py` combines bounded smoke runs and availability checks. It does not
reproduce all paper results or generate the figures. `bat_schema_sample.py` and
`public_rtb_check.py` are optional data-inspection tools; the latter checks source
availability rather than running an RTB experiment. Each script supports
`--help` for its command-line options.
