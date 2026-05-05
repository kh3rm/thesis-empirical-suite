# Batch summary

## Batch headlines
- total_runs_seen: 40
- total_runs_aggregated: 40
- total_runs_failed_or_incomplete: 0
- total_scenarios: 4
- highest_variance_scenario: state_non_regression__retained_immediate__backlog_shock__standard
- highest_variance_std: 2.122127
- highest_p99_scenario: state_non_regression__retained_immediate__backlog_forward_resume__standard
- highest_cluster100_scenario: state_non_regression__retained_immediate__backlog_shock__standard
- highest_unattained_scenario: state_non_regression__transient_immediate__backlog_shock__standard
- highest_residual_backlog_scenario: None

## Included families
- backlog shock
- backlog shock + forward resume

## Strongest amplifiers
- largest mean amplification: n/a
- largest p95 amplification: n/a
- largest gap-cv amplification: n/a
- strongest deferred-vs-immediate shape gap: n/a
- largest bulk-window amplifier: n/a
- largest upper-bulk-window amplifier: n/a
- largest late-region-window amplifier: n/a
- largest tail-window amplifier: n/a
- largest straggler-window amplifier: n/a
- largest upper-bulk region shift: n/a
- largest convergence-region shift: n/a
- largest straggler-region shift: n/a
- strongest upper-bulk compression: n/a
- strongest late-region compression: n/a
- strongest tail-window compression: n/a
- strongest straggler compression: n/a
- largest tail-to-bulk shift: n/a
- largest upper-bulk-to-bulk shift: n/a
- strongest tail-without-mean candidate: n/a
- largest unattained-case increase: n/a
- largest residual backlog indicator: n/a

## Burden redistribution highlights
- strongest synchronized-lateness candidate: n/a
- strongest concentration-sensitive candidate: n/a
- strongest convergence-region candidate: n/a
- strongest upper-bulk displacement candidate: n/a
- strongest convergence-over-straggler candidate: n/a
- strongest tail-sensitive candidate: n/a
- strongest straggler-sensitive candidate: n/a
- strongest bulk-stretch candidate: n/a

## Candidate findings

## How to read the roles
- **Broadly delayed recovery** means much of the attainment curve shifts later together.
- **Catch-up surge recovery** means recovery resumes in a more synchronized burst rather than spreading out smoothly.
- **Late-convergence fragility** means the near-finish region moves more than the average alone would suggest.
- **Straggler-stretch recovery** means the slowest cases stretch more than the rest of the curve.
- **General slowdown** means average recovery time rises without a clearer regional or concentration signature.
- **Mixed burden pattern** means more than one burden type matters at once and no single one dominates cleanly.

## Burden redistribution map

## Family-role cues

## Curve-region cues
- scenarios_with_any_censoring: 1
- scenarios_with_any_residual_backlog: 0
- max_window_expired_repeat_fraction: 0.0

## Interpretive cautions
- No clean strongly straggler-stretch pattern was observed in this batch; the strongest late effects should be read mainly through near-finish-region and broad lateness signals rather than a pure tail story.
- Some of the strongest late-region effects in this batch appear as region displacement rather than simple window expansion, so region-shift metrics may be more informative than raw window deltas on their own.

## Analysis-ready exports
- aggregates/scenario_repeat_summary.csv
- aggregates/family_comparison_summary.csv
- aggregates/family_delta_summary.csv
- aggregates/family_role_summary.csv
- aggregates/burden_redistribution_summary.csv
- aggregates/scenario_curve_summary.csv
- aggregates/curve_region_summary.csv
- aggregates/analysis_ready_family_summary.csv
- aggregates/candidate_findings.json
- aggregates/profile_summary.json

## Plotting
- If plots were not generated yet, run plot_batch.sh on this batch later.
