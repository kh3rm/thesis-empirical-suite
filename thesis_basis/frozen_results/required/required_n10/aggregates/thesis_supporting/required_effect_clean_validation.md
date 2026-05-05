# Required-effect clean validation

This report isolates required-effect semantics into replayable handling omissions, duplicate consolidation, and non-replayable source omission control.

- overall_status: pass

## Claim statuses
- C1 replay recovers handling-gap omissions: pass
- C2 deferred consolidates duplicate side effects: pass
- C3 source omission is outside replay scope: pass
- C4 deferred adds settlement cost: pass

## C1 handling-gap rows
- standard: transient=598.800, retained_immediate=0.000, retained_deferred=0.000, delta_ti_ri=598.800, delta_ti_rd=598.800
- extreme: transient=871.700, retained_immediate=0.000, retained_deferred=0.000, delta_ti_ri=871.700, delta_ti_rd=871.700

## C2 duplicate rows
- standard: best_immediate=800.000, deferred=15.200, relief_ratio=0.981, rewrite=784.800
- extreme: best_immediate=1400.000, deferred=24.600, relief_ratio=0.982, rewrite=1375.400

## C3 source omission rows
- standard: transient=200.100, retained_immediate=200.000, retained_deferred=200.000, spread=0.100

## C4 deferred-cost rows
- duplicate_pressure | standard: lag_delta=0.105s, reconciliation_delta=33.200, rd_reconciliation=33.200
- duplicate_pressure | extreme: lag_delta=0.060s, reconciliation_delta=37.200, rd_reconciliation=37.200
- handling_gap_replayable | standard: lag_delta=0.112s, reconciliation_delta=10.100, rd_reconciliation=10.100
- handling_gap_replayable | extreme: lag_delta=0.141s, reconciliation_delta=5.100, rd_reconciliation=5.100
