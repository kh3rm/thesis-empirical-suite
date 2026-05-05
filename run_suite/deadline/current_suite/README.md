# Deadline Suite

This directory contains the canonical runnable deadline suite used for the thesis rerun path.

## Run

```bash
./run_profile.sh deadline_n10
```

Optional plotting:

```bash
./run_profile.sh deadline_n10 --plot
```

## Cases

- `baseline`
- `degradation moderate`
- `degradation high`
- `backlog shock`

Each case is run across:

- `transient/immediate`
- `retained/immediate`
- `retained/deferred`

The canonical profile runs `12` scenario cells with `10` repeats each.

## Outputs

Each rerun writes a fresh batch under `output/batches/`.
Start in the batch `aggregates/` folder and read:

- `family_comparison_summary.csv`
- `scenario_repeat_summary.csv`
- `deadline_runtime_semantic_summary.csv`
