import json
import os
import time
from pathlib import Path
from typing import Optional

import redis


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


REDIS_HOST = env("REDIS_HOST", "redis")
DELIVERY_MODE = env("DELIVERY_MODE", "transient")
ENFORCEMENT_TIMING = env("ENFORCEMENT_TIMING", "immediate")
BOUNDARY = env("BOUNDARY", "required_effect")
DISTURBANCE = env("DISTURBANCE", "none")
STREAM_KEY = env("STREAM_KEY", "events")
CHANNEL_KEY = env("CHANNEL_KEY", "events")
OBSERVATION_WINDOW_SECONDS = float(env("OBSERVATION_WINDOW_SECONDS", "45"))
QUIET_PERIOD_SECONDS = float(env("QUIET_PERIOD_SECONDS", "2.0"))
INTERRUPTION_START_DELAY_SECONDS = float(env("INTERRUPTION_START_DELAY_SECONDS", "1.5"))
INTERRUPTION_START_MODE = env("INTERRUPTION_START_MODE", "time_seconds")
INTERRUPTION_START_FRACTION = float(env("INTERRUPTION_START_FRACTION", "0.0"))
INTERRUPTION_SECONDS = float(env("INTERRUPTION_SECONDS", "5.0"))
# Keep degradation delay as float to allow fine-grained (e.g. 9.5ms) calibration.
DEGRADATION_DELAY_MS = float(env("DEGRADATION_DELAY_MS", "50"))
DEGRADATION_RAMP_SECONDS = float(env("DEGRADATION_RAMP_SECONDS", "0.0"))
DEGRADATION_SECONDS = float(env("DEGRADATION_SECONDS", "8.0"))
DEFERRED_RECONCILIATION_INTERVAL_MS = int(env("DEFERRED_RECONCILIATION_INTERVAL_MS", "250"))
EVENT_COUNT = int(env("EVENT_COUNT", "0"))
DEADLINE_WINDOW_SECONDS = float(env("DEADLINE_WINDOW_SECONDS", "0.0"))
RUNTIME_TRACE_INTERVAL_MS = int(env("RUNTIME_TRACE_INTERVAL_MS", "250"))

RUN_DIR = Path(env("RUN_DIR", "/run"))
LOGS_DIR = Path(env("LOGS_DIR", "/run/logs"))
ARTIFACTS_DIR = Path(env("ARTIFACTS_DIR", "/run/artifacts"))
for path in (RUN_DIR, LOGS_DIR, ARTIFACTS_DIR):
    path.mkdir(parents=True, exist_ok=True)

producer_sentinel = ARTIFACTS_DIR / "producer_complete.json"
producer_progress_file = ARTIFACTS_DIR / "producer_progress.json"
producer_timeline_file = ARTIFACTS_DIR / "producer_timeline.csv"
run_complete = ARTIFACTS_DIR / "run_complete.json"
consumer_summary = LOGS_DIR / "consumer_summary.json"
consumer_log = LOGS_DIR / "consumer.log"
outcome_log = LOGS_DIR / "outcome.log"
metrics_summary = ARTIFACTS_DIR / "metrics_summary.json"
run_report = ARTIFACTS_DIR / "run_report.md"
recovery_shape_summary = ARTIFACTS_DIR / "recovery_shape_summary.json"
runtime_trace_csv = ARTIFACTS_DIR / "runtime_trace.csv"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} consumer {message}"
    print(line, flush=True)
    with consumer_log.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def append_outcome(payload: dict) -> None:
    with outcome_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def resolve_outcome_kind(event: dict, resolved_epoch: float) -> str:
    if BOUNDARY != "deadline_constrained":
        return "completed"
    deadline_at = event.get("deadline_at_epoch")
    if deadline_at is None:
        return "completed_in_time"
    return "completed_in_time" if resolved_epoch <= float(deadline_at) else "expired"


def append_terminal_outcome(*, case_id: int, event_id: int, resolved_at_seconds: float, resolved_epoch: float, source: str, event: dict, outcome_kind: str) -> None:
    append_outcome(
        {
            "case_id": case_id,
            "event_id": event_id,
            "resolved_at_seconds": round(resolved_at_seconds, 6),
            "attained_at_seconds": round(resolved_at_seconds, 6),
            "mode": ENFORCEMENT_TIMING,
            "attainment_source": source,
            "outcome_kind": outcome_kind,
            "boundary": BOUNDARY,
            "deadline_window_seconds": float(event.get("deadline_window_seconds", DEADLINE_WINDOW_SECONDS or 0.0)),
            "deadline_at_epoch": float(event.get("deadline_at_epoch", 0.0)) if event.get("deadline_at_epoch") is not None else None,
            "produced_at_epoch": float(event.get("produced_at_epoch", 0.0)) if event.get("produced_at_epoch") is not None else None,
            "resolved_epoch": round(resolved_epoch, 6),
            "completion_lag_from_production_seconds": round(max(0.0, resolved_epoch - float(event.get("produced_at_epoch", resolved_epoch))), 6) if event.get("produced_at_epoch") is not None else None,
            "extra_processing_delay_ms": int(event.get("extra_processing_delay_ms", 0)),
        }
    )


def bucket_busiest_share(values: list[float], bucket_width_seconds: float, busiest_fraction: float = 0.10) -> float:
    if not values:
        return 0.0
    bucket_counts: dict[int, int] = {}
    for value in values:
        bucket = int(value / bucket_width_seconds)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    counts = sorted(bucket_counts.values(), reverse=True)
    bucket_take = max(1, int(len(counts) * busiest_fraction))
    return sum(counts[:bucket_take]) / len(values)


def rounded_distinct_count(values: list[float], decimals: int) -> int:
    if not values:
        return 0
    return len({round(value, decimals) for value in values})


def inter_attainment_gap_stats(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return 0.0, 0.0
    gaps = [later - earlier for earlier, later in zip(values, values[1:])]
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap <= 0:
        return mean_gap, 0.0
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    stddev = variance ** 0.5
    return mean_gap, stddev / mean_gap


def parse_event(payload: str) -> dict:
    return json.loads(payload)


def read_producer_count_hint() -> Optional[int]:
    if not producer_sentinel.exists():
        return None
    try:
        producer_info = json.loads(producer_sentinel.read_text(encoding="utf-8"))
        return int(producer_info.get("produced_event_count", 0))
    except Exception:
        return None


def read_producer_progress_count() -> Optional[int]:
    if not producer_progress_file.exists():
        return None
    try:
        producer_info = json.loads(producer_progress_file.read_text(encoding="utf-8"))
        return int(producer_info.get("produced_event_count", 0))
    except Exception:
        return None


def read_producer_progress_fraction() -> float:
    if not producer_progress_file.exists():
        return 0.0
    try:
        producer_info = json.loads(producer_progress_file.read_text(encoding="utf-8"))
        fraction = producer_info.get("progress_fraction")
        if fraction is not None:
            return float(fraction)
        produced = float(producer_info.get("produced_event_count", 0))
        event_count = float(producer_info.get("event_count", EVENT_COUNT))
        return 0.0 if event_count <= 0 else produced / event_count
    except Exception:
        return 0.0


def event_extra_delay_seconds(event: dict) -> float:
    return max(0.0, float(event.get("extra_processing_delay_ms", 0)) / 1000.0)


def read_producer_timeline() -> list[dict[str, float | None]]:
    if not producer_timeline_file.exists():
        return []
    rows: list[dict[str, float | None]] = []
    try:
        with producer_timeline_file.open("r", encoding="utf-8") as fh:
            header_seen = False
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                if not header_seen:
                    header_seen = True
                    continue
                parts = line.split(",")
                if len(parts) != 3:
                    continue
                case_id_text, produced_text, deadline_text = parts
                rows.append({
                    "case_id": int(case_id_text),
                    "produced_at_epoch": float(produced_text),
                    "deadline_at_epoch": float(deadline_text) if deadline_text else None,
                })
    except Exception:
        return []
    return rows


def estimate_produced_count() -> int:
    counts = [value for value in [read_producer_count_hint(), read_producer_progress_count(), len(read_producer_timeline())] if value is not None]
    return max(counts) if counts else 0


def compute_runtime_burden_states(*, seen_cases: set[int], now_epoch: float) -> dict[str, int]:
    timeline_rows = read_producer_timeline()
    state_counts = {
        "produced_cases": len(timeline_rows),
        "salvageable": 0,
        "doomed": 0,
        "comfortable": 0,
        "warning": 0,
        "critical": 0,
    }
    if not timeline_rows:
        return state_counts
    for row in timeline_rows:
        case_id = int(row["case_id"])
        if case_id in seen_cases:
            continue
        deadline_at_epoch = row.get("deadline_at_epoch")
        if deadline_at_epoch is None or BOUNDARY != "deadline_constrained":
            state_counts["salvageable"] += 1
            continue
        deadline_at_epoch = float(deadline_at_epoch)
        remaining = deadline_at_epoch - now_epoch
        if remaining <= 0:
            state_counts["doomed"] += 1
            continue
        state_counts["salvageable"] += 1
        produced_at_epoch = row.get("produced_at_epoch")
        if produced_at_epoch is None:
            state_counts["warning"] += 1
            continue
        full_window = max(1e-9, deadline_at_epoch - float(produced_at_epoch))
        slack_fraction = remaining / full_window
        if slack_fraction > 0.50:
            state_counts["comfortable"] += 1
        elif slack_fraction > 0.25:
            state_counts["warning"] += 1
        else:
            state_counts["critical"] += 1
    return state_counts


def reconcile_pending_cases(
    pending_cases: dict[int, dict],
    seen_cases: set[int],
    first_attainment_times: list[float],
    run_started: float,
    deadline_counts: dict[str, int],
    completion_times: list[float],
    expiry_times: list[float],
) -> tuple[int, int, int, int]:
    if not pending_cases:
        return 0, 0, 0, 0

    reconciled = 0
    newly_attained = 0
    delayed_cases = 0
    pending_ids = sorted(pending_cases.keys())
    pending_before = len(pending_ids)
    for case_id in pending_ids:
        item = pending_cases.pop(case_id)
        event_id = int(item["event_id"])
        extra_delay = event_extra_delay_seconds(item)
        if extra_delay > 0:
            delayed_cases += 1
            time.sleep(extra_delay)
        reconciled += 1
        if case_id in seen_cases:
            continue
        seen_cases.add(case_id)
        newly_attained += 1
        resolved_epoch = time.time()
        attained_at = resolved_epoch - run_started
        first_attainment_times.append(attained_at)
        outcome_kind = resolve_outcome_kind(item, resolved_epoch)
        if outcome_kind == "completed_in_time":
            completion_times.append(attained_at)
            deadline_counts["completed_in_time"] += 1
        elif outcome_kind == "expired":
            expiry_times.append(attained_at)
            deadline_counts["expired"] += 1
        append_terminal_outcome(case_id=case_id, event_id=event_id, resolved_at_seconds=attained_at, resolved_epoch=resolved_epoch, source="periodic_reconciliation", event=item, outcome_kind=outcome_kind)

    log(
        f"reconciliation_pass pending_before={pending_before} reconciled={reconciled} newly_attained={newly_attained} delayed_cases={delayed_cases}"
    )
    return reconciled, newly_attained, pending_before, delayed_cases


def maybe_apply_disturbance(
    run_started: float,
    interruption_state: dict,
) -> None:
    elapsed = time.time() - run_started
    if DISTURBANCE == "degradation" and elapsed <= DEGRADATION_SECONDS and DEGRADATION_DELAY_MS > 0:
        effective_delay_ms = DEGRADATION_DELAY_MS
        if DEGRADATION_RAMP_SECONDS > 0:
            scale = max(0.0, min(1.0, elapsed / DEGRADATION_RAMP_SECONDS))
            effective_delay_ms = DEGRADATION_DELAY_MS * scale
        if effective_delay_ms > 0:
            time.sleep(effective_delay_ms / 1000.0)
        return
    if DISTURBANCE != "interruption" or interruption_state["applied"]:
        return

    should_interrupt = False
    trigger_reason = None
    trigger_fraction = 0.0
    if INTERRUPTION_START_MODE == "progress_fraction":
        trigger_fraction = read_producer_progress_fraction()
        if trigger_fraction >= INTERRUPTION_START_FRACTION > 0:
            should_interrupt = True
            trigger_reason = f"progress_fraction>={INTERRUPTION_START_FRACTION}"
    else:
        if elapsed >= INTERRUPTION_START_DELAY_SECONDS:
            should_interrupt = True
            trigger_reason = f"elapsed_seconds>={INTERRUPTION_START_DELAY_SECONDS}"

    if should_interrupt:
        interruption_state["applied"] = True
        interruption_state["trigger_elapsed_seconds"] = round(elapsed, 6)
        interruption_state["trigger_progress_fraction"] = round(trigger_fraction, 6)
        interruption_state["trigger_reason"] = trigger_reason
        log(
            f"interruption_active mode={INTERRUPTION_START_MODE} reason={trigger_reason} duration={INTERRUPTION_SECONDS:.3f} trigger_elapsed={elapsed:.3f} trigger_fraction={trigger_fraction:.3f}"
        )
        time.sleep(max(0.0, INTERRUPTION_SECONDS))



def current_disturbance_active(elapsed: float, interruption_state: dict) -> bool:
    if DISTURBANCE == "degradation":
        return elapsed <= DEGRADATION_SECONDS
    if DISTURBANCE == "interruption" and interruption_state.get("applied") and interruption_state.get("trigger_elapsed_seconds") is not None:
        start = float(interruption_state["trigger_elapsed_seconds"])
        return start <= elapsed <= (start + INTERRUPTION_SECONDS)
    return False


def write_runtime_trace_header(path: Path) -> None:
    path.write_text(
        "t_sec,produced_total,produced_progress_fraction,attained_total,completed_in_time_total,expired_total,unresolved_cases,unresolved_share,salvageable_unsettled_cases,salvageable_unsettled_share,doomed_unsettled_cases,doomed_unsettled_share,comfortable_slack_cases,comfortable_slack_share,warning_slack_cases,warning_slack_share,critical_slack_cases,critical_slack_share,active_settlement_cases,active_settlement_share,pending_cases,retained_backlog_cases,retained_backlog_share,disturbance_active,configured_delay_ms,configured_ramp_seconds,effective_delay_ms_current,consumer_pause_configured_seconds\n",
        encoding="utf-8",
    )


def sample_runtime_trace(path: Path, run_started: float, attained: int, pending_cases: dict[int, dict], retained_buffer: list[dict], deadline_counts: dict[str, int], interruption_state: dict, seen_cases: set[int]) -> None:
    elapsed = time.time() - run_started
    progress_fraction = read_producer_progress_fraction()
    produced_hint = estimate_produced_count()
    unresolved_cases = max(0, produced_hint - attained)
    unresolved_share = 0.0 if produced_hint <= 0 else unresolved_cases / produced_hint
    state_counts = compute_runtime_burden_states(seen_cases=seen_cases, now_epoch=time.time())
    salvageable_unsettled_cases = int(state_counts.get("salvageable", 0))
    doomed_unsettled_cases = int(state_counts.get("doomed", 0))
    comfortable_slack_cases = int(state_counts.get("comfortable", 0))
    warning_slack_cases = int(state_counts.get("warning", 0))
    critical_slack_cases = int(state_counts.get("critical", 0))
    burden_total = salvageable_unsettled_cases + doomed_unsettled_cases
    if burden_total > unresolved_cases and unresolved_cases > 0:
        scale = unresolved_cases / burden_total
        comfortable_scaled = int(round(comfortable_slack_cases * scale))
        warning_scaled = int(round(warning_slack_cases * scale))
        critical_scaled = int(round(critical_slack_cases * scale))
        salvageable_scaled = comfortable_scaled + warning_scaled + critical_scaled
        if salvageable_scaled > unresolved_cases:
            overflow = salvageable_scaled - unresolved_cases
            critical_scaled = max(0, critical_scaled - overflow)
            salvageable_scaled = comfortable_scaled + warning_scaled + critical_scaled
        comfortable_slack_cases = comfortable_scaled
        warning_slack_cases = warning_scaled
        critical_slack_cases = critical_scaled
        salvageable_unsettled_cases = salvageable_scaled
        doomed_unsettled_cases = max(0, unresolved_cases - salvageable_unsettled_cases)
    elif produced_hint <= 0:
        salvageable_unsettled_cases = 0
        doomed_unsettled_cases = 0
        comfortable_slack_cases = 0
        warning_slack_cases = 0
        critical_slack_cases = 0
    salvageable_unsettled_share = 0.0 if produced_hint <= 0 else salvageable_unsettled_cases / produced_hint
    doomed_unsettled_share = 0.0 if produced_hint <= 0 else doomed_unsettled_cases / produced_hint
    comfortable_slack_share = 0.0 if produced_hint <= 0 else comfortable_slack_cases / produced_hint
    warning_slack_share = 0.0 if produced_hint <= 0 else warning_slack_cases / produced_hint
    critical_slack_share = 0.0 if produced_hint <= 0 else critical_slack_cases / produced_hint
    active_settlement_cases = max(0, salvageable_unsettled_cases - len(retained_buffer))
    active_settlement_share = 0.0 if produced_hint <= 0 else active_settlement_cases / produced_hint
    retained_backlog_share = 0.0 if produced_hint <= 0 else len(retained_buffer) / produced_hint
    effective_delay_ms_current = 0.0
    if DISTURBANCE == "degradation":
        if DEGRADATION_RAMP_SECONDS > 0:
            scale = max(0.0, min(1.0, elapsed / DEGRADATION_RAMP_SECONDS))
            effective_delay_ms_current = DEGRADATION_DELAY_MS * scale
        else:
            effective_delay_ms_current = DEGRADATION_DELAY_MS
    row = {
        "t_sec": round(elapsed, 6),
        "produced_total": produced_hint,
        "produced_progress_fraction": round(progress_fraction, 6),
        "attained_total": attained,
        "completed_in_time_total": int(deadline_counts.get("completed_in_time", 0)),
        "expired_total": int(deadline_counts.get("expired", 0)),
        "unresolved_cases": unresolved_cases,
        "unresolved_share": round(unresolved_share, 6),
        "salvageable_unsettled_cases": salvageable_unsettled_cases,
        "salvageable_unsettled_share": round(salvageable_unsettled_share, 6),
        "doomed_unsettled_cases": doomed_unsettled_cases,
        "doomed_unsettled_share": round(doomed_unsettled_share, 6),
        "comfortable_slack_cases": comfortable_slack_cases,
        "comfortable_slack_share": round(comfortable_slack_share, 6),
        "warning_slack_cases": warning_slack_cases,
        "warning_slack_share": round(warning_slack_share, 6),
        "critical_slack_cases": critical_slack_cases,
        "critical_slack_share": round(critical_slack_share, 6),
        "active_settlement_cases": active_settlement_cases,
        "active_settlement_share": round(active_settlement_share, 6),
        "pending_cases": len(pending_cases),
        "retained_backlog_cases": len(retained_buffer),
        "retained_backlog_share": round(retained_backlog_share, 6),
        "disturbance_active": 1 if current_disturbance_active(elapsed, interruption_state) else 0,
        "configured_delay_ms": round(DEGRADATION_DELAY_MS, 3) if DISTURBANCE == "degradation" else 0.0,
        "configured_ramp_seconds": round(DEGRADATION_RAMP_SECONDS, 3) if DISTURBANCE == "degradation" else 0.0,
        "effective_delay_ms_current": round(effective_delay_ms_current, 3),
        "consumer_pause_configured_seconds": INTERRUPTION_SECONDS if DISTURBANCE == "interruption" else 0.0,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"{row['t_sec']},{row['produced_total']},{row['produced_progress_fraction']},{row['attained_total']},{row['completed_in_time_total']},{row['expired_total']},{row['unresolved_cases']},{row['unresolved_share']},{row['salvageable_unsettled_cases']},{row['salvageable_unsettled_share']},{row['doomed_unsettled_cases']},{row['doomed_unsettled_share']},{row['comfortable_slack_cases']},{row['comfortable_slack_share']},{row['warning_slack_cases']},{row['warning_slack_share']},{row['critical_slack_cases']},{row['critical_slack_share']},{row['active_settlement_cases']},{row['active_settlement_share']},{row['pending_cases']},{row['retained_backlog_cases']},{row['retained_backlog_share']},{row['disturbance_active']},{row['configured_delay_ms']},{row['configured_ramp_seconds']},{row['effective_delay_ms_current']},{row['consumer_pause_configured_seconds']}\n"
        )

def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    idx = max(0, min(len(values) - 1, int((len(values) - 1) * q)))
    return values[idx]


def main() -> int:
    client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    run_started = time.time()
    last_activity = run_started
    processed = 0
    attained = 0
    first_attainment_times: list[float] = []
    completion_times: list[float] = []
    expiry_times: list[float] = []
    deadline_counts = {"completed_in_time": 0, "expired": 0}
    seen_cases: set[int] = set()
    pending_cases: dict[int, dict] = {}
    retained_buffer: list[dict] = []
    last_stream_id = "0-0"
    produced_count_hint: Optional[int] = None
    producer_complete_seen_elapsed_seconds: Optional[float] = None
    observation_window_expired = False
    status = "complete"
    error_text: Optional[str] = None
    next_reconciliation_at = run_started + (DEFERRED_RECONCILIATION_INTERVAL_MS / 1000.0)
    reconciliation_pass_count = 0
    reconciliation_cases_seen = 0
    reconciliation_attainment_passes = 0
    reconciliation_delayed_cases = 0
    interruption_state = {
        "applied": False,
        "trigger_elapsed_seconds": None,
        "trigger_progress_fraction": None,
        "trigger_reason": None,
    }
    write_runtime_trace_header(runtime_trace_csv)
    next_runtime_trace_at = run_started

    log(
        f"starting delivery_mode={DELIVERY_MODE} enforcement_timing={ENFORCEMENT_TIMING} boundary={BOUNDARY} disturbance={DISTURBANCE} deferred_interval_ms={DEFERRED_RECONCILIATION_INTERVAL_MS} interruption_start_mode={INTERRUPTION_START_MODE}"
    )

    pubsub = None
    if DELIVERY_MODE == "transient":
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(CHANNEL_KEY)

    try:
        while True:
            elapsed = time.time() - run_started
            if time.time() >= next_runtime_trace_at:
                sample_runtime_trace(runtime_trace_csv, run_started, attained, pending_cases, retained_buffer, deadline_counts, interruption_state, seen_cases)
                next_runtime_trace_at = time.time() + (RUNTIME_TRACE_INTERVAL_MS / 1000.0)
            if elapsed > OBSERVATION_WINDOW_SECONDS:
                observation_window_expired = True
                status = "window_expired"
                log("observation_window_expired")
                break

            maybe_apply_disturbance(run_started, interruption_state)

            now = time.time()
            if ENFORCEMENT_TIMING == "deferred" and pending_cases and now >= next_reconciliation_at:
                reconciled, newly_attained, pending_before, delayed_cases = reconcile_pending_cases(
                    pending_cases=pending_cases,
                    seen_cases=seen_cases,
                    first_attainment_times=first_attainment_times,
                    run_started=run_started,
                    deadline_counts=deadline_counts,
                    completion_times=completion_times,
                    expiry_times=expiry_times,
                )
                processed += reconciled
                attained += newly_attained
                reconciliation_pass_count += 1
                reconciliation_cases_seen += pending_before
                reconciliation_delayed_cases += delayed_cases
                if newly_attained > 0:
                    reconciliation_attainment_passes += 1
                last_activity = time.time()
                next_reconciliation_at = time.time() + (DEFERRED_RECONCILIATION_INTERVAL_MS / 1000.0)
                continue

            event = None
            if DELIVERY_MODE == "retained":
                if retained_buffer:
                    event = retained_buffer.pop(0)
                else:
                    response = client.xread({STREAM_KEY: last_stream_id}, block=100, count=200)
                    if response:
                        _, entries = response[0]
                        for entry_id, data in entries:
                            retained_buffer.append(parse_event(data["payload"]))
                            last_stream_id = entry_id
                    if retained_buffer:
                        event = retained_buffer.pop(0)
            else:
                message = pubsub.get_message(timeout=0.1) if pubsub is not None else None
                if message and message.get("type") == "message":
                    event = parse_event(message["data"])

            if event is not None:
                last_activity = time.time()
                case_id = int(event["case_id"])
                event_id = int(event["event_id"])
                if ENFORCEMENT_TIMING == "deferred":
                    pending_cases[case_id] = event
                    log(f"pending_recorded case_id={case_id} event_id={event_id} pending_count={len(pending_cases)}")
                else:
                    extra_delay = event_extra_delay_seconds(event)
                    if extra_delay > 0:
                        time.sleep(extra_delay)
                    if case_id not in seen_cases:
                        seen_cases.add(case_id)
                        processed += 1
                        attained += 1
                        resolved_epoch = time.time()
                        attained_at = resolved_epoch - run_started
                        first_attainment_times.append(attained_at)
                        outcome_kind = resolve_outcome_kind(event, resolved_epoch)
                        if outcome_kind == "completed_in_time":
                            completion_times.append(attained_at)
                            deadline_counts["completed_in_time"] += 1
                        elif outcome_kind == "expired":
                            expiry_times.append(attained_at)
                            deadline_counts["expired"] += 1
                        append_terminal_outcome(case_id=case_id, event_id=event_id, resolved_at_seconds=attained_at, resolved_epoch=resolved_epoch, source="immediate_handling", event=event, outcome_kind=outcome_kind)
                        log(f"processed case_id={case_id} event_id={event_id} processed={processed}")
                continue

            if producer_sentinel.exists():
                producer_count = read_producer_count_hint()
                if produced_count_hint is None and producer_count is not None:
                    produced_count_hint = producer_count
                    producer_complete_seen_elapsed_seconds = round(time.time() - run_started, 6)
                    log(f"producer_complete_seen produced_hint={produced_count_hint} seen_elapsed={producer_complete_seen_elapsed_seconds}")
                quiet_for = time.time() - last_activity
                if DELIVERY_MODE == "retained":
                    target_reached = produced_count_hint is not None and processed >= produced_count_hint
                else:
                    target_reached = True
                if quiet_for >= QUIET_PERIOD_SECONDS and not retained_buffer and not pending_cases and target_reached:
                    log(
                        f"drain_complete processed={processed} produced_hint={produced_count_hint} quiet_for={quiet_for:.3f}"
                    )
                    status = "complete"
                    break

        sorted_times = sorted(first_attainment_times)
        mean_tta = sum(sorted_times) / len(sorted_times) if sorted_times else 0.0
        p95 = quantile(sorted_times, 0.95)
        p99 = quantile(sorted_times, 0.99)
        p999 = quantile(sorted_times, 0.999)

        busy_share_1s = bucket_busiest_share(sorted_times, 1.0)
        busy_share_250ms = bucket_busiest_share(sorted_times, 0.25)
        busy_share_100ms = bucket_busiest_share(sorted_times, 0.10)
        distinct_timestamps_1ms = rounded_distinct_count(sorted_times, 3)
        distinct_timestamps_10ms = rounded_distinct_count(sorted_times, 2)
        mean_gap, gap_cv = inter_attainment_gap_stats(sorted_times)

        t50 = quantile(sorted_times, 0.50)
        t90 = quantile(sorted_times, 0.90)
        t95 = quantile(sorted_times, 0.95)
        last_attainment_seconds = sorted_times[-1] if sorted_times else 0.0
        if produced_count_hint is None:
            produced_count_hint = read_producer_count_hint()
        produced_total = produced_count_hint if produced_count_hint is not None else 0
        all_cases_attained_within_window = produced_total > 0 and attained == produced_total
        unattained_case_count = max(0, produced_total - attained)
        completed_in_time_count = deadline_counts["completed_in_time"] if BOUNDARY == "deadline_constrained" else attained
        expired_count = deadline_counts["expired"] if BOUNDARY == "deadline_constrained" else 0
        completed_in_time_rate = 0.0 if produced_total == 0 else completed_in_time_count / produced_total
        expired_rate = 0.0 if produced_total == 0 else expired_count / produced_total
        terminal_resolution_rate = 0.0 if produced_total == 0 else (completed_in_time_count + expired_count) / produced_total
        median_time_to_completion_in_time = quantile(sorted(completion_times), 0.50) if completion_times else 0.0
        median_time_to_expiry = quantile(sorted(expiry_times), 0.50) if expiry_times else 0.0
        producer_complete_to_last_attainment_seconds = 0.0
        producer_complete_to_p95_seconds = 0.0
        attained_after_producer_complete_count = 0
        attained_after_producer_complete_share = 0.0
        if producer_complete_seen_elapsed_seconds is not None and sorted_times:
            producer_complete_to_last_attainment_seconds = max(0.0, last_attainment_seconds - producer_complete_seen_elapsed_seconds)
            producer_complete_to_p95_seconds = max(0.0, p95 - producer_complete_seen_elapsed_seconds)
            attained_after_producer_complete_count = sum(1 for v in sorted_times if v >= producer_complete_seen_elapsed_seconds)
            attained_after_producer_complete_share = attained_after_producer_complete_count / len(sorted_times) if sorted_times else 0.0

        recovery_shape = {
            "attained_case_count": len(sorted_times),
            "busiest_interval_share_1s": round(busy_share_1s, 6),
            "busiest_10pct_interval_share_250ms": round(busy_share_250ms, 6),
            "busiest_10pct_interval_share_100ms": round(busy_share_100ms, 6),
            "distinct_attainment_timestamps_1ms": distinct_timestamps_1ms,
            "distinct_attainment_timestamps_10ms": distinct_timestamps_10ms,
            "mean_inter_attainment_gap_ms": round(mean_gap * 1000.0, 6),
            "inter_attainment_gap_cv": round(gap_cv, 6),
            "reconciliation_pass_count": reconciliation_pass_count,
            "reconciliation_attainment_pass_count": reconciliation_attainment_passes,
            "reconciled_case_slots_seen": reconciliation_cases_seen,
            "reconciliation_delayed_cases": reconciliation_delayed_cases,
            "interruption_applied": interruption_state["applied"],
            "interruption_trigger_elapsed_seconds": interruption_state["trigger_elapsed_seconds"],
            "interruption_trigger_progress_fraction": interruption_state["trigger_progress_fraction"],
            "interruption_trigger_reason": interruption_state["trigger_reason"],
            "interruption_start_mode": INTERRUPTION_START_MODE,
            "unattained_case_count": unattained_case_count,
            "observation_window_expired_flag": 1.0 if observation_window_expired else 0.0,
            "all_cases_attained_within_window_flag": 1.0 if all_cases_attained_within_window else 0.0,
            "tta_metrics_censored_flag": 0.0 if all_cases_attained_within_window else 1.0,
            "run_duration_seconds": round(time.time() - run_started, 6),
            "producer_complete_seen_elapsed_seconds": producer_complete_seen_elapsed_seconds or 0.0,
            "last_attainment_seconds": round(last_attainment_seconds, 6),
            "attainment_t50_seconds": round(t50, 6),
            "attainment_t90_seconds": round(t90, 6),
            "attainment_t95_seconds": round(t95, 6),
            "producer_complete_to_last_attainment_seconds": round(producer_complete_to_last_attainment_seconds, 6),
            "producer_complete_to_p95_seconds": round(producer_complete_to_p95_seconds, 6),
            "attained_after_producer_complete_count": attained_after_producer_complete_count,
            "attained_after_producer_complete_share": round(attained_after_producer_complete_share, 6),
            "retained_buffer_remaining": len(retained_buffer),
            "pending_case_count_remaining": len(pending_cases),
            "completed_in_time_count": completed_in_time_count,
            "expired_count": expired_count,
            "completed_in_time_rate": round(completed_in_time_rate, 6),
            "expired_rate": round(expired_rate, 6),
            "terminal_resolution_rate": round(terminal_resolution_rate, 6),
            "median_time_to_completion_in_time": round(median_time_to_completion_in_time, 6),
            "median_time_to_expiry": round(median_time_to_expiry, 6),
            "share_resolved_by_expiry": round(expired_rate, 6),
            "share_resolved_by_completion": round(completed_in_time_rate, 6),
        }
        recovery_shape_summary.write_text(json.dumps(recovery_shape, indent=2), encoding="utf-8")

        sample_runtime_trace(runtime_trace_csv, run_started, attained, pending_cases, retained_buffer, deadline_counts, interruption_state, seen_cases)
        metrics = {
            "status": status,
            "observation_window_expired": observation_window_expired,
            "produced_event_count": produced_total,
            "processed_event_count": processed,
            "produced_case_count": produced_total,
            "attained_case_count": attained,
            "attainment_rate": round(terminal_resolution_rate if BOUNDARY == "deadline_constrained" else (0.0 if produced_total == 0 else attained / produced_total), 6),
            "all_cases_attained_within_window": all_cases_attained_within_window,
            "mean_time_to_attainment_seconds": round(mean_tta, 6),
            "p95_time_to_attainment_seconds": round(p95, 6),
            "p99_time_to_attainment_seconds": round(p99, 6),
            "p999_time_to_attainment_seconds": round(p999, 6),
            "temporal_clustering_busiest_interval_share": round(busy_share_1s, 6),
            "temporal_clustering_busiest_10pct_interval_share_250ms": round(busy_share_250ms, 6),
            "temporal_clustering_busiest_10pct_interval_share_100ms": round(busy_share_100ms, 6),
            "distinct_attainment_timestamps_1ms": distinct_timestamps_1ms,
            "distinct_attainment_timestamps_10ms": distinct_timestamps_10ms,
            "mean_inter_attainment_gap_ms": round(mean_gap * 1000.0, 6),
            "inter_attainment_gap_cv": round(gap_cv, 6),
            "delivery_mode": DELIVERY_MODE,
            "enforcement_timing": ENFORCEMENT_TIMING,
            "disturbance": DISTURBANCE,
            "boundary": BOUNDARY,
            "deferred_reconciliation_interval_ms": DEFERRED_RECONCILIATION_INTERVAL_MS,
            "interruption_start_mode": INTERRUPTION_START_MODE,
            "unattained_case_count": unattained_case_count,
            "observation_window_expired_flag": 1.0 if observation_window_expired else 0.0,
            "all_cases_attained_within_window_flag": 1.0 if all_cases_attained_within_window else 0.0,
            "tta_metrics_censored_flag": 0.0 if all_cases_attained_within_window else 1.0,
            "run_duration_seconds": round(time.time() - run_started, 6),
            "producer_complete_seen_elapsed_seconds": producer_complete_seen_elapsed_seconds or 0.0,
            "last_attainment_seconds": round(last_attainment_seconds, 6),
            "attainment_t50_seconds": round(t50, 6),
            "attainment_t90_seconds": round(t90, 6),
            "attainment_t95_seconds": round(t95, 6),
            "producer_complete_to_last_attainment_seconds": round(producer_complete_to_last_attainment_seconds, 6),
            "producer_complete_to_p95_seconds": round(producer_complete_to_p95_seconds, 6),
            "attained_after_producer_complete_count": attained_after_producer_complete_count,
            "attained_after_producer_complete_share": round(attained_after_producer_complete_share, 6),
            "retained_buffer_remaining": len(retained_buffer),
            "pending_case_count_remaining": len(pending_cases),
            "deadline_window_seconds": DEADLINE_WINDOW_SECONDS,
            "runtime_trace_interval_ms": RUNTIME_TRACE_INTERVAL_MS,
            "completed_in_time_count": completed_in_time_count,
            "expired_count": expired_count,
            "completed_in_time_rate": round(completed_in_time_rate, 6),
            "expired_rate": round(expired_rate, 6),
            "terminal_resolution_rate": round(terminal_resolution_rate, 6),
            "median_time_to_completion_in_time": round(median_time_to_completion_in_time, 6),
            "median_time_to_expiry": round(median_time_to_expiry, 6),
            "share_resolved_by_expiry": round(expired_rate, 6),
            "share_resolved_by_completion": round(completed_in_time_rate, 6),
        }
        metrics_summary.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        consumer_summary.write_text(
            json.dumps(
                {
                    "status": status,
                    "observation_window_expired": observation_window_expired,
                    "processed_event_count": processed,
                    "attained_case_count": attained,
                    "produced_event_count_hint": produced_count_hint,
                    "all_cases_attained_within_window": all_cases_attained_within_window,
                    "pending_case_count_remaining": len(pending_cases),
                    "retained_buffer_remaining": len(retained_buffer),
                    "producer_complete_seen": producer_sentinel.exists(),
                    "duration_seconds": round(time.time() - run_started, 6),
                    "unattained_case_count": unattained_case_count,
                    "tta_metrics_censored_flag": 0.0 if all_cases_attained_within_window else 1.0,
                    "producer_complete_seen_elapsed_seconds": producer_complete_seen_elapsed_seconds or 0.0,
                    "last_attainment_seconds": round(last_attainment_seconds, 6),
                    "attainment_t50_seconds": round(t50, 6),
                    "attainment_t90_seconds": round(t90, 6),
                    "attainment_t95_seconds": round(t95, 6),
                    "producer_complete_to_last_attainment_seconds": round(producer_complete_to_last_attainment_seconds, 6),
                    "producer_complete_to_p95_seconds": round(producer_complete_to_p95_seconds, 6),
                    "attained_after_producer_complete_count": attained_after_producer_complete_count,
                    "attained_after_producer_complete_share": round(attained_after_producer_complete_share, 6),
                    "deferred_reconciliation_interval_ms": DEFERRED_RECONCILIATION_INTERVAL_MS,
                    "reconciliation_pass_count": reconciliation_pass_count,
                    "reconciliation_attainment_pass_count": reconciliation_attainment_passes,
                    "interruption_applied": interruption_state["applied"],
                    "interruption_trigger_elapsed_seconds": interruption_state["trigger_elapsed_seconds"],
                    "interruption_trigger_progress_fraction": interruption_state["trigger_progress_fraction"],
                    "interruption_trigger_reason": interruption_state["trigger_reason"],
                    "interruption_start_mode": INTERRUPTION_START_MODE,
                    "deadline_window_seconds": DEADLINE_WINDOW_SECONDS,
            "runtime_trace_interval_ms": RUNTIME_TRACE_INTERVAL_MS,
                    "completed_in_time_count": completed_in_time_count,
                    "expired_count": expired_count,
                    "completed_in_time_rate": round(completed_in_time_rate, 6),
                    "expired_rate": round(expired_rate, 6),
                    "terminal_resolution_rate": round(terminal_resolution_rate, 6),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        run_report.write_text(
            "\n".join(
                [
                    "# Run report",
                    "",
                    f"- boundary: {BOUNDARY}",
                    f"- delivery_mode: {DELIVERY_MODE}",
                    f"- enforcement_timing: {ENFORCEMENT_TIMING}",
                    f"- disturbance: {DISTURBANCE}",
                    f"- status: {status}",
                    f"- produced_event_count: {produced_total}",
                    f"- processed_event_count: {processed}",
                    f"- attained_case_count: {attained}",
                    f"- all_cases_attained_within_window: {all_cases_attained_within_window}",
                    f"- unattained_case_count: {unattained_case_count}",
                    f"- observation_window_expired: {observation_window_expired}",
                    f"- producer_complete_seen_elapsed_seconds: {producer_complete_seen_elapsed_seconds}",
                    f"- last_attainment_seconds: {round(last_attainment_seconds, 6)}",
                    f"- producer_complete_to_last_attainment_seconds: {round(producer_complete_to_last_attainment_seconds, 6)}",
                    f"- retained_buffer_remaining: {len(retained_buffer)}",
                    f"- pending_case_count_remaining: {len(pending_cases)}",
                    f"- deadline_window_seconds: {DEADLINE_WINDOW_SECONDS}",
                    f"- completed_in_time_count: {completed_in_time_count}",
                    f"- expired_count: {expired_count}",
                    f"- completed_in_time_rate: {round(completed_in_time_rate, 6)}",
                    f"- expired_rate: {round(expired_rate, 6)}",
                    f"- deferred_reconciliation_interval_ms: {DEFERRED_RECONCILIATION_INTERVAL_MS}",
                    f"- interruption_start_mode: {INTERRUPTION_START_MODE}",
                    f"- interruption_applied: {interruption_state['applied']}",
                    f"- interruption_trigger_elapsed_seconds: {interruption_state['trigger_elapsed_seconds']}",
                    f"- interruption_trigger_progress_fraction: {interruption_state['trigger_progress_fraction']}",
                    f"- busiest_10pct_interval_share_250ms: {round(busy_share_250ms, 6)}",
                    f"- busiest_10pct_interval_share_100ms: {round(busy_share_100ms, 6)}",
                    f"- distinct_attainment_timestamps_10ms: {distinct_timestamps_10ms}",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        status = "failed"
        error_text = repr(exc)
        log(f"failed error={error_text}")
        raise
    finally:
        payload = {
            "status": status,
            "error": error_text,
            "producer_complete_seen": producer_sentinel.exists(),
            "observation_window_expired": observation_window_expired,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        run_complete.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log(f"wrote_run_complete status={status}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise
