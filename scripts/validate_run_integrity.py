from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def producer_epoch_range(path: Path) -> tuple[float, float] | None:
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        values = [float(row["produced_at_epoch"]) for row in reader if row.get("produced_at_epoch")]
    if not values:
        return None
    return min(values), max(values)


def outcome_epoch_range(path: Path) -> tuple[float, float] | None:
    if not path.exists():
        return None
    values: list[float] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        produced_at_epoch = payload.get("produced_at_epoch")
        if produced_at_epoch is not None:
            values.append(float(produced_at_epoch))
    if not values:
        return None
    return min(values), max(values)


def append_failure(failures: list[str], message: str) -> None:
    failures.append(message)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: validate_run_integrity.py <run_dir>")

    run_dir = Path(sys.argv[1]).resolve()
    env_path = run_dir / "scenario.env"
    producer_complete_path = run_dir / "artifacts" / "producer_complete.json"
    consumer_summary_path = run_dir / "logs" / "consumer_summary.json"
    producer_timeline_path = run_dir / "artifacts" / "producer_timeline.csv"
    outcome_log_path = run_dir / "logs" / "outcome.log"
    report_path = run_dir / "artifacts" / "run_integrity.json"

    env = parse_env(env_path)
    producer_complete = load_json(producer_complete_path) if producer_complete_path.exists() else {}
    consumer_summary = load_json(consumer_summary_path) if consumer_summary_path.exists() else {}

    produced_hint = producer_complete.get("produced_case_count", producer_complete.get("produced_event_count"))
    processed_hint = consumer_summary.get("processed_event_count")
    duplicate_fraction = float(env.get("DUPLICATE_FRACTION", "0") or 0.0)
    updates_per_entity = int(env.get("UPDATES_PER_ENTITY", "1") or 1)
    boundary = env.get("BOUNDARY", "")
    family = env.get("FAMILY", "")

    failures: list[str] = []

    allow_extra_processing = duplicate_fraction > 0 or updates_per_entity > 1 or boundary == "state_non_regression" or family == "duplicate_pressure"
    if (
        produced_hint is not None
        and processed_hint is not None
        and not allow_extra_processing
        and int(processed_hint) > int(produced_hint)
    ):
        append_failure(
            failures,
            f"processed_event_count ({processed_hint}) exceeds produced_hint ({produced_hint}) for a non-duplicate single-update run",
        )

    producer_range = producer_epoch_range(producer_timeline_path)
    outcome_range = outcome_epoch_range(outcome_log_path)
    if producer_range is not None and outcome_range is not None:
        producer_min, producer_max = producer_range
        outcome_min, outcome_max = outcome_range
        min_delta = abs(outcome_min - producer_min)
        max_delta = abs(outcome_max - producer_max)
        if max(min_delta, max_delta) > 60.0:
            append_failure(
                failures,
                "produced_at_epoch values in outcome.log are not coherent with producer_timeline.csv "
                f"(min_delta={min_delta:.3f}s, max_delta={max_delta:.3f}s)",
            )

    status = "ok" if not failures else "failed"
    report = {
        "run_dir": str(run_dir),
        "status": status,
        "produced_hint": produced_hint,
        "processed_hint": processed_hint,
        "producer_epoch_range": producer_range,
        "outcome_epoch_range": outcome_range,
        "failures": failures,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
