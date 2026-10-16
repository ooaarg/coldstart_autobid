# BAT Calibration Run

- Generated UTC: `2026-05-19T17:14:58.168802+00:00`
- Mode: `full`
- Stats row limit: `None`
- Dataset: [AvitoTech/BAT](https://huggingface.co/datasets/AvitoTech/BAT/resolve/main)

## Admissible And Proxy Calibration

| auction | rows | usable | proxy s | proxy alpha | proxy TCL | adm. s | adm. alpha | adm. TCL | ctx proxy TCL | ctx adm. TCL | ctx adm. delta | Gram cond. | ctx bins | campaign matches |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vcg | 23862060 | 5723132 | -0.0871825 | 0.0785388 | 46.0596 | 1e-08 | 0.0686086 | 46.1976 | 41.3365 | 42.1121 | 0.775591 | 13.8495 | 57 | 23862060 |
| fpa | 9468695 | 9468695 | -1270.31 | 19.5841 | 6599.15 | 264.049 | 1 | 7182.63 | 6109.29 | 7108.14 | 998.855 | 35665 | 51 | 9468695 |

Features are `v = CTRPredicts * CRPredicts` and `contact_price_bin * mu`, with `mu = CTRPredicts`.
`proxy` columns are unconstrained affine least squares and are not called implied-dual fits.
`adm.` columns solve the same squared loss under `s >= 1e-8` and `0 <= alpha <= 1`.
Response is the declared public-BAT proxy `AuctionWinBidSurplus / max(AuctionCount, 1)` with `contact_price_bin` fallback when surplus is unavailable; it is not a raw winning-price target.
Held-out baselines use period-block split `period // 3600 mod 5`, with fold 4 held out.

## Admissibility Diagnostics

| auction | s<0 bins | alpha<0 bins | alpha>1 bins | active s-min bins | active alpha=0 bins | active alpha=1 bins | weak cond. bins | singular bins |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vcg | 55 | 0 | 1 | 55 | 0 | 1 | 0 | 0 |
| fpa | 51 | 0 | 51 | 0 | 0 | 51 | 17 | 0 |

## Schema And Availability

### VCG

- Required stats columns missing: `[]`
- Optional stats columns missing: `['platform_p', 'x_platfrom_num']`
- Campaign metadata available: `True`
- Truncated stats stream: `False`

### FPA

- Required stats columns missing: `[]`
- Optional stats columns missing: `[]`
- Campaign metadata available: `True`
- Truncated stats stream: `False`

## Held-Out Baselines

| auction | model | test rows | test TCL | context SE | blocks |
| --- | --- | --- | --- | --- | --- |
| vcg | global_mean | 1132730 | 44.3812 | 13.2975 | 57 |
| vcg | category_price_mean | 1132730 | 31.4021 | 71.1948 | 5371 |
| vcg | flat_unconstrained_affine_proxy | 1132730 | 47.1729 | 14.1554 | 57 |
| vcg | flat_admissible_idvc | 1132730 | 47.4201 | 14.1742 | 57 |
| vcg | contextual_unconstrained_affine_proxy | 1132730 | 47.2155 | 19.3623 | 57 |
| vcg | contextual_admissible_idvc | 1132730 | 43.2917 | 12.4999 | 57 |
| fpa | global_mean | 1901836 | 6305.72 | 922.72 | 51 |
| fpa | category_price_mean | 1901836 | 3983.17 | 48854.6 | 3982 |
| fpa | flat_unconstrained_affine_proxy | 1901836 | 6192.53 | 892.488 | 51 |
| fpa | flat_admissible_idvc | 1901836 | 6765.23 | 967.578 | 51 |
| fpa | contextual_unconstrained_affine_proxy | 1901836 | 5718.03 | 853.721 | 51 |
| fpa | contextual_admissible_idvc | 1901836 | 6696.68 | 961.794 | 51 |
| fpa | fpa_response_proxy | 1901836 | 5658.82 | NA | None |

## FPA Response Proxy Diagnostics

- Proxy fit TCL MSE: `6012.74`
- Proxy features: `AuctionWinBidSurplus_total + contact_price_bin`
- Proxy target: `AuctionWinBidSurplus / max(AuctionCount, 1)`
- Mean `y / contact_price_bin`: `0.437242`
- Median `y / contact_price_bin`: `0.144289`
- Ratio sample count: `9452817`

Proxy-only diagnostic: public BAT exposes realized surplus and contact-price bins, not the full first-price response curve. The proxy fit uses total win-bid surplus and contact-price-bin covariates to diagnose response dependence; it is not a structural response decomposition.

## Data Request Status

No private data was required for this run. Public BAT CSVs were used first.
Private/platform logs would only be needed for uncensored thresholds, exact payment-rule metadata, or production regime labels.
