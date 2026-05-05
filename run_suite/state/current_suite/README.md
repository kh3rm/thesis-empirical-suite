# State Suite

This directory contains the canonical runnable state-oriented suite used for the thesis rerun path.

## Run

```bash
./run_profile.sh state_n10
```

Optional plotting:

```bash
./run_profile.sh state_n10 --plot
```

## Cases

- `backlog shock`
- `forward resume`

The state suite compares:

- `transient/immediate`
- `retained/immediate`

The canonical profile runs `4` scenario cells with `10` repeats each.

## Outputs

Each rerun writes a fresh batch under `output/batches/`.
Start in the batch `aggregates/` folder and read:

- `state_non_regression_points.csv`
- `state_non_regression_configuration_gaps.csv`
