# Experiments

Code for the synthetic, public BAT, and semi-synthetic experiments in
**Cold-Start Constrained Autobidding via Implied-Dual Calibration**.

## Quick start

From the repository root, run:

```bash
python3 experiments/run_synthetic_smoke.py --out experiments/results/synthetic_smoke.json
```

This small synthetic check needs only Python's standard library and no dataset
download. It writes calibration, auction-response, and initialization metrics
to `experiments/results/synthetic_smoke.json`. It checks the implementation;
it does not reproduce the full paper results.

For full experiment commands, data access, and figure generation, see
[Reproducing the experiments](REPRODUCING.md). The
[evaluation protocol](ACCEPTANCE_PROTOCOL.md) specifies splits, baselines,
endpoints, and confidence intervals.

## Which scripts should I use?

Choose the runner for the experiment you want to reproduce:

| Script | Purpose |
| --- | --- |
| `run_synthetic_smoke.py` | Small, data-free implementation check. |
| `run_full_synthetic.py` | Synthetic calibration and identification experiments. |
| `run_warm_start_suite.py` | Controlled controller/initialization comparisons. |
| `run_supported_bridge.py` | BAT-shaped semi-synthetic experiments with known bid maps. |
| `bat_runner.py` | Public BAT calibration diagnostics. |
| `bat_cold_start_runner.py` | Chronological BAT campaign replay against historical stationary reuse. |

The runners share `experiment_utils.py`; BAT replay also imports `bat_runner.py`.
Keep these dependencies even when running only one experiment.
`generate_paper_artifacts.py` produces tables and figures and imports
`run_full_synthetic.py`. `generate_artifact_manifest.py` records file hashes and
environment details. The two `test_*.py` files check replay and bridge logic.
`generate_bat_category_hour_surfaces.py` generates the paper's category/hour
dual-surface figure from the BAT CSVs.

The remaining tools are optional: `bat_download_check.py` checks dataset access,
`bat_schema_sample.py` inspects a small CSV sample, `public_rtb_check.py` checks
availability of supplementary RTB sources, and `run_all.py` orchestrates bounded
smoke runs. They are not additional steps required for each experiment.

## Included results

`results/` contains selected result JSON, reports, CSV tables, and figures from
the reported experiments. Read `results/paper_artifacts.md` for the evidence
summary. Raw BAT data are fetched separately; local caches and newly generated
outputs are ignored by Git.
