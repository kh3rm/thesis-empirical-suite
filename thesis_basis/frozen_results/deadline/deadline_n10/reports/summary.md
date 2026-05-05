# Batch summary

## Batch headlines
- total_runs_seen: 120
- total_runs_aggregated: 120
- total_runs_failed_or_incomplete: 0
- total_scenarios: 12
- highest_variance_scenario: deadline_constrained__retained_immediate__backlog_shock__standard
- highest_variance_std: 2.465669
- highest_p99_scenario: deadline_constrained__retained_deferred__degradation__high
- highest_cluster100_scenario: deadline_constrained__retained_deferred__backlog_shock__standard
- highest_unattained_scenario: None
- highest_residual_backlog_scenario: None

## Included families
- backlog shock
- baseline
- degradation (high)
- degradation (moderate)

## Strongest amplifiers
- largest mean amplification: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (delta_mean_tta=4.341545)
- largest p95 amplification: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (delta_p95=3.210029)
- largest gap-cv amplification: deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] (delta_gap_cv=14.552253)
- strongest deferred-vs-immediate shape gap: deadline_constrained__retained_deferred__degradation__moderate [degradation (moderate)] (deferred_shape_gap_vs_same_family_abs=14.580124)
- largest bulk-window amplifier: deadline_constrained__retained_deferred__degradation__moderate [degradation (moderate)] (delta_bulk_window_25_to_75=1.83884)
- largest upper-bulk-window amplifier: deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] (delta_upper_bulk_window_75_to_90=0.06036)
- largest late-region-window amplifier: deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] (delta_late_region_window_75_to_95=0.067503)
- largest tail-window amplifier: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (delta_tail_window_90_to_99=0.24964)
- largest straggler-window amplifier: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (delta_straggler_window_95_to_99=0.424934)
- largest upper-bulk region shift: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (upper_bulk_region_shift=3.872016)
- largest convergence-region shift: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (convergence_region_shift=3.695629)
- largest straggler-region shift: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (straggler_region_shift=3.102086)
- strongest upper-bulk compression: deadline_constrained__retained_immediate__degradation__high [degradation (high)] (delta_upper_bulk_window_75_to_90=-0.968648)
- strongest late-region compression: deadline_constrained__retained_immediate__degradation__high [degradation (high)] (delta_late_region_window_75_to_95=-1.231777)
- strongest tail-window compression: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (delta_tail_window_90_to_99=-0.568659)
- strongest straggler compression: deadline_constrained__retained_immediate__degradation__high [degradation (high)] (delta_straggler_window_95_to_99=-0.220062)
- largest tail-to-bulk shift: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (tail_to_bulk_ratio_delta=8.069379)
- largest upper-bulk-to-bulk shift: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (upper_bulk_to_bulk_ratio_delta=6.692354)
- strongest tail-without-mean candidate: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (tail_without_mean_score=0.212468)
- largest unattained-case increase: n/a
- largest residual backlog indicator: n/a

## Burden redistribution highlights
- strongest synchronized-lateness candidate: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (synchronized_lateness_score=1.865303)
- strongest concentration-sensitive candidate: deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] (concentration_score=2.207832)
- strongest convergence-region candidate: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (convergence_region_score=1.407855)
- strongest upper-bulk displacement candidate: deadline_constrained__retained_deferred__degradation__high [degradation (high)] (upper_bulk_displacement_score=2.260452)
- strongest convergence-over-straggler candidate: deadline_constrained__retained_immediate__degradation__high [degradation (high)] (convergence_vs_straggler_score=0.548273)
- strongest tail-sensitive candidate: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (tail_score=0.929322)
- strongest straggler-sensitive candidate: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] (straggler_score=2.028632)
- strongest bulk-stretch candidate: deadline_constrained__retained_deferred__degradation__moderate [degradation (moderate)] (bulk_score=1.273791)

## Candidate findings
- Synchronized lateness leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as broadly delayed recovery. This scenario most strongly shifts much of the recovery curve later together.
- Concentration leader: deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] — backlog shock currently reads mainly as catch-up surge recovery. This scenario most strongly converts disturbance into concentrated catch-up behaviour.
- Convergence-region leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as broadly delayed recovery. This scenario most strongly displaces the late-convergence region relative to the early or main bulk.
- Upper-bulk displacement leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as broadly delayed recovery. This scenario most strongly shifts the upper bulk / late recovery body.
- Tail-sensitive candidate: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] — backlog shock currently reads mainly as catch-up surge recovery. This scenario is the strongest current candidate for a true tail-stretch effect, though it should be read alongside convergence-region signals.
- Straggler-sensitive candidate: deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] — backlog shock currently reads mainly as catch-up surge recovery. This scenario most strongly affects the strict straggler window (95→99).
- Upper-bulk shift leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as n/a. This scenario most strongly shifts the upper bulk later in the recovery episode.
- Convergence-region shift leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as n/a. This scenario most strongly shifts the late-convergence region later in the recovery episode.
- Straggler-region shift leader: deadline_constrained__retained_deferred__degradation__high [degradation (high)] — degradation (high) currently reads mainly as n/a. This scenario most strongly shifts the strict straggler region later.
- Upper-bulk compression leader: deadline_constrained__retained_immediate__degradation__high [degradation (high)] — degradation (high) currently reads mainly as n/a. This scenario most strongly compresses the upper bulk while shifting the broader curve.

## How to read the roles
- **Broadly delayed recovery** means much of the attainment curve shifts later together.
- **Catch-up surge recovery** means recovery resumes in a more synchronized burst rather than spreading out smoothly.
- **Late-convergence fragility** means the near-finish region moves more than the average alone would suggest.
- **Straggler-stretch recovery** means the slowest cases stretch more than the rest of the curve.
- **General slowdown** means average recovery time rises without a clearer regional or concentration signature.
- **Mixed burden pattern** means more than one burden type matters at once and no single one dominates cleanly.

## Burden redistribution map
- deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant); secondary=straggler-stretch recovery (tail-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=10.729, timestamp_compression_ratio=1.087, with concentration_score=1.577 outweighing curve-shift scores (sync=0.896, conv=0.089).
- deadline_constrained__retained_immediate__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant); secondary=broadly delayed recovery (synchronized-lateness dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=13.547, timestamp_compression_ratio=1.537, with concentration_score=1.774 outweighing curve-shift scores (sync=1.085, conv=0.571).
- deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=14.552, timestamp_compression_ratio=1.525, with concentration_score=2.208 outweighing curve-shift scores (sync=0.311, conv=0.000).
- deadline_constrained__retained_deferred__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant); secondary=general slowdown (mean-dominant); confidence=medium
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Broad synchronized lateness dominates: mean=4.342s, early_bulk=-1.317s, main_bulk=-0.113s, upper_bulk=-0.618s, late_region=-0.971s; tail_window=-0.569s and straggler_window=-0.216s are secondary.
- deadline_constrained__retained_immediate__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Broad synchronized lateness dominates: mean=3.811s, early_bulk=-1.262s, main_bulk=-1.369s, upper_bulk=-0.969s, late_region=-1.232s; tail_window=-0.483s and straggler_window=-0.220s are secondary.
- deadline_constrained__transient_immediate__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Broad synchronized lateness dominates: mean=3.778s, early_bulk=-1.342s, main_bulk=-1.312s, upper_bulk=-0.769s, late_region=-1.028s; tail_window=-0.468s and straggler_window=-0.209s are secondary.
- deadline_constrained__retained_deferred__degradation__moderate [degradation (moderate)] => broadly delayed recovery (synchronized-lateness dominant); secondary=catch-up surge recovery (concentration-dominant); confidence=medium
  - burden regions: primary=main recovery body (main_bulk), secondary=late recovery body (upper_bulk)
  - reason: Broad synchronized lateness dominates: mean=1.957s, early_bulk=1.449s, main_bulk=0.390s, upper_bulk=-0.783s, late_region=-1.136s; tail_window=-0.568s and straggler_window=-0.215s are secondary.
- deadline_constrained__retained_immediate__degradation__moderate [degradation (moderate)] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=late recovery body (upper_bulk), secondary=main recovery body (main_bulk)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- deadline_constrained__transient_immediate__degradation__moderate [degradation (moderate)] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=late recovery body (upper_bulk), secondary=near-finish region (late_convergence)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.

## Family-role cues
- deadline_constrained__retained_deferred__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant) with straggler-stretch recovery (tail-dominant) as secondary; confidence=high
  - scores: sync=0.895573, conc=1.576983, conv=0.088824, tail=0.929322, straggler=2.028632
  - reason: Recovery concentration dominates: gap_cv=10.729, timestamp_compression_ratio=1.087, with concentration_score=1.577 outweighing curve-shift scores (sync=0.896, conv=0.089).
- deadline_constrained__retained_immediate__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant) with broadly delayed recovery (synchronized-lateness dominant) as secondary; confidence=high
  - scores: sync=1.084541, conc=1.774215, conv=0.571406, tail=0.039666, straggler=1.023462
  - reason: Recovery concentration dominates: gap_cv=13.547, timestamp_compression_ratio=1.537, with concentration_score=1.774 outweighing curve-shift scores (sync=1.085, conv=0.571).
- deadline_constrained__transient_immediate__backlog_shock__standard [backlog shock] => catch-up surge recovery (concentration-dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=0.310926, conc=2.207832, conv=0.0, tail=0.0, straggler=0.421679
  - reason: Recovery concentration dominates: gap_cv=14.552, timestamp_compression_ratio=1.525, with concentration_score=2.208 outweighing curve-shift scores (sync=0.311, conv=0.000).
- deadline_constrained__retained_deferred__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant) with general slowdown (mean-dominant) as secondary; confidence=medium
  - scores: sync=1.865303, conc=0.850177, conv=1.407855, tail=0.576787, straggler=1.411496
  - reason: Broad synchronized lateness dominates: mean=4.342s, early_bulk=-1.317s, main_bulk=-0.113s, upper_bulk=-0.618s, late_region=-0.971s; tail_window=-0.569s and straggler_window=-0.216s are secondary.
- deadline_constrained__retained_immediate__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=1.861505, conc=0.657756, conv=1.328409, tail=0.393874, straggler=0.97517
  - reason: Broad synchronized lateness dominates: mean=3.811s, early_bulk=-1.262s, main_bulk=-1.369s, upper_bulk=-0.969s, late_region=-1.232s; tail_window=-0.483s and straggler_window=-0.220s are secondary.
- deadline_constrained__transient_immediate__degradation__high [degradation (high)] => broadly delayed recovery (synchronized-lateness dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=1.841313, conc=0.506585, conv=1.317076, tail=0.445941, straggler=1.027353
  - reason: Broad synchronized lateness dominates: mean=3.778s, early_bulk=-1.342s, main_bulk=-1.312s, upper_bulk=-0.769s, late_region=-1.028s; tail_window=-0.468s and straggler_window=-0.209s are secondary.
- deadline_constrained__retained_deferred__degradation__moderate [degradation (moderate)] => broadly delayed recovery (synchronized-lateness dominant) with catch-up surge recovery (concentration-dominant) as secondary; confidence=medium
  - scores: sync=1.335814, conc=1.115801, conv=1.041906, tail=0.132662, straggler=0.965028
  - reason: Broad synchronized lateness dominates: mean=1.957s, early_bulk=1.449s, main_bulk=0.390s, upper_bulk=-0.783s, late_region=-1.136s; tail_window=-0.568s and straggler_window=-0.215s are secondary.
- deadline_constrained__retained_immediate__degradation__moderate [degradation (moderate)] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.317521, conc=0.0, conv=1.231592, tail=0.43066, straggler=0.864126
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- deadline_constrained__transient_immediate__degradation__moderate [degradation (moderate)] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.2971, conc=0.0, conv=1.225989, tail=0.48656, straggler=0.908738
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.

## Curve-region cues
- scenarios_with_any_censoring: 0
- scenarios_with_any_residual_backlog: 0
- max_window_expired_repeat_fraction: 0.0

## Interpretive cautions
- Late-convergence scenarios should be read using both near-finish-region and late-recovery-body evidence rather than strict tail metrics alone.

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
