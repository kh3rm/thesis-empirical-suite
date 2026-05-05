# Thesis Empirical Suite

**Companion repository for the thesis**
*Reliability in Event-Driven Design: How Correctness Boundaries Shape Process-Handling Choices and Recovery Behaviour*

This repository contains the canonical runnable suites, the frozen thesis results, the thesis-used figures, and the thesis PDF.
It provides the compact empirical basis for the thesis: run the suites, inspect the aggregate CSVs, and compare fresh outputs with the frozen results.

## Package Layout

| Path | Contents |
| --- | --- |
| `run_suite/` | Runnable profiles for the three thesis modules. |
| `thesis_basis/frozen_results/` | Frozen result batches used as the thesis evidence base. |
| `thesis_basis/figures/` | Thesis-used figures. |
| `thesis_basis/tables/` | Small CSV tables used for follow-up checks. |
| `thesis_basis/thesis.pdf` | The thesis PDF. |
| `scripts/` | Rerun and comparison helpers. |
| `verification_reports/` | Generated validation reports. |

## Suite Layout

| Module | Cases |
| --- | --- |
| Deadline | baseline, degradation moderate, degradation high, backlog shock |
| Required | baseline, handling gap, duplicate pressure, source omission |
| State | backlog shock, forward resume |

Across the package, the handling configurations are `transient/immediate`, `retained/immediate`, and `retained/deferred`; the state suite uses the first two.

## Prerequisites

`python3` and Docker with Compose support are required to run the suite.
If `python3` is not already installed, install it with your system package manager first, for example `sudo apt install python3` on Ubuntu or `brew install python` on macOS.
If Docker is not already installed, install Docker for your system and verify that `docker compose version` works before running the suite.

## Run

Deadline:

```bash
cd run_suite/deadline/current_suite
./run_profile.sh deadline_n10
```

Required:

```bash
cd run_suite/required/current_suite
./run_profile.sh required_n10
```

State:

```bash
cd run_suite/state/current_suite
./run_profile.sh state_n10
```

Each run writes a new batch under `output/batches/`.
Each batch runs in its own isolated Compose project so stale retained state is cleared before a fresh rerun.

## Read

Start in the new batch's `aggregates/` folder.

- Deadline: `family_comparison_summary.csv`, `scenario_repeat_summary.csv`, `deadline_runtime_semantic_summary.csv`
- Required: `required_effect_clean_matrix.csv`
- State: `state_non_regression_points.csv`, `state_non_regression_configuration_gaps.csv`

The frozen thesis basis lives under `thesis_basis/frozen_results/` in the same aggregate format.

## Compare

To rerun the three canonical profiles and compare them against the frozen thesis results:

```bash
./scripts/run_canonical_confirmation.sh
```

The script prints the report path when it finishes.
Fresh rerun outputs and comparison reports are temporary validation artifacts, while `thesis_basis/frozen_results/` remains the thesis evidence base.
