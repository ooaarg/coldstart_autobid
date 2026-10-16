# Main experiments

These three entry points reproduce the main experimental cases in the final
paper. Run them from the repository root; their defaults use the full paper
settings.

| Entry point | Default configuration | Output in `results/` |
| --- | --- | --- |
| `python3 -m experiments.bat_calibration` | Full VCG and FPA BAT calibration; admissible dual fits. | `bat_full_admissible.json`, `bat_full_admissible.md` |
| `python3 -m experiments.supported_bridge` | 100 seeds, 60 contexts, all declared scenarios and the sensitivity grid. | `supported_bridge.json`, `supported_bridge.md` |
| `python3 -m experiments.warm_start` | 100 seeds, 100 controller updates, matched/shifted/FPA/hybrid/mismatch settings. | `warm_start_suite.json`, `warm_start_suite.md` |

The bridge and warm-start experiments need only Python's standard library and
no external dataset. BAT streams public CSVs unless local files are available.
Use `--help` with an entry point to inspect input and output options.

Implementations and plotting code live in [`src/`](../src/); the entry points
only select the paper configuration. See the
[reproduction guide](../docs/reproducing.md) for data paths, figure generation,
and supplementary experiments, and the
[evaluation protocol](../docs/evaluation.md) for baselines and success criteria.

Selected reference results, tables, and figures are included in `results/`.
New runs overwrite matching output names by default; use `--out`/`--report`
for bridge and warm start, or `--out-dir` for BAT, to keep a separate run.
