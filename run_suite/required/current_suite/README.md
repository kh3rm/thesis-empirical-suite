# Required Suite

This directory contains the canonical runnable required-effect suite used for the thesis rerun path.

## Run

```bash
./run_profile.sh required_n10
```

Optional plotting:

```bash
./run_profile.sh required_n10 --plot
```

## Cases

- `baseline`
- `handling gap`
- `duplicate pressure`
- `source omission`

Each case is run across the handling configurations included in the thesis package.
The canonical profile runs `18` scenario cells with `10` repeats each.

## Outputs

Each rerun writes a fresh batch under `output/batches/`.
Start in the batch `aggregates/` folder and read:

- `required_effect_clean_matrix.csv`
- `scenario_repeat_summary.csv`

To rebuild the required-effect figure pack from an existing batch:

```bash
./build_required_effect_clean_figure_pack.sh <batch_dir> [output_pdf]
```
