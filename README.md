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

The code submission excludes manuscript LaTeX sources, the bibliography, ACM
templates, and local reviewer notes. These remain in the author's local working
directory. Table-generation scripts may create `.tex` fragments locally; those
generated files are excluded from version control and the submission ZIP.

## Quick start

The core synthetic checks use only the Python standard library:

```bash
python3 experiments/run_synthetic_smoke.py \
  --out experiments/results/synthetic_smoke.json
```

Run the complete available experiment pipeline with:

```bash
python3 experiments/run_all.py --synthetic-n 5000 --bat-max-rows 20000
```

Optional dependencies for full BAT experiments can be installed in a local
environment:

```bash
python3 -m venv experiments/.venv
experiments/.venv/bin/pip install -r experiments/requirements.txt
```

See [`experiments/README.md`](experiments/README.md) for individual commands,
outputs, and experiment details.

## Data and reproducibility

Large datasets, local caches, virtual environments, and generated experiment
outputs are excluded from version control. Public BAT data can be checked or
downloaded through the scripts documented in `experiments/README.md`. Main
results use chronological splits and keep final-test campaigns isolated from
model fitting and policy selection.
