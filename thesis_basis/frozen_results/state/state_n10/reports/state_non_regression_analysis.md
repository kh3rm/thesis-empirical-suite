# State non-regression analysis

- scenario points: 4
- configurations: retained_immediate, transient_immediate
- families: backlog_forward_resume, backlog_shock

## Headlines
- highest latest-state attainment: state_non_regression__retained_immediate__backlog_forward_resume__standard (1.000000)
- lowest latest-state attainment: state_non_regression__transient_immediate__backlog_shock__standard (0.350000)
- strongest obsolete-suppression load: state_non_regression__retained_immediate__backlog_shock__standard (0.090909)
- slowest p95 attainment: state_non_regression__retained_immediate__backlog_forward_resume__standard (8.512306s)
- largest retained-vs-transient omission gap: backlog_shock (0.650000)

## Notes
- expected_exposed is the producer-defined latest-version slice inside the configured outage window.
- seen_exposed is the portion of that slice actually observed by the consumer.
- loss_count = unseen_exposed + explicit_drop_count. This is the stable cross-configuration measure of outage-slice loss.

## Family summary
- backlog_shock_+_forward_resume: attainment=1.000000, omission=0.000000, obsolete_suppression=0.069767, expected_exposed=195.000, seen_exposed=195.000, seen_fraction=1.000000, unseen=0.000, drop_count=97.500, drop_fraction=0.500000, loss_count=97.500, loss_fraction=0.500000, forward_version=4.000, forward_resumption_count=195.000, forward_adequacy=1.000000, forward_after_loss_rate=0.500000, mean_tta=7.664015s, p95_tta=8.510486s
- backlog_shock: attainment=0.675000, omission=0.325000, obsolete_suppression=0.045455, expected_exposed=195.000, seen_exposed=105.000, seen_fraction=0.538462, unseen=90.000, drop_count=7.500, drop_fraction=0.038462, loss_count=97.500, loss_fraction=0.500000, forward_version=0.000, forward_resumption_count=0.000, forward_adequacy=0.000000, forward_after_loss_rate=0.000000, mean_tta=6.028577s, p95_tta=6.752237s

## Retained vs transient configuration gaps
- backlog_shock: transient_omission=0.650000, retained_omission=0.000000, omission_gap=0.650000, transient_expected=195.000, retained_expected=195.000, transient_seen=15.000, retained_seen=195.000, transient_unseen=180.000, retained_unseen=0.000, transient_drop_count=15.000, retained_drop_count=0.000, transient_loss_count=195.000, retained_loss_count=0.000, transient_loss_fraction=1.000000, retained_loss_fraction=0.000000, transient_forward_resumption=0.000000, retained_forward_resumption=0.000000, transient_after_loss_forward=0.000000, retained_after_loss_forward=0.000000, transient_attainment=0.350000, retained_attainment=1.000000
- backlog_shock_+_forward_resume: transient_omission=0.000000, retained_omission=0.000000, omission_gap=0.000000, transient_expected=195.000, retained_expected=195.000, transient_seen=195.000, retained_seen=195.000, transient_unseen=0.000, retained_unseen=0.000, transient_drop_count=195.000, retained_drop_count=0.000, transient_loss_count=195.000, retained_loss_count=0.000, transient_loss_fraction=1.000000, retained_loss_fraction=0.000000, transient_forward_resumption=1.000000, retained_forward_resumption=1.000000, transient_after_loss_forward=1.000000, retained_after_loss_forward=0.000000, transient_attainment=1.000000, retained_attainment=1.000000
