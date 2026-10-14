# Cold-Start Constrained Autobidding

Research code for **Cold-Start Constrained Autobidding via
Implied-Dual Calibration**.

When a new ad enters an existing auction market, its first bid must be chosen
before any ad-specific feedback is available. This project studies that
cold-start decision under budget and CPC-style constraints. The proposed method
reuses a compact, admissible implied-dual surface learned from related historical
contexts and converts it into bids for SPA/VCG, first-price, and supported hybrid
auction settings.

## Repository layout

- `cikm_implied_duals.pdf` — compiled CIKM 2026 manuscript.
- `experiments/` — reproducible synthetic, BAT, and semi-synthetic experiments.
- `experiments/ACCEPTANCE_PROTOCOL.md` — frozen evaluation protocol and success
  gates.

## Quick start

Run a small synthetic check from the repository root. No external packages or
dataset downloads are needed:

```bash
python3 experiments/run_synthetic_smoke.py \
  --out experiments/results/synthetic_smoke.json
```

The JSON output is written to `experiments/results/synthetic_smoke.json`.
See [the script guide](experiments/README.md) to choose an experiment and
[the reproduction guide](experiments/REPRODUCING.md) for full paper runs and
plotting dependencies.

## Data and reproducibility

Selected result files are included in `experiments/results/`. Raw datasets,
local caches, virtual environments, and newly generated outputs are ignored by
Git. Public BAT data are accessed by the documented runners. Main
results use chronological splits and keep final-test campaigns isolated from
model fitting and policy selection.

## Citation

Andrey Pudovikov, Aleksandr Katrutsa, Egor Samosvat, and Yuriy Dorn.
**Cold-Start Constrained Autobidding via Implied-Dual Calibration.** CIKM 2026.
[DOI: 10.1145/3799682.3841153](https://doi.org/10.1145/3799682.3841153).

Machine-readable citation metadata are provided in [CITATION.cff](CITATION.cff).
