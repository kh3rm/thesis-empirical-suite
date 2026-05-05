# Batch summary

## Batch headlines
- total_runs_seen: 180
- total_runs_aggregated: 180
- total_runs_failed_or_incomplete: 0
- total_scenarios: 18
- highest_variance_scenario: required_effect__transient_immediate__duplicate_pressure__standard
- highest_variance_std: 1.311857
- highest_p99_scenario: required_effect__transient_immediate__duplicate_pressure__extreme
- highest_cluster100_scenario: required_effect__retained_immediate__handling_gap_replayable__standard
- highest_unattained_scenario: required_effect__transient_immediate__handling_gap_replayable__extreme
- highest_residual_backlog_scenario: None

## Included families
- baseline
- duplicate pressure
- duplicate pressure (extreme)
- handling-gap replayable omission
- handling-gap replayable omission (extreme)
- source omission control

## Strongest amplifiers
- largest mean amplification: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (delta_mean_tta=2.501762)
- largest p95 amplification: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (delta_p95=4.541936)
- largest gap-cv amplification: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_gap_cv=26.095714)
- strongest deferred-vs-immediate shape gap: required_effect__retained_deferred__duplicate_pressure__standard [duplicate pressure] (deferred_shape_gap_vs_same_family_abs=4.787026)
- largest bulk-window amplifier: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (delta_bulk_window_25_to_75=2.26362)
- largest upper-bulk-window amplifier: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (delta_upper_bulk_window_75_to_90=0.679963)
- largest late-region-window amplifier: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (delta_late_region_window_75_to_95=0.905855)
- largest tail-window amplifier: required_effect__transient_immediate__source_omission__standard [source omission control] (delta_tail_window_90_to_99=0.749665)
- largest straggler-window amplifier: required_effect__transient_immediate__source_omission__standard [source omission control] (delta_straggler_window_95_to_99=0.742641)
- largest upper-bulk region shift: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (upper_bulk_region_shift=3.976063)
- largest convergence-region shift: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (convergence_region_shift=4.089009)
- largest straggler-region shift: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (straggler_region_shift=4.642091)
- strongest upper-bulk compression: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_upper_bulk_window_75_to_90=-0.889626)
- strongest late-region compression: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_late_region_window_75_to_95=-1.163116)
- strongest tail-window compression: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_tail_window_90_to_99=-0.495308)
- strongest straggler compression: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_straggler_window_95_to_99=-0.221816)
- largest tail-to-bulk shift: required_effect__retained_deferred__handling_gap_replayable__standard [handling-gap replayable omission] (tail_to_bulk_ratio_delta=5.071996)
- largest upper-bulk-to-bulk shift: required_effect__retained_deferred__handling_gap_replayable__standard [handling-gap replayable omission] (upper_bulk_to_bulk_ratio_delta=3.125622)
- strongest tail-without-mean candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (tail_without_mean_score=2.140329)
- largest unattained-case increase: required_effect__transient_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] (delta_unattained_case_count=871.7)
- largest residual backlog indicator: n/a

## Burden redistribution highlights
- strongest synchronized-lateness candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (synchronized_lateness_score=1.594059)
- strongest concentration-sensitive candidate: required_effect__retained_immediate__handling_gap_replayable__standard [handling-gap replayable omission] (concentration_score=3.393492)
- strongest convergence-region candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (convergence_region_score=1.56872)
- strongest upper-bulk displacement candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (upper_bulk_displacement_score=2.248021)
- strongest convergence-over-straggler candidate: required_effect__retained_immediate__source_omission__standard [source omission control] (convergence_vs_straggler_score=0.226287)
- strongest tail-sensitive candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (tail_score=1.175231)
- strongest straggler-sensitive candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (straggler_score=1.779449)
- strongest bulk-stretch candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] (bulk_score=1.427692)

## Candidate findings
- Synchronized lateness leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as mixed burden pattern. This scenario most strongly shifts much of the recovery curve later together.
- Concentration leader: required_effect__retained_immediate__handling_gap_replayable__standard [handling-gap replayable omission] — handling-gap replayable omission currently reads mainly as catch-up surge recovery. This scenario most strongly converts disturbance into concentrated catch-up behaviour.
- Convergence-region leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as mixed burden pattern. This scenario most strongly displaces the late-convergence region relative to the early or main bulk.
- Upper-bulk displacement leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as mixed burden pattern. This scenario most strongly shifts the upper bulk / late recovery body.
- Tail-sensitive candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as mixed burden pattern. This scenario is the strongest current candidate for a true tail-stretch effect, though it should be read alongside convergence-region signals.
- Straggler-sensitive candidate: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as mixed burden pattern. This scenario most strongly affects the strict straggler window (95→99).
- Upper-bulk shift leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as n/a. This scenario most strongly shifts the upper bulk later in the recovery episode.
- Convergence-region shift leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as n/a. This scenario most strongly shifts the late-convergence region later in the recovery episode.
- Straggler-region shift leader: required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] — duplicate pressure (extreme) currently reads mainly as n/a. This scenario most strongly shifts the strict straggler region later.
- Upper-bulk compression leader: required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] — handling-gap replayable omission (extreme) currently reads mainly as n/a. This scenario most strongly compresses the upper bulk while shifting the broader curve.

## How to read the roles
- **Broadly delayed recovery** means much of the attainment curve shifts later together.
- **Catch-up surge recovery** means recovery resumes in a more synchronized burst rather than spreading out smoothly.
- **Late-convergence fragility** means the near-finish region moves more than the average alone would suggest.
- **Straggler-stretch recovery** means the slowest cases stretch more than the rest of the curve.
- **General slowdown** means average recovery time rises without a clearer regional or concentration signature.
- **Mixed burden pattern** means more than one burden type matters at once and no single one dominates cleanly.

## Burden redistribution map
- required_effect__retained_deferred__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed); secondary=broadly delayed recovery (synchronized-lateness dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_deferred__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed); secondary=broadly delayed recovery (synchronized-lateness dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_deferred__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=18.838, timestamp_compression_ratio=0.920, with concentration_score=2.721 outweighing curve-shift scores (sync=1.176, conv=0.242).
- required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=26.096, timestamp_compression_ratio=2.730, with concentration_score=3.224 outweighing curve-shift scores (sync=1.111, conv=0.221).
- required_effect__transient_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant); secondary=n/a (None); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=6.417, timestamp_compression_ratio=7.783, with concentration_score=2.930 outweighing curve-shift scores (sync=0.000, conv=0.000).
- required_effect__retained_deferred__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=13.717, timestamp_compression_ratio=1.411, with concentration_score=2.861 outweighing curve-shift scores (sync=0.560, conv=0.000).
- required_effect__retained_immediate__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant); secondary=general slowdown (mean-dominant); confidence=high
  - burden regions: primary=early recovery body (early_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=18.903, timestamp_compression_ratio=1.987, with concentration_score=3.393 outweighing curve-shift scores (sync=0.605, conv=0.000).
- required_effect__transient_immediate__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant); secondary=broadly delayed recovery (synchronized-lateness dominant); confidence=high
  - burden regions: primary=late recovery body (upper_bulk), secondary=main recovery body (main_bulk)
  - reason: Recovery concentration dominates: gap_cv=12.067, timestamp_compression_ratio=2.501, with concentration_score=2.223 outweighing curve-shift scores (sync=0.198, conv=0.154).
- required_effect__retained_deferred__source_omission__standard [source omission control] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=near-finish region (late_convergence), secondary=main recovery body (main_bulk)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__source_omission__standard [source omission control] => mixed burden pattern (mixed); secondary=late-convergence fragility (convergence-region dominant); confidence=low
  - burden regions: primary=late recovery body (upper_bulk), secondary=near-finish region (late_convergence)
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__source_omission__standard [source omission control] => catch-up surge recovery (concentration-dominant); secondary=straggler-stretch recovery (tail-dominant); confidence=medium
  - burden regions: primary=slowest cases (straggler), secondary=last recovery segment (tail)
  - reason: Recovery concentration dominates: gap_cv=2.718, timestamp_compression_ratio=1.255, with concentration_score=0.863 outweighing curve-shift scores (sync=0.454, conv=0.403).

## Family-role cues
- required_effect__retained_deferred__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed) with broadly delayed recovery (synchronized-lateness dominant) as secondary; confidence=low
  - scores: sync=1.219735, conc=0.0, conv=1.248754, tail=0.959273, straggler=1.387686
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.448887, conc=0.0, conv=1.443232, tail=1.058361, straggler=1.581355
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__duplicate_pressure__extreme [duplicate pressure (extreme)] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.594059, conc=0.0, conv=1.56872, tail=1.175231, straggler=1.779449
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_deferred__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed) with broadly delayed recovery (synchronized-lateness dominant) as secondary; confidence=low
  - scores: sync=1.020088, conc=0.0, conv=1.068948, tail=0.759575, straggler=1.113281
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.256613, conc=0.0, conv=1.252582, tail=0.913767, straggler=1.345789
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__duplicate_pressure__standard [duplicate pressure] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=1.328642, conc=0.010612, conv=1.305314, tail=0.926221, straggler=1.466455
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_deferred__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=1.175933, conc=2.720874, conv=0.242284, tail=0.0, straggler=0.518494
  - reason: Recovery concentration dominates: gap_cv=18.838, timestamp_compression_ratio=0.920, with concentration_score=2.721 outweighing curve-shift scores (sync=1.176, conv=0.242).
- required_effect__retained_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=1.111278, conc=3.224127, conv=0.221203, tail=0.0, straggler=0.281734
  - reason: Recovery concentration dominates: gap_cv=26.096, timestamp_compression_ratio=2.730, with concentration_score=3.224 outweighing curve-shift scores (sync=1.111, conv=0.221).
- required_effect__transient_immediate__handling_gap_replayable__extreme [handling-gap replayable omission (extreme)] => catch-up surge recovery (concentration-dominant) with n/a (None) as secondary; confidence=high
  - scores: sync=0.0, conc=2.93044, conv=0.0, tail=0.0, straggler=0.159652
  - reason: Recovery concentration dominates: gap_cv=6.417, timestamp_compression_ratio=7.783, with concentration_score=2.930 outweighing curve-shift scores (sync=0.000, conv=0.000).
- required_effect__retained_deferred__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=0.560344, conc=2.86135, conv=0.0, tail=0.0, straggler=1.135075
  - reason: Recovery concentration dominates: gap_cv=13.717, timestamp_compression_ratio=1.411, with concentration_score=2.861 outweighing curve-shift scores (sync=0.560, conv=0.000).
- required_effect__retained_immediate__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant) with general slowdown (mean-dominant) as secondary; confidence=high
  - scores: sync=0.604882, conc=3.393492, conv=0.0, tail=0.0, straggler=0.853027
  - reason: Recovery concentration dominates: gap_cv=18.903, timestamp_compression_ratio=1.987, with concentration_score=3.393 outweighing curve-shift scores (sync=0.605, conv=0.000).
- required_effect__transient_immediate__handling_gap_replayable__standard [handling-gap replayable omission] => catch-up surge recovery (concentration-dominant) with broadly delayed recovery (synchronized-lateness dominant) as secondary; confidence=high
  - scores: sync=0.198344, conc=2.223429, conv=0.154294, tail=0.0, straggler=0.230419
  - reason: Recovery concentration dominates: gap_cv=12.067, timestamp_compression_ratio=2.501, with concentration_score=2.223 outweighing curve-shift scores (sync=0.198, conv=0.154).
- required_effect__retained_deferred__source_omission__standard [source omission control] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=0.134682, conc=0.0, conv=0.111635, tail=0.054778, straggler=0.071348
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__retained_immediate__source_omission__standard [source omission control] => mixed burden pattern (mixed) with late-convergence fragility (convergence-region dominant) as secondary; confidence=low
  - scores: sync=0.728419, conc=0.0, conv=0.657561, tail=0.308239, straggler=0.539093
  - reason: No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics.
- required_effect__transient_immediate__source_omission__standard [source omission control] => catch-up surge recovery (concentration-dominant) with straggler-stretch recovery (tail-dominant) as secondary; confidence=medium
  - scores: sync=0.454386, conc=0.863185, conv=0.403005, tail=0.741357, straggler=1.193595
  - reason: Recovery concentration dominates: gap_cv=2.718, timestamp_compression_ratio=1.255, with concentration_score=0.863 outweighing curve-shift scores (sync=0.454, conv=0.403).

## Curve-region cues
- scenarios_with_any_censoring: 5
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
