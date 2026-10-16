# Warm-Start Suite

- Seeds: `100`
- Horizon: `100` synthetic controller updates
- Controller: one stable residual controller shared by all initializations.
- Guard: abstain when mismatch z-score exceeds `1.65`; otherwise shrink with `n/(n+6)`.

## Main Metrics

| Scenario | Initialization | Early-AUC | Lift vs hist. | TTT | Early violation | Oracle gap | Abstain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| abrupt_shift | contextual_idvc | 49.160 | 0.015 | 0.0 | 0.009 | 0.002 | 0.00 |
| abrupt_shift | historical_stationary | 48.418 | 0.000 | 5.0 | 0.266 | 0.010 | 0.00 |
| abrupt_shift | oracle_init | 49.393 | 0.020 | 0.0 | 0.000 | 0.000 | 0.00 |
| abrupt_shift | response_idvc | 49.160 | 0.015 | 0.0 | 0.009 | 0.002 | 0.00 |
| abrupt_shift | shrunk_idvc | 49.176 | 0.016 | 0.0 | 0.007 | 0.002 | 0.00 |
| fpa_blind_vs_response | contextual_idvc | 48.598 | -0.016 | 7.0 | 0.452 | 0.013 | 0.00 |
| fpa_blind_vs_response | historical_stationary | 49.390 | 0.000 | 2.0 | 0.040 | 0.004 | 0.00 |
| fpa_blind_vs_response | oracle_init | 49.815 | 0.009 | 0.0 | 0.000 | 0.000 | 0.00 |
| fpa_blind_vs_response | response_idvc | 49.697 | 0.006 | 0.0 | 0.008 | 0.001 | 0.00 |
| fpa_blind_vs_response | shrunk_idvc | 48.683 | -0.014 | 7.0 | 0.399 | 0.012 | 0.00 |
| hybrid_lambda_grid | contextual_idvc | 49.071 | -0.002 | 4.0 | 0.096 | 0.005 | 0.00 |
| hybrid_lambda_grid | historical_stationary | 49.179 | 0.000 | 2.0 | 0.039 | 0.004 | 0.00 |
| hybrid_lambda_grid | oracle_init | 49.586 | 0.008 | 0.0 | 0.000 | 0.000 | 0.00 |
| hybrid_lambda_grid | response_idvc | 49.449 | 0.005 | 0.0 | 0.008 | 0.001 | 0.00 |
| hybrid_lambda_grid | shrunk_idvc | 49.065 | -0.002 | 4.0 | 0.092 | 0.006 | 0.00 |
| matched_stationary | contextual_idvc | 50.374 | 0.011 | 0.0 | 0.001 | 0.001 | 0.00 |
| matched_stationary | historical_stationary | 49.803 | 0.000 | 4.0 | 0.131 | 0.007 | 0.00 |
| matched_stationary | oracle_init | 50.500 | 0.014 | 0.0 | 0.000 | 0.000 | 0.00 |
| matched_stationary | response_idvc | 50.374 | 0.011 | 0.0 | 0.001 | 0.001 | 0.00 |
| matched_stationary | shrunk_idvc | 50.366 | 0.011 | 0.0 | 0.000 | 0.001 | 0.00 |
| mismatched_prior | contextual_idvc | 47.644 | 0.001 | 10.0 | 1.259 | 0.026 | 0.00 |
| mismatched_prior | historical_stationary | 47.583 | 0.000 | 10.0 | 1.298 | 0.027 | 0.00 |
| mismatched_prior | oracle_init | 50.157 | 0.054 | 0.0 | 0.000 | 0.000 | 0.00 |
| mismatched_prior | response_idvc | 47.644 | 0.001 | 10.0 | 1.259 | 0.026 | 0.00 |
| mismatched_prior | shrunk_idvc | 49.773 | 0.046 | 1.0 | 0.039 | 0.004 | 1.00 |
| smooth_drift | contextual_idvc | 48.830 | 0.014 | 0.0 | 0.004 | 0.001 | 0.00 |
| smooth_drift | historical_stationary | 48.171 | 0.000 | 8.0 | 0.229 | 0.008 | 0.00 |
| smooth_drift | oracle_init | 48.901 | 0.015 | 0.0 | 0.000 | 0.000 | 0.00 |
| smooth_drift | response_idvc | 48.830 | 0.014 | 0.0 | 0.004 | 0.001 | 0.00 |
| smooth_drift | shrunk_idvc | 48.791 | 0.013 | 0.0 | 0.005 | 0.001 | 0.00 |

## Negative Transfer Diagnostics

| Scenario | Negative-transfer rate |
| --- | ---: |
| abrupt_shift | 0.000 |
| fpa_blind_vs_response | 0.210 |
| hybrid_lambda_grid | 0.000 |
| matched_stationary | 0.000 |
| mismatched_prior | 1.000 |
| smooth_drift | 0.000 |

Overall guarded-transfer abstention accuracy: `1.000`.

These are controlled synthetic/semi-synthetic results. They support the warm-start mechanism and failure modes, not a public-BAT FPA deployment claim.
