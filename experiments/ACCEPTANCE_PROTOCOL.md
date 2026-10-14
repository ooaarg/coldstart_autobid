# Evaluation Protocol

This document records the evaluation settings fixed before the reported
decision-evidence experiments: endpoints, data splits, baseline selection,
confidence intervals, and success criteria.

## Primary Endpoint

The primary endpoint is campaign-clustered total contact lift for fixed-horizon
early-AUC. For each policy and campaign, compute cumulative
`AuctionContactsSurplus` at the first `1, 3, 6, 12, 24` observed cold-start
periods, using all available periods when the requested horizon exceeds the
campaign's observed prefix. The campaign-level early-AUC is the unweighted mean
of those five cumulative values. The reported primary contrast is the
campaign-clustered paired bootstrap lift in total early-AUC.

## Secondary Endpoints

- Budget-violation AUC over the same fixed horizons.
- Cost per contact over the same fixed horizons.
- Budget utilization over the same fixed horizons.
- Time-to-target and negative-transfer rate in controlled warm-start and
  BAT-shaped known-transform semi-synthetic bridge experiments.

## Splits And Tuning

- BAT campaigns are sorted by `campaign_start`.
- The first 70% are training campaigns.
- The next 10% are validation campaigns.
- The final 20% are test campaigns.
- No final-test campaign may influence model fitting, scalar selection,
  support-stratum definitions, or bridge-generation parameters.

## BAT Frontier

Each deployable policy is evaluated on validation campaigns with scalar grid
`0.50, 0.75, 1.00, 1.25, 1.50, 2.00, 3.00`.

For each policy, select the scalar that maximizes validation primary endpoint
subject to validation budget-violation AUC no worse than `1.05x` historical
stationary reuse at scale `1.00`. The primary comparator,
`historical_stationary_context_bin`, is locked at scale `1.00` for the
feasibility threshold and the final paired CI. If no scalar is feasible for a
non-comparator policy, report the selected infeasible scalar explicitly.

The selected scalar is then evaluated once on test campaigns. Paired confidence
intervals cluster by campaign with seed `20260522` and `1000` bootstrap
resamples.

## Primary Contrast And Multiplicity

The primary unchanged-BAT contrast is `shrunk_contextual_idvc` versus
`historical_stationary_context_bin`, both evaluated on the selected test replay
with the historical comparator fixed at scale `1.00`.

All other policies, auction-specific breakdowns, support strata, and secondary
endpoints are reported as diagnostic or exploratory. They are not used to claim
unchanged public-BAT decision lift.

The unchanged-BAT primary gate passes only if the lower 95% confidence bound for
contact lift is greater than zero and the upper 95% confidence bound for
budget-violation AUC difference is less than or equal to zero.

## Support Strata

Support strata are defined from training context rows:

- `low`: fewer than `500` rows.
- `medium`: `500` through `5000` rows.
- `high`: more than `5000` rows.
- `weak`: Gram condition missing or greater than `1e5`.

All support strata are reported, including unfavorable ones.

## Supported Bridge Success Gate

The BAT-shaped known-transform semi-synthetic bridge is positive evidence only if
guarded IDVC beats historical stationary reuse on the primary endpoint with
lower 95% confidence bound above zero and no larger matched constraint
violation. Response-aware IDVC is a secondary bridge contrast unless guarded
IDVC is inapplicable in the bridge configuration.

If unchanged BAT and the supported bridge both fail this gate, the evidence
supports calibration diagnostics and controlled mechanisms rather than a
decision-lift claim.

### Frozen Bridge Scenario Registry

The bridge uses `experiments/run_supported_bridge.py` with seed `20260522`,
`100` seeds, `60` contexts, horizons `1,3,6,12,24`, and paired cluster
bootstrap with `1000` resamples. Primary policy is `guarded_idvc`; comparator is
`historical_stationary`. The guard abstains when
`abs(contextual_idvc - global_flat_idvc) / 0.16 > 1.65`.

| scenario | role | history_shift | global_shift | context_shift | response_factor | target_level_shift | abrupt_after |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| matched | primary | -0.10 | -0.070 | 0.00 | 0.00 | 0.00 | 0.00 |
| fpa_response_bias | primary | -0.10 | -0.070 | 0.00 | 1.00 | 0.00 | 0.00 |
| hybrid | primary | -0.10 | -0.070 | 0.00 | 0.55 | 0.00 | 0.00 |
| abrupt_shift | primary | -0.14 | -0.070 | 0.00 | 0.00 | 0.05 | 0.13 |
| null_stationary | negative_control | 0.00 | -0.020 | 0.00 | 0.00 | 0.00 | 0.00 |
| unsupported_mismatch | negative_control | -0.060 | -0.060 | -0.55 | 0.00 | 0.30 | 0.00 |

Sensitivity is predeclared over shift and response multipliers
`0.85,1.00,1.15`. The bridge remains positive evidence only if every cell in
this 3x3 grid passes the same primary gate and negative controls.

Exact final command:

```sh
python3 experiments/run_supported_bridge.py --seeds 100 --contexts 60 --out experiments/results/supported_bridge.json --report experiments/results/supported_bridge.md
```

## Full-data Runs

Reported BAT replay runs use full BAT with `--max-campaigns` unset and
`--max-stats-rows` unset. Capped runs are smoke tests only and are not
evidentiary.

The per-period budget rule uses the declared `campaign_start` and
`campaign_end` fields in the BAT campaign table to compute hourly planned
duration. Test-period outcome counts are not used for budget scheduling.

Exact final BAT frontier command:

```sh
python3 experiments/bat_cold_start_runner.py --jobs 2 --json-name bat_cold_start_frontier_full.json --md-name bat_cold_start_frontier_full.md --timeout 180
```
