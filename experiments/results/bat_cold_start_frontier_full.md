# BAT Campaign Cold-Start Replay

- Generated UTC: `2026-05-22T20:59:40.928352+00:00`
- Dataset: [AvitoTech/BAT](https://huggingface.co/datasets/AvitoTech/BAT/resolve/main)
- Split: campaigns sorted by `campaign_start`; first 70% train, next 10% validation, final 20% test.
- Cold-start horizons: first 1, 3, 6, 12, and 24 observed periods, plus first 5%, 10%, and 20% of observed campaign lifetime.
- Spend mapping: VCG uses cumulative `AuctionWinBidSurplus`; FPA uses `1.2 ** contact_price_bin` times cumulative contacts.
- Budget mapping: per-period budget uses declared `campaign_start`/`campaign_end` duration from the BAT campaign table; no test-period outcome count is used for budget scheduling.
- BAT surplus fields are simulator-style public proxy outcomes, not raw winning-price or raw payment logs.
- `oracle_ex_post_feasible_bin` is a diagnostic upper reference chosen from test-period proxy surplus curves, not a deployable baseline.

## Decision Metrics

| auction | horizon | policy | campaigns | contacts | clicks | spend | budget viol. | util. | CPC | contact lift |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPA | first_period | global_feasible_bin | 2060 | 201.713 | 2770.6 | 23999 | 13621.4 | 0.608919 | 118.976 | 0.0395843 |
| FPA | first_period | historical_stationary_context_bin | 2060 | 194.033 | 2760.45 | 32617.8 | 20776.6 | 0.827602 | 168.105 | 0 |
| FPA | first_period | flat_admissible_idvc | 2060 | 68.034 | 578.574 | 975.546 | 344.757 | 0.0247522 | 14.3391 | -0.649368 |
| FPA | first_period | contextual_admissible_idvc | 2060 | 67.7337 | 714.781 | 1096.29 | 380.405 | 0.0278159 | 16.1853 | -0.650916 |
| FPA | first_period | shrunk_contextual_idvc | 2060 | 67.7337 | 714.781 | 1096.29 | 380.405 | 0.0278159 | 16.1853 | -0.650916 |
| FPA | first_period | oracle_ex_post_feasible_bin | 2060 | 178.316 | 2662.56 | 43034.7 | 14790.9 | 1.09191 | 241.339 | -0.0809981 |
| FPA | first_3 | global_feasible_bin | 2060 | 781.852 | 10936.2 | 94658.7 | 57990.3 | 0.800582 | 121.07 | 0.0264432 |
| FPA | first_3 | historical_stationary_context_bin | 2060 | 761.71 | 11005.1 | 131576 | 89629.6 | 1.11281 | 172.738 | 0 |
| FPA | first_3 | flat_admissible_idvc | 2060 | 263.988 | 2182.73 | 2201.88 | 623.386 | 0.0186225 | 8.34083 | -0.653427 |
| FPA | first_3 | contextual_admissible_idvc | 2060 | 273.095 | 2908.25 | 3858.64 | 1866.23 | 0.0326347 | 14.1293 | -0.641471 |
| FPA | first_3 | shrunk_contextual_idvc | 2060 | 271.915 | 2903.89 | 2903.11 | 909.932 | 0.0245533 | 10.6766 | -0.643021 |
| FPA | first_3 | oracle_ex_post_feasible_bin | 2060 | 669.415 | 10073.2 | 145554 | 60479.4 | 1.23103 | 217.434 | -0.121167 |
| FPA | first_6 | global_feasible_bin | 2060 | 1407.17 | 19287.9 | 171491 | 102150 | 0.725199 | 121.869 | 0.0277585 |
| FPA | first_6 | historical_stationary_context_bin | 2060 | 1369.17 | 19336.6 | 228220 | 148212 | 0.965094 | 166.685 | 0 |
| FPA | first_6 | flat_admissible_idvc | 2060 | 524.35 | 4348.04 | 4884.37 | 1507.06 | 0.0206549 | 9.31509 | -0.61703 |
| FPA | first_6 | contextual_admissible_idvc | 2060 | 558.048 | 5830.17 | 9692.32 | 5401.33 | 0.0409867 | 17.3683 | -0.592418 |
| FPA | first_6 | shrunk_contextual_idvc | 2060 | 556.825 | 5824.98 | 8728.15 | 4445.03 | 0.0369095 | 15.6749 | -0.593312 |
| FPA | first_6 | oracle_ex_post_feasible_bin | 2060 | 1220.91 | 18118 | 352956 | 183066 | 1.49258 | 289.094 | -0.108286 |
| FPA | first_12 | global_feasible_bin | 2060 | 2226.3 | 29898.1 | 271696 | 153906 | 0.574471 | 122.039 | 0.0309686 |
| FPA | first_12 | historical_stationary_context_bin | 2060 | 2159.43 | 29845 | 353699 | 215608 | 0.747858 | 163.793 | 0 |
| FPA | first_12 | flat_admissible_idvc | 2060 | 922.492 | 7818.64 | 13751.6 | 4828.25 | 0.0290762 | 14.907 | -0.572807 |
| FPA | first_12 | contextual_admissible_idvc | 2060 | 1000.26 | 10270.5 | 24429.7 | 13809.2 | 0.051654 | 24.4233 | -0.536793 |
| FPA | first_12 | shrunk_contextual_idvc | 2060 | 996.172 | 10254.4 | 23180.7 | 12575.4 | 0.0490131 | 23.2698 | -0.538687 |
| FPA | first_12 | oracle_ex_post_feasible_bin | 2060 | 1989.38 | 29485.3 | 1.13529e+06 | 796042 | 2.40044 | 570.673 | -0.0787463 |
| FPA | first_24 | global_feasible_bin | 2060 | 3535.82 | 47222.6 | 442402 | 241295 | 0.469031 | 125.12 | 0.0290676 |
| FPA | first_24 | historical_stationary_context_bin | 2060 | 3435.94 | 47078.8 | 582763 | 342115 | 0.617841 | 169.608 | 0 |
| FPA | first_24 | flat_admissible_idvc | 2060 | 1604 | 14151.2 | 41489.2 | 17952.4 | 0.0439865 | 25.8662 | -0.533172 |
| FPA | first_24 | contextual_admissible_idvc | 2060 | 1733.67 | 18387.2 | 58215.4 | 31681.3 | 0.0617194 | 33.5792 | -0.49543 |
| FPA | first_24 | shrunk_contextual_idvc | 2060 | 1729.48 | 18368.7 | 56951.4 | 30447.4 | 0.0603794 | 32.9299 | -0.496652 |
| FPA | first_24 | oracle_ex_post_feasible_bin | 2060 | 3265.11 | 49189.9 | 2.63398e+06 | 1.95571e+06 | 2.79253 | 806.706 | -0.0497195 |
| FPA | first_5pct_lifetime | global_feasible_bin | 2060 | 527.785 | 7549.44 | 63460 | 38733.7 | 0.782035 | 120.238 | 0.0304004 |
| FPA | first_5pct_lifetime | historical_stationary_context_bin | 2060 | 512.213 | 7569.42 | 89016 | 60377.7 | 1.09697 | 173.787 | 0 |
| FPA | first_5pct_lifetime | flat_admissible_idvc | 2060 | 172.885 | 1483.78 | 1578.1 | 475.324 | 0.0194473 | 9.12802 | -0.662474 |
| FPA | first_5pct_lifetime | contextual_admissible_idvc | 2060 | 179.165 | 1985.34 | 3127.28 | 1706.79 | 0.0385384 | 17.4547 | -0.650213 |
| FPA | first_5pct_lifetime | shrunk_contextual_idvc | 2060 | 177.848 | 1980.35 | 2094.75 | 673.514 | 0.0258142 | 11.7783 | -0.652784 |
| FPA | first_5pct_lifetime | oracle_ex_post_feasible_bin | 2060 | 452.127 | 6974.77 | 85426.5 | 27128.7 | 1.05273 | 188.943 | -0.117307 |
| FPA | first_10pct_lifetime | global_feasible_bin | 2060 | 805.62 | 11598.3 | 97205.9 | 59288.3 | 0.786537 | 120.66 | 0.0277219 |
| FPA | first_10pct_lifetime | historical_stationary_context_bin | 2060 | 783.89 | 11661.7 | 136956 | 93091.6 | 1.10817 | 174.713 | 0 |
| FPA | first_10pct_lifetime | flat_admissible_idvc | 2060 | 273.254 | 2343.43 | 2263.45 | 633.12 | 0.0183146 | 8.28329 | -0.651412 |
| FPA | first_10pct_lifetime | contextual_admissible_idvc | 2060 | 284.127 | 3175.6 | 3985.06 | 1870.97 | 0.0322449 | 14.0256 | -0.637542 |
| FPA | first_10pct_lifetime | shrunk_contextual_idvc | 2060 | 282.947 | 3171.23 | 3029.53 | 914.662 | 0.0245133 | 10.707 | -0.639047 |
| FPA | first_10pct_lifetime | oracle_ex_post_feasible_bin | 2060 | 690.34 | 10717.8 | 170476 | 81810.3 | 1.3794 | 246.944 | -0.11934 |
| FPA | first_20pct_lifetime | global_feasible_bin | 2060 | 1272.06 | 18021.8 | 154346 | 92719.9 | 0.739169 | 121.336 | 0.0308526 |
| FPA | first_20pct_lifetime | historical_stationary_context_bin | 2060 | 1233.99 | 18033.5 | 209476 | 137544 | 1.00319 | 169.756 | 0 |
| FPA | first_20pct_lifetime | flat_admissible_idvc | 2060 | 462.249 | 3979.13 | 4121.24 | 1212.09 | 0.0197368 | 8.91564 | -0.625403 |
| FPA | first_20pct_lifetime | contextual_admissible_idvc | 2060 | 491.053 | 5386.24 | 7541.2 | 3718.49 | 0.036115 | 15.3572 | -0.60206 |
| FPA | first_20pct_lifetime | shrunk_contextual_idvc | 2060 | 489.83 | 5381 | 6577.13 | 2762.19 | 0.031498 | 13.4274 | -0.603051 |
| FPA | first_20pct_lifetime | oracle_ex_post_feasible_bin | 2060 | 1094.5 | 16785.6 | 308834 | 158987 | 1.47901 | 282.169 | -0.113038 |
| VCG | first_period | global_feasible_bin | 20672 | 1143.79 | 30038.7 | 1.46842e+06 | 1.44068e+06 | 30.1836 | 1283.82 | 0.0505884 |
| VCG | first_period | historical_stationary_context_bin | 20672 | 1088.71 | 28762.9 | 1.46792e+06 | 1.44022e+06 | 30.1734 | 1348.31 | 0 |
| VCG | first_period | flat_admissible_idvc | 20672 | 1107.48 | 28725.4 | 1.47192e+06 | 1.44427e+06 | 30.2556 | 1329.06 | 0.0172435 |
| VCG | first_period | contextual_admissible_idvc | 20672 | 1128.68 | 28825.1 | 1.48805e+06 | 1.46023e+06 | 30.5872 | 1318.4 | 0.0367103 |
| VCG | first_period | shrunk_contextual_idvc | 20672 | 1128.21 | 28821.7 | 1.48758e+06 | 1.45976e+06 | 30.5775 | 1318.53 | 0.0362831 |
| VCG | first_period | oracle_ex_post_feasible_bin | 20672 | 2543.51 | 64593.1 | 7.23236e+06 | 7.19809e+06 | 148.663 | 2843.45 | 1.33626 |
| VCG | first_3 | global_feasible_bin | 20672 | 2454.94 | 67226 | 2.60511e+06 | 2.52865e+06 | 18.3471 | 1061.17 | 0.0803505 |
| VCG | first_3 | historical_stationary_context_bin | 20672 | 2272.36 | 63177.8 | 2.60372e+06 | 2.52722e+06 | 18.3373 | 1145.82 | 0 |
| VCG | first_3 | flat_admissible_idvc | 20672 | 2336.32 | 63080.3 | 2.61619e+06 | 2.53997e+06 | 18.4252 | 1119.79 | 0.0281501 |
| VCG | first_3 | contextual_admissible_idvc | 20672 | 2389.59 | 63301.2 | 2.65992e+06 | 2.58317e+06 | 18.7331 | 1113.13 | 0.05159 |
| VCG | first_3 | shrunk_contextual_idvc | 20672 | 2389.64 | 63301.2 | 2.65982e+06 | 2.58306e+06 | 18.7324 | 1113.06 | 0.0516147 |
| VCG | first_3 | oracle_ex_post_feasible_bin | 20672 | 6291.08 | 161444 | 1.82251e+07 | 1.81277e+07 | 128.355 | 2896.98 | 1.76853 |
| VCG | first_6 | global_feasible_bin | 20672 | 3932.43 | 109042 | 3.50972e+06 | 3.37003e+06 | 12.8372 | 892.507 | 0.106518 |
| VCG | first_6 | historical_stationary_context_bin | 20672 | 3553.88 | 100497 | 3.5094e+06 | 3.36958e+06 | 12.8361 | 987.484 | 0 |
| VCG | first_6 | flat_admissible_idvc | 20672 | 3671.04 | 100313 | 3.53252e+06 | 3.3932e+06 | 12.9206 | 962.268 | 0.0329648 |
| VCG | first_6 | contextual_admissible_idvc | 20672 | 3775.92 | 100702 | 3.61836e+06 | 3.47797e+06 | 13.2346 | 958.272 | 0.062477 |
| VCG | first_6 | shrunk_contextual_idvc | 20672 | 3774.85 | 100697 | 3.61781e+06 | 3.47741e+06 | 13.2326 | 958.397 | 0.0621762 |
| VCG | first_6 | oracle_ex_post_feasible_bin | 20672 | 11308.7 | 290389 | 3.2522e+07 | 3.23387e+07 | 118.953 | 2875.85 | 2.18206 |
| VCG | first_12 | global_feasible_bin | 20672 | 5713.05 | 161303 | 4.47565e+06 | 4.24908e+06 | 9.75675 | 783.408 | 0.131021 |
| VCG | first_12 | historical_stationary_context_bin | 20672 | 5051.23 | 145762 | 4.47303e+06 | 4.24621e+06 | 9.75104 | 885.532 | 0 |
| VCG | first_12 | flat_admissible_idvc | 20672 | 5230.99 | 145428 | 4.51519e+06 | 4.28908e+06 | 9.84295 | 863.162 | 0.0355862 |
| VCG | first_12 | contextual_admissible_idvc | 20672 | 5411.34 | 146041 | 4.66126e+06 | 4.43341e+06 | 10.1614 | 861.388 | 0.0712905 |
| VCG | first_12 | shrunk_contextual_idvc | 20672 | 5410.14 | 146035 | 4.66061e+06 | 4.43275e+06 | 10.16 | 861.459 | 0.0710527 |
| VCG | first_12 | oracle_ex_post_feasible_bin | 20672 | 17366 | 451010 | 4.97542e+07 | 4.94496e+07 | 108.462 | 2865.03 | 2.43797 |
| VCG | first_24 | global_feasible_bin | 20672 | 6613.23 | 186292 | 5.01746e+06 | 4.74311e+06 | 8.98844 | 758.7 | 0.134904 |
| VCG | first_24 | historical_stationary_context_bin | 20672 | 5827.13 | 168072 | 5.01336e+06 | 4.73877e+06 | 8.9811 | 860.349 | 0 |
| VCG | first_24 | flat_admissible_idvc | 20672 | 6050.62 | 167767 | 5.06263e+06 | 4.78885e+06 | 9.06936 | 836.712 | 0.0383537 |
| VCG | first_24 | contextual_admissible_idvc | 20672 | 6259.47 | 168528 | 5.23764e+06 | 4.96178e+06 | 9.38287 | 836.754 | 0.0741941 |
| VCG | first_24 | shrunk_contextual_idvc | 20672 | 6257.85 | 168519 | 5.23654e+06 | 4.96069e+06 | 9.3809 | 836.795 | 0.0739167 |
| VCG | first_24 | oracle_ex_post_feasible_bin | 20672 | 20061.1 | 522675 | 5.78783e+07 | 5.75085e+07 | 103.685 | 2885.1 | 2.44271 |
| VCG | first_5pct_lifetime | global_feasible_bin | 20672 | 1234.72 | 33020 | 1.60102e+06 | 1.57128e+06 | 30.215 | 1296.66 | 0.0533219 |
| VCG | first_5pct_lifetime | historical_stationary_context_bin | 20672 | 1172.22 | 31579.1 | 1.60057e+06 | 1.57085e+06 | 30.2064 | 1365.42 | 0 |
| VCG | first_5pct_lifetime | flat_admissible_idvc | 20672 | 1194 | 31532 | 1.6048e+06 | 1.57517e+06 | 30.2863 | 1344.06 | 0.018579 |
| VCG | first_5pct_lifetime | contextual_admissible_idvc | 20672 | 1217.12 | 31638.5 | 1.62266e+06 | 1.59283e+06 | 30.6233 | 1333.19 | 0.0383072 |
| VCG | first_5pct_lifetime | shrunk_contextual_idvc | 20672 | 1216.66 | 31635.1 | 1.62218e+06 | 1.59236e+06 | 30.6144 | 1333.31 | 0.0379104 |
| VCG | first_5pct_lifetime | oracle_ex_post_feasible_bin | 20672 | 2784.88 | 72644.2 | 8.40647e+06 | 8.36947e+06 | 158.65 | 3018.61 | 1.37574 |
| VCG | first_10pct_lifetime | global_feasible_bin | 20672 | 1702.99 | 47391.9 | 2.04078e+06 | 2.00114e+06 | 27.7107 | 1198.35 | 0.054322 |
| VCG | first_10pct_lifetime | historical_stationary_context_bin | 20672 | 1615.25 | 45445.8 | 2.04039e+06 | 2.00076e+06 | 27.7053 | 1263.2 | 0 |
| VCG | first_10pct_lifetime | flat_admissible_idvc | 20672 | 1648.98 | 45345.8 | 2.04679e+06 | 2.00732e+06 | 27.7922 | 1241.24 | 0.0208843 |
| VCG | first_10pct_lifetime | contextual_admissible_idvc | 20672 | 1680.09 | 45496.8 | 2.07192e+06 | 2.03223e+06 | 28.1335 | 1233.22 | 0.0401389 |
| VCG | first_10pct_lifetime | shrunk_contextual_idvc | 20672 | 1679.58 | 45493.2 | 2.07142e+06 | 2.03173e+06 | 28.1267 | 1233.3 | 0.0398248 |
| VCG | first_10pct_lifetime | oracle_ex_post_feasible_bin | 20672 | 3921.89 | 105656 | 1.20478e+07 | 1.19975e+07 | 163.591 | 3071.94 | 1.42804 |
| VCG | first_20pct_lifetime | global_feasible_bin | 20672 | 2515.07 | 70752 | 2.57295e+06 | 2.5051e+06 | 19.1111 | 1023.01 | 0.0717042 |
| VCG | first_20pct_lifetime | historical_stationary_context_bin | 20672 | 2346.8 | 66932.1 | 2.57257e+06 | 2.50469e+06 | 19.1083 | 1096.21 | 0 |
| VCG | first_20pct_lifetime | flat_admissible_idvc | 20672 | 2409.48 | 66839.8 | 2.58277e+06 | 2.51521e+06 | 19.184 | 1071.92 | 0.0267108 |
| VCG | first_20pct_lifetime | contextual_admissible_idvc | 20672 | 2466.2 | 67096.4 | 2.6316e+06 | 2.56352e+06 | 19.5467 | 1067.07 | 0.0508793 |
| VCG | first_20pct_lifetime | shrunk_contextual_idvc | 20672 | 2465.9 | 67093.8 | 2.6313e+06 | 2.5632e+06 | 19.5445 | 1067.07 | 0.0507517 |
| VCG | first_20pct_lifetime | oracle_ex_post_feasible_bin | 20672 | 6585.82 | 173304 | 1.99063e+07 | 1.98177e+07 | 147.858 | 3022.61 | 1.8063 |

## Early-AUC Over Fixed Horizons

| auction | policy | fixed horizons | contacts early-AUC | early-AUC lift | viol. AUC | util. AUC |
| --- | --- | --- | --- | --- | --- | --- |
| FPA | global_feasible_bin | first_period,first_3,first_6,first_12,first_24 | 1630.57 | 0.0293648 | 113792 | 0.63564 |
| FPA | historical_stationary_context_bin | first_period,first_3,first_6,first_12,first_24 | 1584.06 | 0 | 163268 | 0.854242 |
| FPA | flat_admissible_idvc | first_period,first_3,first_6,first_12,first_24 | 676.572 | -0.572886 | 5051.18 | 0.0274185 |
| FPA | contextual_admissible_idvc | first_period,first_3,first_6,first_12,first_24 | 726.562 | -0.541328 | 10627.7 | 0.0429622 |
| FPA | shrunk_contextual_idvc | first_period,first_3,first_6,first_12,first_24 | 724.424 | -0.542678 | 9751.63 | 0.0397342 |
| FPA | oracle_ex_post_feasible_bin | first_period,first_3,first_6,first_12,first_24 | 1464.63 | -0.0753954 | 602018 | 1.8017 |
| VCG | global_feasible_bin | first_period,first_3,first_6,first_12,first_24 | 3971.49 | 0.116006 | 3.26631e+06 | 16.0226 |
| VCG | historical_stationary_context_bin | first_period,first_3,first_6,first_12,first_24 | 3558.66 | 0 | 3.2644e+06 | 16.0158 |
| VCG | flat_admissible_idvc | first_period,first_3,first_6,first_12,first_24 | 3679.29 | 0.033897 | 3.29107e+06 | 16.1027 |
| VCG | contextual_admissible_idvc | first_period,first_3,first_6,first_12,first_24 | 3793 | 0.0658493 | 3.38331e+06 | 16.4198 |
| VCG | shrunk_contextual_idvc | first_period,first_3,first_6,first_12,first_24 | 3792.14 | 0.0656079 | 3.38273e+06 | 16.4167 |
| VCG | oracle_ex_post_feasible_bin | first_period,first_3,first_6,first_12,first_24 | 11514.1 | 2.2355 | 3.29245e+07 | 121.624 |

## Validation-Tuned Frontier

The historical stationary fixed-bin baseline is locked at scale `1.00` for the primary comparator; scalar-tuned historical variants are not used as the primary comparator.

| auction | policy | scale | validation AUC | validation viol. | selected feasible |
| --- | --- | --- | --- | --- | --- |
| FPA | global_feasible_bin | 1 | 636.351 | 39548.1 | True |
| FPA | historical_stationary_context_bin | 1 | 605.377 | 45283.7 | True |
| FPA | flat_admissible_idvc | 3 | 355.638 | 5683.49 | True |
| FPA | contextual_admissible_idvc | 3 | 391.736 | 7664.41 | True |
| FPA | shrunk_contextual_idvc | 3 | 388.705 | 6495.07 | True |
| VCG | global_feasible_bin | 1.25 | 2787.52 | 2.30188e+06 | True |
| VCG | historical_stationary_context_bin | 1 | 2355.4 | 2.27945e+06 | True |
| VCG | flat_admissible_idvc | 3 | 2463.62 | 2.33638e+06 | True |
| VCG | contextual_admissible_idvc | 2 | 2517.12 | 2.38998e+06 | True |
| VCG | shrunk_contextual_idvc | 2 | 2517.16 | 2.39011e+06 | True |

## Test Bootstrap For Selected Frontier

Paired intervals cluster by campaign with `1000` resamples and require at least `30` campaign clusters for evidentiary CIs. Smoke/capped runs are non-evidentiary even when numeric diagnostics are present.

| auction | policy | evidentiary | clusters | min clusters | resamples | contact lift mean | contact lift lo | contact lift hi | viol. diff mean | viol. diff lo | viol. diff hi | ineligible reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPA | global_feasible_bin | True | 2060 | 30 | 1000 | 0.0293648 | 0.00884081 | 0.0533683 | -24.0174 | -42.9063 | -8.47386 | None |
| FPA | flat_admissible_idvc | True | 2060 | 30 | 1000 | -0.487415 | -0.516172 | -0.461123 | -75.1053 | -98.0849 | -57.1691 | None |
| FPA | contextual_admissible_idvc | True | 2060 | 30 | 1000 | -0.422503 | -0.446749 | -0.398935 | -72.6726 | -93.1545 | -56.5146 | None |
| FPA | shrunk_contextual_idvc | True | 2060 | 30 | 1000 | -0.420866 | -0.443549 | -0.397195 | -72.3577 | -92.6896 | -56.5436 | None |
| FPA | oracle_ex_post_feasible_bin | True | 2060 | 30 | 1000 | -0.0753954 | -0.114289 | -0.0408019 | 212.985 | 153.466 | 282.258 | None |
| VCG | global_feasible_bin | True | 20672 | 30 | 1000 | 0.308659 | 0.223987 | 0.413837 | 3.21828 | 2.03425 | 4.67818 | None |
| VCG | flat_admissible_idvc | True | 20672 | 30 | 1000 | 0.054863 | 0.0447524 | 0.0655459 | 4.42573 | 3.62717 | 5.30158 | None |
| VCG | contextual_admissible_idvc | True | 20672 | 30 | 1000 | 0.083066 | 0.0705447 | 0.096596 | 9.03397 | 7.79423 | 10.3627 | None |
| VCG | shrunk_contextual_idvc | True | 20672 | 30 | 1000 | 0.083141 | 0.0704494 | 0.0969067 | 9.00053 | 7.76385 | 10.3487 | None |
| VCG | oracle_ex_post_feasible_bin | True | 20672 | 30 | 1000 | 2.2355 | 2.09002 | 2.39611 | 1434.8 | 1382.02 | 1496.88 | None |

### Paired-CI Inclusion

Campaign-level CIs use campaigns with at least one evaluated public-stats period for both the selected policy and the historical comparator over the fixed horizons; campaigns without public stats rows after the chronological split are counted as attrition, not as zero-outcome campaigns.

| auction | split test campaigns | public-stats campaigns | paired primary clusters | excluded from paired CI | inclusion rule |
| --- | --- | --- | --- | --- | --- |
| FPA | 2060 | 2060 | 2060 | 0 | campaign has at least one evaluated public stats period for both the policy and historical comparator over fixed horizons |
| VCG | 45330 | 20672 | 20672 | 0 | campaign has at least one evaluated public stats period for both the policy and historical comparator over fixed horizons |

## Gate Status

| auction | evidentiary | primary policy | pass | endpoint CI ok | constraint CI ok | consequence |
| --- | --- | --- | --- | --- | --- | --- |
| FPA | True | shrunk_contextual_idvc | False | False | True | Unchanged public BAT remains boundary evidence; do not claim public-BAT deployment lift. |
| VCG | True | shrunk_contextual_idvc | False | True | False | Unchanged public BAT remains boundary evidence; do not claim public-BAT deployment lift. |

## Support-Stratified Selected Test Replay

Support rule: low `<500` training rows, medium `500-5000`, high `>5000`; weak means Gram condition is missing or `>1e5`.

| auction | horizon | stratum | support rule | policy | campaigns | fallbacks | contacts | contact lift | budget viol. | util. |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 471 | None | 99.732 | 0.125228 | 7418.6 | 0.874897 |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 471 | 65 | 88.6327 | 0 | 4808.64 | 0.628205 |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 471 | None | 62.3704 | -0.296305 | 368.638 | 0.0776827 |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 471 | 65 | 48.547 | -0.452267 | 186.431 | 0.0434324 |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 471 | 65 | 48.5922 | -0.451757 | 186.431 | 0.0434802 |
| FPA | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 471 | None | 84.2908 | -0.0489874 | 3992.01 | 0.973777 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 1519 | None | 101.291 | -0.0317881 | 6202.85 | 0.48356 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 1519 | 65 | 104.617 | 0 | 15931.6 | 0.968189 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 1519 | None | 27.3083 | -0.738969 | 375.753 | 0.0298201 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 1519 | 65 | 47.2341 | -0.548505 | 356.26 | 0.0460455 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 1519 | 65 | 47.2341 | -0.548505 | 356.26 | 0.0460455 |
| FPA | first_period | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 1519 | None | 93.119 | -0.109906 | 10798.9 | 1.16961 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 65 | None | 0.571937 | 0 | 0 | 0.0756347 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 65 | 65 | 0.571937 | 0 | 0 | 0.0756347 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 65 | None | 0.0892358 | -0.843976 | 0 | 0.00209372 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 65 | 65 | 0.0892358 | -0.843976 | 0 | 0.00209372 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 65 | 65 | 0.0892358 | -0.843976 | 0 | 0.00209372 |
| FPA | first_period | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 65 | None | 0.753212 | 0.316949 | 0 | 0.820601 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 5 | None | 0.117782 | -0.441464 | 0 | 0.173107 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 5 | 65 | 0.210877 | 0 | 36.3319 | 0.845942 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 5 | None | 0.0322235 | -0.847193 | 0 | 0.00371114 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 5 | 65 | 0.0683157 | -0.67604 | 0 | 0.0223288 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 5 | 65 | 0.0683157 | -0.67604 | 0 | 0.0223288 |
| FPA | first_period | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 5 | None | 0.153313 | -0.272975 | 0 | 0.716019 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 471 | None | 345.217 | 0.118171 | 26977.9 | 1.01615 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 471 | 195 | 308.733 | 0 | 17148.3 | 0.719551 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 471 | None | 213.196 | -0.309448 | 771.219 | 0.0626641 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 471 | 195 | 178.252 | -0.422635 | 483.781 | 0.0389439 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 471 | 195 | 178.261 | -0.422604 | 483.781 | 0.0389353 |
| FPA | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 471 | None | 285.834 | -0.0741709 | 31247 | 1.45357 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 1519 | None | 434.559 | -0.0359716 | 31003 | 0.711498 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 1519 | 195 | 450.774 | 0 | 72401.7 | 1.37399 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 1519 | None | 122.666 | -0.727876 | 1161.69 | 0.0298338 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 1519 | 195 | 214.831 | -0.523418 | 2247 | 0.0694174 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 1519 | 195 | 218.522 | -0.515229 | 3302.16 | 0.0841508 |
| FPA | first_3 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 1519 | None | 380.865 | -0.155086 | 29232.3 | 1.1254 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 65 | None | 1.66286 | 0 | 0 | 0.0731487 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 65 | 195 | 1.66286 | 0 | 0 | 0.0731487 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 65 | None | 0.279363 | -0.831999 | 0 | 0.00207364 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 65 | 195 | 0.279363 | -0.831999 | 0 | 0.00207364 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 65 | 195 | 0.279363 | -0.831999 | 0 | 0.00207364 |
| FPA | first_3 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 65 | None | 2.2282 | 0.339975 | 0 | 0.819443 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 5 | None | 0.413182 | -0.233906 | 9.36267 | 0.199522 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 5 | 195 | 0.539335 | 0 | 79.6097 | 0.721391 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 5 | None | 0.212728 | -0.605575 | 0 | 0.00685471 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 5 | 195 | 0.310983 | -0.423395 | 0 | 0.0367462 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 5 | 195 | 0.307717 | -0.429451 | 0 | 0.0336428 |
| FPA | first_3 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 5 | None | 0.487727 | -0.0956877 | 0 | 0.683461 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 471 | None | 627.714 | 0.115598 | 47278.5 | 0.931984 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 471 | 390 | 562.67 | 0 | 29892 | 0.661613 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 471 | None | 390.112 | -0.306677 | 1593.54 | 0.0640259 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 471 | 390 | 338.446 | -0.398501 | 989.966 | 0.0393026 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 471 | 390 | 338.778 | -0.39791 | 989.966 | 0.0393321 |
| FPA | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 471 | None | 528.632 | -0.060494 | 61347.4 | 1.44038 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 1519 | None | 775.939 | -0.0332076 | 54849.7 | 0.638308 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 1519 | 390 | 802.591 | 0 | 118097 | 1.17023 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 1519 | None | 258.876 | -0.677449 | 3263.31 | 0.0374787 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 1519 | 390 | 408.722 | -0.490747 | 6404 | 0.0824288 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 1519 | 390 | 412.341 | -0.486238 | 7445.54 | 0.0896032 |
| FPA | first_6 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 1519 | None | 687.5 | -0.143399 | 121719 | 1.55117 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 65 | None | 2.65435 | 0 | 0 | 0.0588902 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 65 | 390 | 2.65435 | 0 | 0 | 0.0588902 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 65 | None | 0.472643 | -0.821937 | 0 | 0.00216435 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 65 | 390 | 0.472643 | -0.821937 | 0 | 0.00216435 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 65 | 390 | 0.472643 | -0.821937 | 0 | 0.00216435 |
| FPA | first_6 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 65 | None | 3.77653 | 0.42277 | 0 | 0.815605 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 5 | None | 0.866696 | -0.307948 | 21.5142 | 0.205406 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 5 | 390 | 1.25236 | 0 | 223.144 | 0.818137 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 5 | None | 0.423088 | -0.662167 | 0 | 0.00561761 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 5 | 390 | 0.724879 | -0.421189 | 56.2912 | 0.162204 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 5 | 390 | 0.629851 | -0.497067 | 0 | 0.0338011 |
| FPA | first_6 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 5 | None | 0.997455 | -0.203538 | 0 | 0.67044 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 471 | None | 1017.03 | 0.11181 | 72035.6 | 0.756824 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 471 | 780 | 914.749 | 0 | 46890.2 | 0.554244 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 471 | None | 648.226 | -0.291362 | 4251.88 | 0.0770469 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 471 | 780 | 580.696 | -0.365186 | 2878.97 | 0.0531287 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 471 | 780 | 580.724 | -0.365154 | 2856.2 | 0.0528772 |
| FPA | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 471 | None | 888.762 | -0.0284087 | 300366 | 2.51701 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 1519 | None | 1203.16 | -0.027996 | 81848.9 | 0.495127 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 1519 | 780 | 1237.81 | 0 | 168372 | 0.883301 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 1519 | None | 454.735 | -0.632629 | 5576.18 | 0.0366672 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 1519 | 780 | 664.899 | -0.462843 | 13397.5 | 0.0824694 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 1519 | 780 | 668.328 | -0.460073 | 14418 | 0.0860213 |
| FPA | first_12 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 1519 | None | 1092.07 | -0.117744 | 495677 | 2.40435 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 65 | None | 4.74023 | 0 | 0 | 0.0518059 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 65 | 780 | 4.74023 | 0 | 0 | 0.0518059 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 65 | None | 0.984593 | -0.79229 | 0 | 0.00205842 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 65 | 780 | 0.984593 | -0.79229 | 0 | 0.00205842 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 65 | 780 | 0.984593 | -0.79229 | 0 | 0.00205842 |
| FPA | first_12 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 65 | None | 6.86638 | 0.448533 | 0 | 0.80679 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 5 | None | 1.37721 | -0.352574 | 21.5142 | 0.160978 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 5 | 780 | 2.1272 | 0 | 345.572 | 0.682045 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 5 | None | 0.737731 | -0.653192 | 0 | 0.00510963 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 5 | 780 | 1.12738 | -0.470018 | 56.2912 | 0.0947247 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 5 | 780 | 1.13785 | -0.465097 | 25.6155 | 0.0671447 |
| FPA | first_12 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 5 | None | 1.68606 | -0.207383 | 0 | 0.716052 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 471 | None | 1655.08 | 0.109513 | 119816 | 0.640454 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 471 | 1556 | 1491.72 | 0 | 81370.6 | 0.482802 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 471 | None | 1056.34 | -0.291869 | 13431.3 | 0.098779 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 471 | 1556 | 962.531 | -0.354752 | 11312.8 | 0.0794087 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 471 | 1556 | 962.345 | -0.354877 | 11321.7 | 0.0794155 |
| FPA | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 471 | None | 1476 | -0.0105393 | 775197 | 3.05595 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 1519 | None | 1866.23 | -0.0323915 | 121417 | 0.390508 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 1519 | 1556 | 1928.7 | 0 | 260197 | 0.715018 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 1519 | None | 819.104 | -0.575307 | 11926.4 | 0.0420387 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 1519 | 1556 | 1121.37 | -0.418588 | 29219.9 | 0.0887545 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 1519 | 1556 | 1123.46 | -0.417501 | 29478.3 | 0.0891793 |
| FPA | first_24 | high_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 1519 | None | 1769.34 | -0.0826238 | 1.1798e+06 | 2.72961 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 65 | None | 12.3417 | 0 | 2.72758 | 0.0684766 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 65 | 1556 | 12.3417 | 0 | 2.72758 | 0.0684766 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 65 | None | 2.33102 | -0.811126 | 0 | 0.00214833 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 65 | 1556 | 2.33102 | -0.811126 | 0 | 0.00214833 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 65 | 1556 | 2.33102 | -0.811126 | 0 | 0.00214833 |
| FPA | first_24 | low_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 65 | None | 17.0276 | 0.379683 | 0 | 0.824661 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 5 | None | 2.16679 | -0.318812 | 58.6679 | 0.154268 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 5 | 1556 | 3.1809 | 0 | 544.725 | 0.544369 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 5 | None | 1.32361 | -0.583887 | 37.1536 | 0.0576935 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 5 | 1556 | 2.02157 | -0.364467 | 224.22 | 0.196531 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 5 | 1556 | 2.01278 | -0.36723 | 193.544 | 0.1756 |
| FPA | first_24 | medium_weak | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 5 | None | 2.73971 | -0.138698 | 716.217 | 1.06184 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 20651 | None | 1240.25 | 0.139956 | 1.45003e+06 | 30.4083 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 20651 | None | 1087.98 | 0 | 1.44018e+06 | 30.1938 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 20651 | None | 1119.87 | 0.0293077 | 1.45498e+06 | 30.5004 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 20651 | None | 1137.9 | 0.0458812 | 1.47027e+06 | 30.8212 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 20651 | None | 1137.89 | 0.0458695 | 1.47024e+06 | 30.8206 |
| VCG | first_period | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 20651 | None | 2542.64 | 1.33702 | 7.19772e+06 | 148.76 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 21 | None | 0.731813 | 0.00363101 | 31.7057 | 1.18611 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 21 | None | 0.729166 | 0 | 38.9557 | 1.47128 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 21 | None | 0.712948 | -0.0222409 | 64.7857 | 2.14091 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 21 | None | 0.712948 | -0.0222409 | 64.7857 | 2.14091 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 21 | None | 0.712948 | -0.0222409 | 64.7857 | 2.14091 |
| VCG | first_period | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 21 | None | 0.874594 | 0.199445 | 373.676 | 11.2442 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 20651 | None | 2780.6 | 0.224749 | 2.5596e+06 | 18.5904 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 20651 | None | 2270.34 | 0 | 2.52711e+06 | 18.3497 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 20651 | None | 2369.1 | 0.043498 | 2.56953e+06 | 18.6508 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 20651 | None | 2423.88 | 0.0676292 | 2.61543e+06 | 18.9795 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 20651 | None | 2425.21 | 0.0682127 | 2.61532e+06 | 18.9788 |
| VCG | first_3 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 20651 | None | 6287.58 | 1.76944 | 1.81208e+07 | 128.399 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 21 | None | 2.00332 | -0.00558614 | 75.0957 | 0.9795 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 21 | None | 2.01457 | 0 | 113.816 | 1.42254 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 21 | None | 2.11865 | 0.0516623 | 309.466 | 3.23795 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 21 | None | 1.88943 | -0.0621195 | 165.166 | 1.83384 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 21 | None | 1.88943 | -0.0621195 | 165.166 | 1.83384 |
| VCG | first_3 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 21 | None | 3.50727 | 0.74095 | 6934.65 | 67.3821 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 20651 | None | 4594.88 | 0.294225 | 3.43281e+06 | 13.0891 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 20651 | None | 3550.3 | 0 | 3.36913e+06 | 12.8439 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 20651 | None | 3730.53 | 0.0507643 | 3.44769e+06 | 13.1342 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 20651 | None | 3830.38 | 0.07889 | 3.54143e+06 | 13.4819 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 20651 | None | 3830.33 | 0.0788761 | 3.54074e+06 | 13.4792 |
| VCG | first_6 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 20651 | None | 11303.1 | 2.1837 | 3.23273e+07 | 119.001 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 21 | None | 3.54866 | -0.0103762 | 369.906 | 2.06506 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 21 | None | 3.58587 | 0 | 449.336 | 2.50033 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 21 | None | 3.7809 | 0.0543904 | 719.626 | 3.74164 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 21 | None | 3.38675 | -0.0555275 | 497.356 | 2.66048 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 21 | None | 3.38675 | -0.0555275 | 497.356 | 2.66048 |
| VCG | first_6 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 21 | None | 5.58659 | 0.557948 | 11386.4 | 55.4419 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 20651 | None | 6782.96 | 0.344131 | 4.34963e+06 | 9.99588 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 20651 | None | 5046.35 | 0 | 4.24553e+06 | 9.75676 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 20651 | None | 5347.99 | 0.0597739 | 4.39304e+06 | 10.0822 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 20651 | None | 5498.94 | 0.0896863 | 4.5376e+06 | 10.4012 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 20651 | None | 5498.96 | 0.089689 | 4.53633e+06 | 10.3984 |
| VCG | first_12 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 20651 | None | 17358 | 2.43971 | 4.94328e+07 | 108.509 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 21 | None | 4.9231 | 0.00926338 | 594.463 | 2.00007 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 21 | None | 4.87792 | 0 | 681.463 | 2.28993 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 21 | None | 5.08049 | 0.0415278 | 942.143 | 2.97764 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 21 | None | 4.68633 | -0.0392753 | 719.873 | 2.34041 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 21 | None | 4.68633 | -0.0392753 | 719.873 | 2.34041 |
| VCG | first_12 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 21 | None | 8.00683 | 0.641445 | 16777.4 | 48.249 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 20651 | None | 7869.08 | 0.351816 | 4.86082e+06 | 9.21805 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 20651 | None | 5821.12 | 0 | 4.73801e+06 | 8.98593 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 20651 | None | 6183.99 | 0.0623378 | 4.91115e+06 | 9.29969 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 20651 | None | 6363.6 | 0.0931917 | 5.08878e+06 | 9.62226 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 20651 | None | 6363.66 | 0.0932017 | 5.08742e+06 | 9.6198 |
| VCG | first_24 | high_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 20651 | None | 20051.2 | 2.44457 | 5.749e+07 | 103.726 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | global_feasible_bin | 21 | None | 6.39219 | 0.0632159 | 678.986 | 2.00669 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | historical_stationary_context_bin | 21 | None | 6.01212 | 0 | 758.846 | 2.23738 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | flat_admissible_idvc | 21 | None | 6.33494 | 0.053694 | 1019.53 | 2.84306 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | contextual_admissible_idvc | 21 | None | 5.95181 | -0.0100324 | 797.256 | 2.28188 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | shrunk_contextual_idvc | 21 | None | 5.95181 | -0.0100324 | 797.256 | 2.28188 |
| VCG | first_24 | medium_ok | low<500; medium<=5000; high>5000; weak cond missing/>1e5 | oracle_ex_post_feasible_bin | 21 | None | 9.87216 | 0.642041 | 18460 | 46.7738 |

## Split And Fit Diagnostics

| auction | campaigns | train | validation | test | train states | validation states | test states | flat s | flat alpha | ctx fits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FPA | 10296 | 7207 | 1029 | 2060 | 305262 | 30336 | 55487 | 273.331 | 1 | 49 |
| VCG | 230442 | 158655 | 22665 | 45330 | 1584870 | 271174 | 250154 | 1e-08 | 0.0672024 | 57 |
