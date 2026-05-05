from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from batch_utils import ROOT, dump_json, slugify_project_name, timestamped_batch_name

PROFILES_ROOT = ROOT / "profiles"
OUTPUT_BATCHES = ROOT / "output" / "batches"
SINGLE_RUN_SCRIPT = ROOT / "scripts" / "execute_single_run.sh"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_variant_id(base_id: str, deadline_seconds: float) -> str:
    token = f"{deadline_seconds:.2f}".replace('.', 'p')
    return f"{base_id}__dw_{token}s"


def scenario_to_env(scenario: dict[str, Any], run_dir: Path, repeat_index: int, batch_seed: int) -> dict[str, str]:
    conf = scenario["configuration"]
    delivery_mode, enforcement_timing = conf.split("_", 1)
    batch_name = run_dir.parent.parent.name
    batch_parts = batch_name.rsplit("_", 2)
    if len(batch_parts) >= 3:
        batch_token = f"{batch_parts[-2].replace('-', '')}_{batch_parts[-1]}"
    else:
        batch_token = batch_name
    env: dict[str, str] = {
        "SCENARIO_ID": scenario["scenario_id"],
        "BASE_SCENARIO_ID": scenario.get("base_scenario_id", scenario["scenario_id"]),
        "BOUNDARY": scenario["boundary_type"],
        "FAMILY": scenario["family"],
        "SEVERITY": scenario["severity"],
        "CONFIGURATION": conf,
        "DELIVERY_MODE": delivery_mode,
        "ENFORCEMENT_TIMING": enforcement_timing,
        "STREAM_KEY": "events",
        "CHANNEL_KEY": "events",
        "REDIS_HOST": "redis",
        "RUN_DIR": "/run",
        "LOGS_DIR": "/run/logs",
        "ARTIFACTS_DIR": "/run/artifacts",
        "PROJECT_NAME": slugify_project_name(f"{scenario['scenario_id']}_{batch_token}_rep{repeat_index:02d}"),
        "RUN_TIMEOUT_SECONDS": str(scenario.get("timeouts", {}).get("run_timeout_seconds", 180)),
        "PRODUCER_START_TIMEOUT_SECONDS": str(scenario.get("timeouts", {}).get("producer_start_timeout_seconds", 45)),
        "PRODUCER_COMPLETE_TIMEOUT_SECONDS": str(scenario.get("timeouts", {}).get("producer_complete_timeout_seconds", 180)),
        "OBSERVATION_WINDOW_SECONDS": str(scenario["runtime"].get("observation_window_seconds", 45)),
        "QUIET_PERIOD_SECONDS": str(scenario["runtime"].get("quiet_period_seconds", 2.0)),
        "EVENT_COUNT": str(scenario["runtime"].get("case_count", 1000)),
        "PRODUCER_START_DELAY_SECONDS": str(scenario["runtime"].get("producer_start_delay_seconds", 1.0)),
        "EVENT_INTERVAL_MS": str(scenario.get("load", {}).get("event_interval_ms", 5)),
        "BASE_EVENT_INTERVAL_MS": str(scenario.get("load", {}).get("base_event_interval_ms", scenario.get("load", {}).get("event_interval_ms", 5))),
        "OVERLOAD_EVENT_INTERVAL_MS": str(scenario.get("load", {}).get("overload_event_interval_ms", scenario.get("load", {}).get("event_interval_ms", 5))),
        "OVERLOAD_START_SECONDS": str(scenario.get("load", {}).get("overload_start_seconds", 0.0)),
        "OVERLOAD_DURATION_SECONDS": str(scenario.get("load", {}).get("overload_duration_seconds", 0.0)),
        "INTERRUPTION_START_DELAY_SECONDS": str(scenario.get("disturbance", {}).get("interruption_start_delay_seconds", 1.5)),
        "INTERRUPTION_START_MODE": str(scenario.get("disturbance", {}).get("interruption_start_mode", "time_seconds")),
        "INTERRUPTION_START_FRACTION": str(scenario.get("disturbance", {}).get("interruption_start_fraction", 0.0)),
        "INTERRUPTION_SECONDS": str(scenario.get("disturbance", {}).get("interruption_duration_seconds", 0.0)),
        "DEGRADATION_DELAY_MS": str(scenario.get("disturbance", {}).get("degradation_delay_ms", 0)),
        "DEGRADATION_RAMP_SECONDS": str(scenario.get("disturbance", {}).get("degradation_ramp_seconds", 0.0)),
        "DEGRADATION_SECONDS": str(scenario.get("disturbance", {}).get("degradation_seconds", 8.0)),
        "DEFERRED_RECONCILIATION_INTERVAL_MS": str(scenario.get("delivery", {}).get("deferred_reconciliation_interval_ms", 250)),
        "SKEWED_TAIL_FRACTION": str(scenario.get("disturbance", {}).get("skewed_tail_fraction", 0.0)),
        "SKEWED_TAIL_EXTRA_DELAY_MS": str(scenario.get("disturbance", {}).get("skewed_tail_extra_delay_ms", 0)),
        "SCENARIO_SEED": str(batch_seed + repeat_index),
        "DEADLINE_WINDOW_SECONDS": str(scenario["runtime"].get("deadline_window_seconds", 0.0)),
    }
    family = scenario["family"]
    if family == "baseline":
        env["DISTURBANCE"] = "none"
    elif family == "degradation":
        env["DISTURBANCE"] = "degradation"
    elif family == "overload_burst":
        env["DISTURBANCE"] = "overload_burst"
    elif family == "backlog_shock":
        interruption_seconds = float(scenario.get("disturbance", {}).get("interruption_duration_seconds", 0.0) or 0.0)
        env["DISTURBANCE"] = "interruption" if interruption_seconds > 0 else "overload_burst"
    elif family == "skewed_tail":
        env["DISTURBANCE"] = "skewed_tail"
    elif family.startswith("interrupt") or family == "interruption":
        env["DISTURBANCE"] = "interruption"
    else:
        env["DISTURBANCE"] = "none"
    return env


def write_env_file(path: Path, env_map: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in env_map.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_run_dir(batch_raw_runs: Path, scenario_id: str, repeat_index: int) -> Path:
    run_dir = batch_raw_runs / f"{scenario_id}__rep{repeat_index:02d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "logs").mkdir(exist_ok=True)
    return run_dir


def expand_profile(profile_name: str) -> dict[str, Any]:
    return load_json(PROFILES_ROOT / f"{profile_name}.json")


def collect_scenarios(
    profile: dict[str, Any],
    deadline_override_seconds: float | None = None,
    case_count_override: int | None = None,
) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    candidates = profile.get("deadline_candidates_seconds")
    effective_override = deadline_override_seconds
    if effective_override is None:
        selected = profile.get("selected_deadline_window_seconds")
        if selected is not None:
            effective_override = float(selected)
    for rel in profile["scenario_files"]:
        path = ROOT / rel
        base = load_json(path)
        if effective_override is not None and base.get("boundary_type") == "deadline_constrained":
            base = deepcopy(base)
            base["runtime"] = deepcopy(base.get("runtime", {}))
            base["runtime"]["deadline_window_seconds"] = float(effective_override)
            base["base_scenario_id"] = base.get("base_scenario_id", base["scenario_id"])
        if case_count_override is not None:
            base = deepcopy(base)
            base["runtime"] = deepcopy(base.get("runtime", {}))
            base["runtime"]["case_count"] = int(case_count_override)
        if candidates and base.get("boundary_type") == "deadline_constrained":
            for candidate in candidates:
                variant = deepcopy(base)
                variant["runtime"] = deepcopy(variant.get("runtime", {}))
                variant["runtime"]["deadline_window_seconds"] = float(candidate)
                variant["base_scenario_id"] = base.get("base_scenario_id", base["scenario_id"])
                variant["scenario_id"] = scenario_variant_id(variant["base_scenario_id"], float(candidate))
                scenarios.append(variant)
        else:
            scenarios.append(base)
    return scenarios


def create_batch(profile_name: str, profile: dict[str, Any], deadline_override_seconds: float | None = None) -> Path:
    batch_dir = OUTPUT_BATCHES / timestamped_batch_name(profile_name)
    (batch_dir / "raw_runs").mkdir(parents=True, exist_ok=True)
    (batch_dir / "aggregates").mkdir(parents=True, exist_ok=True)
    (batch_dir / "plots").mkdir(parents=True, exist_ok=True)
    (batch_dir / "reports").mkdir(parents=True, exist_ok=True)
    dump_json(
        batch_dir / "batch_meta.json",
        {
            "profile_name": profile_name,
            "batch_dir": str(batch_dir),
            "repeat_count": profile["repeat_count"],
            "boundary_types": profile.get("boundary_types", ["required_effect"]),
            "plot_default": profile.get("plot_default", True),
            "scenario_file_count": len(profile["scenario_files"]),
            "scenarios": profile["scenario_files"],
            "seed": profile.get("seed", 1000),
            "selected_deadline_window_seconds": profile.get("selected_deadline_window_seconds"),
            "deadline_window_override_seconds": deadline_override_seconds,
            "deadline_candidates_seconds": profile.get("deadline_candidates_seconds"),
            "deadline_calibration_profile": profile.get("deadline_calibration_profile", False),
        },
    )
    return batch_dir


def run_profile(
    profile_name: str,
    with_plot: bool = False,
    deadline_window_seconds: float | None = None,
    case_count: int | None = None,
) -> Path:
    profile = expand_profile(profile_name)
    scenarios = collect_scenarios(
        profile,
        deadline_override_seconds=deadline_window_seconds,
        case_count_override=case_count,
    )
    batch_dir = create_batch(profile_name, profile, deadline_override_seconds=deadline_window_seconds)
    raw_runs_dir = batch_dir / "raw_runs"
    print(f"[run_profile] profile={profile_name} batch={batch_dir}")
    if deadline_window_seconds is not None:
        print(f"[run_profile] deadline_window_seconds={deadline_window_seconds}")
    elif profile.get("selected_deadline_window_seconds") is not None and not profile.get("deadline_candidates_seconds"):
        print(f"[run_profile] deadline_window_seconds={profile['selected_deadline_window_seconds']} (profile default)")
    if case_count is not None:
        print(f"[run_profile] case_count={case_count}")
    for scenario in scenarios:
        for repeat_index in range(1, profile["repeat_count"] + 1):
            run_dir = make_run_dir(raw_runs_dir, scenario["scenario_id"], repeat_index)
            env_map = scenario_to_env(scenario, run_dir, repeat_index, profile.get("seed", 1000))
            write_env_file(run_dir / "scenario.env", env_map)
            completed = subprocess.run([str(SINGLE_RUN_SCRIPT), str(run_dir)], cwd=str(ROOT), check=False)
            if completed.returncode != 0:
                raise SystemExit(f"Scenario failed: {scenario['scenario_id']} repeat {repeat_index}")
    subprocess.run([sys.executable, str(ROOT / "scripts" / "aggregate_batch.py"), str(batch_dir)], check=True)
    if profile.get("deadline_calibration_profile", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "deadline_calibration_analysis.py"), str(batch_dir)], check=True)
    if len(profile.get("boundary_types", [])) > 1:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "cross_boundary_analysis.py"), str(batch_dir)], check=True)
    if with_plot:
        plot_completed = subprocess.run([sys.executable, str(ROOT / "scripts" / "plot_batch.py"), str(batch_dir)], check=False)
        if plot_completed.returncode != 0:
            print(f"[run_profile] plotting step failed for batch {batch_dir}; raw runs and aggregates were still produced", file=sys.stderr)
    print(batch_dir)
    return batch_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_name")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--deadline-window-seconds", type=float, default=None)
    parser.add_argument("--case-count", type=int, default=None)
    args = parser.parse_args()
    run_profile(
        args.profile_name,
        with_plot=args.plot,
        deadline_window_seconds=args.deadline_window_seconds,
        case_count=args.case_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
