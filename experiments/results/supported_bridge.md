# Supported BAT-Shaped Bridge

- Claim boundary: Mechanism evidence with BAT-shaped support and injected known response transforms; not unchanged public-BAT deployment lift.
- Seeds: `100`
- Contexts: `60`
- Bridge pass: `True`
- Primary contact lift CI: `{'clusters': 6000, 'scenario_pairs': 24000, 'mean': 0.04104198746341757, 'lo': 0.040911001024894686, 'hi': 0.041179747564317755}`
- Primary violation diff CI: `{'clusters': 6000, 'scenario_pairs': 24000, 'mean': -0.016969852335312077, 'lo': -0.017040242931143798, 'hi': -0.01689878262660069}`
- Uncertainty scope: cluster bootstrap over synthetic campaign/context clusters conditional on the frozen scenario registry; not empirical BAT uncertainty
- Mismatch abstention rate: `1.000`
- Negative controls: `{'null_stationary_guarded_vs_historical': {'clusters': 6000, 'scenario_pairs': 6000, 'mean': -0.0006144015753015858, 'lo': -0.0007915254968827133, 'hi': -0.00045276133507931817}, 'unsupported_contextual_vs_global': {'clusters': 6000, 'scenario_pairs': 6000, 'mean': -0.21962075078214957, 'lo': -0.2199233961981292, 'hi': -0.2193276575133284}, 'unsupported_guarded_vs_historical': {'clusters': 6000, 'scenario_pairs': 6000, 'mean': -6.23296889262288e-05, 'lo': -0.0003979275094641207, 'hi': 0.0002966530005785478}, 'unsupported_guard_abstention_rate': 1.0, 'pass': True}`
- Sensitivity grid pass: `True`; min lower lift CI `0.03368550014199286`; max violation upper CI `-0.011843250343171305`

| scenario             | initialization        | runs | early_auc | lift_vs_hist | violation_auc | ttt | abstain |
| -------------------- | --------------------- | ---- | --------- | ------------ | ------------- | --- | ------- |
| abrupt_shift         | contextual_idvc       | 6000 | 8.7932    | 0.0625       | 0.0050        | 0.0 | 0.000   |
| abrupt_shift         | global_flat_idvc      | 6000 | 8.5564    | 0.0339       | 0.0136        | 2.0 | 0.000   |
| abrupt_shift         | guarded_idvc          | 6000 | 8.7693    | 0.0596       | 0.0057        | 0.0 | 0.000   |
| abrupt_shift         | historical_stationary | 6000 | 8.2758    | 0.0000       | 0.0363        | 8.0 | 0.000   |
| abrupt_shift         | oracle                | 6000 | 8.8380    | 0.0679       | 0.0050        | 0.0 | 0.000   |
| abrupt_shift         | response_idvc         | 6000 | 8.7932    | 0.0625       | 0.0050        | 0.0 | 0.000   |
| fpa_response_bias    | contextual_idvc       | 6000 | 8.3995    | -0.0375      | 0.0412        | 6.0 | 0.000   |
| fpa_response_bias    | global_flat_idvc      | 6000 | 8.8432    | 0.0133       | 0.0056        | 2.0 | 0.000   |
| fpa_response_bias    | guarded_idvc          | 6000 | 9.0494    | 0.0370       | 0.0000        | 0.0 | 0.000   |
| fpa_response_bias    | historical_stationary | 6000 | 8.7269    | 0.0000       | 0.0132        | 4.0 | 0.000   |
| fpa_response_bias    | oracle                | 6000 | 9.1108    | 0.0440       | 0.0000        | 0.0 | 0.000   |
| fpa_response_bias    | response_idvc         | 6000 | 9.0755    | 0.0400       | 0.0000        | 0.0 | 0.000   |
| hybrid               | contextual_idvc       | 6000 | 8.8202    | -0.0005      | 0.0122        | 3.0 | 0.000   |
| hybrid               | global_flat_idvc      | 6000 | 8.9361    | 0.0126       | 0.0050        | 2.0 | 0.000   |
| hybrid               | guarded_idvc          | 6000 | 9.0997    | 0.0312       | 0.0000        | 0.0 | 0.000   |
| hybrid               | historical_stationary | 6000 | 8.8247    | 0.0000       | 0.0116        | 3.0 | 0.000   |
| hybrid               | oracle                | 6000 | 9.1430    | 0.0361       | 0.0000        | 0.0 | 0.000   |
| hybrid               | response_idvc         | 6000 | 9.0966    | 0.0308       | 0.0000        | 0.0 | 0.000   |
| matched              | contextual_idvc       | 6000 | 9.0945    | 0.0402       | 0.0000        | 0.0 | 0.000   |
| matched              | global_flat_idvc      | 6000 | 8.8592    | 0.0133       | 0.0054        | 2.0 | 0.000   |
| matched              | guarded_idvc          | 6000 | 9.0708    | 0.0375       | 0.0000        | 0.0 | 0.000   |
| matched              | historical_stationary | 6000 | 8.7429    | 0.0000       | 0.0126        | 4.0 | 0.000   |
| matched              | oracle                | 6000 | 9.1361    | 0.0450       | 0.0000        | 0.0 | 0.000   |
| matched              | response_idvc         | 6000 | 9.0945    | 0.0402       | 0.0000        | 0.0 | 0.000   |
| null_stationary      | contextual_idvc       | 6000 | 9.0956    | -0.0007      | 0.0000        | 0.0 | 0.000   |
| null_stationary      | global_flat_idvc      | 6000 | 9.0432    | -0.0065      | 0.0003        | 0.0 | 0.000   |
| null_stationary      | guarded_idvc          | 6000 | 9.0968    | -0.0006      | 0.0000        | 0.0 | 0.000   |
| null_stationary      | historical_stationary | 6000 | 9.1024    | 0.0000       | 0.0000        | 0.0 | 0.000   |
| null_stationary      | oracle                | 6000 | 9.1373    | 0.0038       | 0.0000        | 0.0 | 0.000   |
| null_stationary      | response_idvc         | 6000 | 9.0956    | -0.0007      | 0.0000        | 0.0 | 0.000   |
| unsupported_mismatch | contextual_idvc       | 6000 | 6.9911    | -0.2197      | 0.1714        | 9.0 | 0.000   |
| unsupported_mismatch | global_flat_idvc      | 6000 | 8.9586    | -0.0001      | 0.0034        | 1.0 | 0.000   |
| unsupported_mismatch | guarded_idvc          | 6000 | 8.9586    | -0.0001      | 0.0034        | 1.0 | 1.000   |
| unsupported_mismatch | historical_stationary | 6000 | 8.9592    | 0.0000       | 0.0027        | 1.0 | 0.000   |
| unsupported_mismatch | oracle                | 6000 | 9.2001    | 0.0269       | 0.0000        | 0.0 | 0.000   |
| unsupported_mismatch | response_idvc         | 6000 | 6.9911    | -0.2197      | 0.1714        | 9.0 | 0.000   |
