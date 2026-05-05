from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from batch_utils import ROOT, dump_json, load_suite_defaults, slugify_project_name, timestamped_batch_name, scenario_display_severity, scenario_display_label, scenario_role_tag

PROFILES_ROOT = ROOT / "profiles"
OUTPUT_BATCHES = ROOT / "output" / "batches"
SINGLE_RUN_SCRIPT = ROOT / "scripts" / "execute_single_run.sh"


SUITE_DEFAULTS = load_suite_defaults()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_variant_id(base_id: str, deadline_seconds: float) -> str:
    token = f"{deadline_seconds:.2f}".replace('.', 'p')
    return f"{base_id}__dw_{token}s"


def scenario_to_env(
    scenario: dict[str, Any],
    run_dir: Path,
    repeat_index: int,
    batch_seed: int,
    run_mode: str,
    profile_name: str,
) -> dict[str, str]:
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
        "DEGRADATION_SECONDS": str(scenario.get("disturbance", {}).get("degradation_seconds", 8.0)),
        "DEFERRED_RECONCILIATION_INTERVAL_MS": str(scenario.get("delivery", {}).get("deferred_reconciliation_interval_ms", 250)),
        "SKEWED_TAIL_FRACTION": str(scenario.get("disturbance", {}).get("skewed_tail_fraction", 0.0)),
        "SKEWED_TAIL_EXTRA_DELAY_MS": str(scenario.get("disturbance", {}).get("skewed_tail_extra_delay_ms", 0)),
        "SCENARIO_SEED": str(batch_seed + repeat_index),
        "DEADLINE_WINDOW_SECONDS": str(scenario["runtime"].get("deadline_window_seconds", 0.0)),
        "DUPLICATE_FRACTION": str(scenario.get("disturbance", {}).get("duplicate_fraction", 0.0)),
        "DUPLICATE_DELAY_MS": str(scenario.get("disturbance", {}).get("duplicate_delay_ms", 0)),
        "DUPLICATE_MODE": str(scenario.get("disturbance", {}).get("duplicate_mode", "selected_cases_once")),
        "DUPLICATE_REPEATS": str(scenario.get("disturbance", {}).get("duplicate_repeats", 1)),
        "DUPLICATE_JITTER_MS": str(scenario.get("disturbance", {}).get("duplicate_jitter_ms", 0)),
        "OMISSION_FRACTION": str(scenario.get("disturbance", {}).get("omission_fraction", 0.0)),
        "OMISSION_MODE": str(scenario.get("disturbance", {}).get("omission_mode", "selected_cases_skip")),
        "UPDATES_PER_ENTITY": str(scenario["runtime"].get("updates_per_entity", 1)),
        "STATE_OBSOLETE_REPLAY_FRACTION": str(scenario.get("disturbance", {}).get("state_obsolete_replay_fraction", 0.0)),
        "STATE_OUTAGE_EXPOSED_VERSION": str(scenario.get("disturbance", {}).get("state_outage_exposed_version", scenario["runtime"].get("updates_per_entity", 1))),
        "STATE_OUTAGE_EXPOSED_START_FRACTION": str(scenario.get("disturbance", {}).get("state_outage_exposed_start_fraction", 0.34)),
        "STATE_FORWARD_RESUMPTION_VERSION": str(scenario.get("disturbance", {}).get("state_forward_resumption_version", 0)),
        "TRANSIENT_INTERRUPT_DISCONNECT": str(int(bool(scenario.get("disturbance", {}).get("transient_interrupt_disconnect", False)))),
        "STATE_TRANSIENT_DROP_EXPOSED_LATEST": str(int(bool(scenario.get("disturbance", {}).get("state_transient_drop_exposed_latest", False)))),
        "SCENARIO_ROLE": str(scenario.get("scenario_role", "main_core")),
        "SCENARIO_ROLE_DETAIL": str(scenario_role_tag(str(scenario["family"]), str(scenario["severity"]), str(scenario.get("scenario_role_detail", "")) or None)),
        "SCENARIO_DISPLAY_SEVERITY": str(scenario.get("severity_display", scenario_display_severity(str(scenario["family"]), str(scenario["severity"])))),
        "SCENARIO_DISPLAY_LABEL": str(scenario.get("display_label", scenario_display_label(str(scenario["family"]), str(scenario["severity"]))).replace(" ", "_")),
        "RUN_MODE": run_mode,
        "PROFILE_NAME": profile_name,
    }
    family = scenario["family"]
    if family == "baseline":
        env["DISTURBANCE"] = "none"
    elif family == "degradation":
        env["DISTURBANCE"] = "degradation"
    elif family == "overload_burst":
        env["DISTURBANCE"] = "overload_burst"
    elif family == "skewed_tail":
        env["DISTURBANCE"] = "skewed_tail"
    elif (
        family.startswith("interrupt")
        or family == "interruption"
        or family == "backlog_shock"
        or family == "backlog_forward_resume"
        or family == "handling_gap_replayable"
    ):
        env["DISTURBANCE"] = "interruption"
    elif family == "duplicate_pressure":
        env["DISTURBANCE"] = "duplicate_pressure"
    elif family == "omission_pressure" or family == "source_omission":
        env["DISTURBANCE"] = "omission_pressure"
    elif family == "mixed_pressure":
        env["DISTURBANCE"] = "mixed_pressure"
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
    profile = load_json(PROFILES_ROOT / f"{profile_name}.json")
    profile.setdefault("profile_version", SUITE_DEFAULTS.get("profile_version", "6.4"))
    profile.setdefault("run_mode", "evidence")
    return profile


def determine_main_deadline(profile: dict[str, Any], deadline_override_seconds: float | None) -> float | None:
    if deadline_override_seconds is not None:
        return float(deadline_override_seconds)
    selected = profile.get("selected_deadline_window_seconds")
    if selected is not None:
        return float(selected)
    default = SUITE_DEFAULTS.get("main_deadline_window_seconds")
    return float(default) if default is not None else None


def determine_deadline_candidates(profile: dict[str, Any]) -> list[float] | None:
    candidates = profile.get("deadline_candidates_seconds")
    if candidates:
        return [float(v) for v in candidates]
    default = SUITE_DEFAULTS.get("deadline_sweep_window_seconds")
    if default:
        return [float(v) for v in default]
    return None


def collect_scenarios(profile: dict[str, Any], deadline_override_seconds: float | None = None) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    candidates = determine_deadline_candidates(profile) if profile.get("deadline_sweep_profile", False) else None
    effective_override = determine_main_deadline(profile, deadline_override_seconds)
    for rel in profile["scenario_files"]:
        path = ROOT / rel
        base = load_json(path)
        if effective_override is not None and base.get("boundary_type") == "deadline_constrained":
            base = deepcopy(base)
            base["runtime"] = deepcopy(base.get("runtime", {}))
            base["runtime"]["deadline_window_seconds"] = float(effective_override)
            base["base_scenario_id"] = base.get("base_scenario_id", base["scenario_id"])
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
    effective_repeat_count = int(profile.get("repeat_count", SUITE_DEFAULTS.get("full_repeat_count", 5)))
    dump_json(
        batch_dir / "batch_meta.json",
        {
            "profile_name": profile_name,
            "batch_dir": str(batch_dir),
            "repeat_count": effective_repeat_count,
            "boundary_types": profile.get("boundary_types", ["required_effect"]),
            "plot_default": profile.get("plot_default", True),
            "scenario_file_count": len(profile["scenario_files"]),
            "scenarios": profile["scenario_files"],
            "seed": profile.get("seed", 1000),
            "selected_deadline_window_seconds": determine_main_deadline(profile, deadline_override_seconds),
            "deadline_window_override_seconds": deadline_override_seconds,
            "deadline_candidates_seconds": determine_deadline_candidates(profile) if profile.get("deadline_sweep_profile", False) else profile.get("deadline_candidates_seconds"),
            "deadline_calibration_profile": profile.get("deadline_calibration_profile", False),
            "deadline_sweep_profile": profile.get("deadline_sweep_profile", False),
            "profile_version": profile.get("profile_version", SUITE_DEFAULTS.get("profile_version", "6.4")),
            "suite_role": profile.get("suite_role", "main_core"),
            "run_mode": profile.get("run_mode", "evidence"),
            "suite_defaults": SUITE_DEFAULTS,
            "expected_run_count": len(collect_scenarios(profile, deadline_override_seconds=deadline_override_seconds)) * effective_repeat_count,
        },
    )
    return batch_dir


def run_profile(profile_name: str, with_plot: bool = False, deadline_window_seconds: float | None = None) -> Path:
    profile = expand_profile(profile_name)
    scenarios = collect_scenarios(profile, deadline_override_seconds=deadline_window_seconds)
    batch_dir = create_batch(profile_name, profile, deadline_override_seconds=deadline_window_seconds)
    raw_runs_dir = batch_dir / "raw_runs"
    repeat_count = int(profile.get("repeat_count", SUITE_DEFAULTS.get("full_repeat_count", 5)))
    run_mode = str(profile.get("run_mode", "evidence"))
    print(f"[run_profile] profile={profile_name} batch={batch_dir} run_mode={run_mode}")
    effective_deadline = determine_main_deadline(profile, deadline_window_seconds)
    if effective_deadline is not None and not profile.get("deadline_sweep_profile", False):
        print(f"[run_profile] deadline_window_seconds={effective_deadline}")
    elif profile.get("deadline_sweep_profile", False):
        print(f"[run_profile] deadline_candidates_seconds={determine_deadline_candidates(profile)}")
    plan_rows: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []
    for scenario in scenarios:
        for repeat_index in range(1, repeat_count + 1):
            run_dir = make_run_dir(raw_runs_dir, scenario["scenario_id"], repeat_index)
            env_map = scenario_to_env(scenario, run_dir, repeat_index, profile.get("seed", 1000), run_mode, profile_name)
            write_env_file(run_dir / "scenario.env", env_map)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "render_run_spec.py"), str(run_dir / "scenario.env"), str(run_dir / "scenario.rendered.json")], check=True)
            plan_rows.append({
                "run_dir": str(run_dir),
                "scenario_id": scenario["scenario_id"],
                "base_scenario_id": scenario.get("base_scenario_id", scenario["scenario_id"]),
                "repeat_index": repeat_index,
                "boundary_type": scenario["boundary_type"],
                "configuration": scenario["configuration"],
                "family": scenario["family"],
                "severity": scenario["severity"],
                "scenario_role": scenario.get("scenario_role", "main_core"),
                "run_mode": run_mode,
            })
            completed = subprocess.run([str(SINGLE_RUN_SCRIPT), str(run_dir)], cwd=str(ROOT), check=False)
            if completed.returncode != 0:
                failed_runs.append({
                    "run_dir": str(run_dir),
                    "scenario_id": scenario["scenario_id"],
                    "repeat_index": repeat_index,
                    "return_code": completed.returncode,
                })
    dump_json(batch_dir / "execution_plan.json", plan_rows)
    dump_json(batch_dir / "execution_failures.json", failed_runs)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "aggregate_batch.py"), str(batch_dir)], check=True)
    if profile.get("deadline_calibration_profile", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "deadline_calibration_analysis.py"), str(batch_dir)], check=True)
    if profile.get("deadline_sweep_profile", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "deadline_sweep_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_recovery_phase_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "recovery_phase_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_placement_signature_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "placement_signature_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_unresolved_correctness_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "unresolved_correctness_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_burden_conversion_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "burden_conversion_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_state_non_regression_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "state_non_regression_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_state_non_regression_spotcheck", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "state_non_regression_spotcheck.py"), str(batch_dir)], check=True)
    if profile.get("run_required_effect_focus_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "required_effect_focus_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_required_effect_guideline_analysis", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "required_effect_guideline_analysis.py"), str(batch_dir)], check=True)
    if profile.get("run_required_effect_pattern_validation", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "required_effect_pattern_validation.py"), str(batch_dir)], check=True)
    if profile.get("run_required_effect_clean_validation", False):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "required_effect_clean_validation.py"), str(batch_dir)], check=True)
    if len(profile.get("boundary_types", [])) > 1:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "cross_boundary_analysis.py"), str(batch_dir)], check=True)
    if failed_runs:
        print(f"[run_profile] warning: {len(failed_runs)} runs failed or timed out; aggregates cover completed runs only", file=sys.stderr)
    if with_plot:
        plot_completed = subprocess.run([sys.executable, str(ROOT / "scripts" / "plot_batch.py"), str(batch_dir)], check=False)
        if plot_completed.returncode != 0:
            print(f"[run_profile] plotting step failed for batch {batch_dir}; raw runs and aggregates were still produced", file=sys.stderr)
    print(batch_dir)
    if failed_runs:
        raise SystemExit(f"Profile completed with {len(failed_runs)} failed runs. See {batch_dir / 'execution_failures.json'}")
    return batch_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_name")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument("--deadline-window-seconds", type=float, default=None)
    args = parser.parse_args()
    run_profile(args.profile_name, with_plot=args.plot, deadline_window_seconds=args.deadline_window_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
