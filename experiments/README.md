# Reviewer-Grade Experiment Scaffold

This directory contains the reproducible workbench for the implied-dual and
response-surface paper. The scaffold is split into two layers:

- `run_synthetic_smoke.py` is dependency-free and validates the core mechanics:
  truthful recovery, first-price response correction, hybrid composite response,
  rank-one curvature, multi-constraint weak identification, pacing
  initialization, and cold-start shrinkage.
- `bat_download_check.py` is the public-data entry point. It checks the public
  BAT Hugging Face dataset first and records whether the four expected subsets
  (`fpa_campaigns`, `fpa_stats`, `vcg_campaigns`, `vcg_stats`) are available.
- `bat_runner.py` is the standard-library BAT calibration runner. It streams
  the public Hugging Face CSVs, joins campaign metadata when available, computes
  flat and contextual two-feature OLS diagnostics, and writes JSON plus Markdown
  summaries under `experiments/results/`.
- `run_full_synthetic.py` is the full dependency-free synthetic/semi-synthetic
  suite covering Q01-Q10: monotonicity, rank-one curvature, response-model
  choice, dual-smile decomposition, generated regressors, censoring, hybrid
  identifiability, multi-constraint weak identification, pacing initialization,
  and cold-start transfer.
- `run_warm_start_suite.py` is the controlled `controller x initialization x
  scenario` suite for the warm-start claim.  It reports matched, drift,
  mismatch, FPA response-aware, and hybrid initialization trajectories.
- `bat_cold_start_runner.py` is the chronological BAT frontier replay.  It
  selects policy scalars on validation, evaluates once on held-out campaigns,
  uses declared `campaign_start`/`campaign_end` duration for budget scheduling,
  and reports campaign-clustered bootstrap intervals.
- `run_supported_bridge.py` is the BAT-shaped known-transform bridge.  It uses
  the frozen scenario registry in `ACCEPTANCE_PROTOCOL.md` plus a 3x3
  shift/response sensitivity grid.
- `generate_artifact_manifest.py` writes exact commands, dependency versions,
  row-count summaries, and output hashes for the anonymized artifact bundle.
- `run_all.py` orchestrates the available smoke, full synthetic, BAT, and public
  RTB status checks and writes a provenance manifest.

## Quick Start

```bash
python3 experiments/run_synthetic_smoke.py --out experiments/results/synthetic_smoke.json
python3 experiments/bat_download_check.py --out experiments/results/bat_access.json
python3 experiments/run_full_synthetic.py --out experiments/results/full_synthetic.json \
  --report experiments/results/full_synthetic_report.md
python3 experiments/run_warm_start_suite.py --n 5000 --horizon 100 --seeds 10 \
  --out experiments/results/warm_start_suite.json \
  --report experiments/results/warm_start_suite.md
python3 experiments/bat_runner.py --max-rows 2000 --min-category-rows 50 \
  --json-name bat_calibration_smoke.json --md-name bat_calibration_smoke.md
python3 experiments/bat_cold_start_runner.py --jobs 2 \
  --json-name bat_cold_start_frontier_full.json --md-name bat_cold_start_frontier_full.md
python3 experiments/run_supported_bridge.py --seeds 100 --contexts 60 \
  --out experiments/results/supported_bridge.json \
  --report experiments/results/supported_bridge.md
python3 experiments/generate_paper_artifacts.py \
  --bat experiments/results/bat_full_admissible.json \
  --cold-start experiments/results/bat_cold_start_frontier_full.json \
  --bridge experiments/results/supported_bridge.json \
  --out-dir experiments/results
python3 experiments/generate_artifact_manifest.py
python3 experiments/public_rtb_check.py --out experiments/results/public_rtb_check.json
python3 experiments/run_all.py --synthetic-n 5000 --bat-max-rows 20000
```

For full BAT experiments, create a local environment and install the optional
dependencies:

```bash
python3 -m venv experiments/.venv
experiments/.venv/bin/pip install -r experiments/requirements.txt
```

Large data and generated outputs belong in `experiments/data/` and
`experiments/results/`; both are ignored by git.

`bat_runner.py` does not require these optional dependencies. By default it uses
a bounded `--sample-rows 100000` stats stream; pass `--full` to stream the full
BAT stats files, or `--max-rows N` for smoke tests.  `bat_cold_start_runner.py`
can use `--jobs 2` to evaluate VCG and FPA in separate processes when both
local CSVs are available.

## Artifact Bundle Hygiene

For anonymous review, package only the manuscript-facing reproducibility files:
the scripts in this directory, `ACCEPTANCE_PROTOCOL.md`, generated CSV/Markdown
tables and figures used by the paper, `artifact_manifest.json`, and concise
result reports. Exclude manuscript and generated table `.tex` sources,
bibliography files, LaTeX templates and template archives, local notes,
reviewer work logs, `AGENTS.md`, draft
supplements not referenced by the main submission, machine-specific paths, and
raw cached datasets that can be redownloaded from public sources.

## Roadmap

The smoke script intentionally reports the same quantities used in the paper:
transformed calibration loss (TCL), market-state recovery error (MSRE),
monotonicity margins for `phi_z(b)`, rank-one curvature ratios, weak-design
condition numbers, initialization regret, and cold-start risk ratios.

The heavy runs should extend these routines rather than replace them:

- BAT VCG: flat IDVC versus contextual implied duals.
- BAT FPA: raw affine regression versus response-IDVC.
- Semi-synthetic BAT hybrid: known rule versus unknown composite response.
- Public RTB/iPinYou: censored-observability stress test only.

Current generated summaries:

- `experiments/results/full_synthetic_report.md`
- `experiments/results/bat_runner.md`
- `experiments/results/bat_cold_start_frontier_full.md`
- `experiments/results/supported_bridge.md`
- `experiments/results/artifact_manifest.json`
- `experiments/results/public_rtb_check.md`
- `experiments/results/paper_integration_notes.md`
