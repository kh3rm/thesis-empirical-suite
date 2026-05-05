import json
import math
import os
from decimal import Decimal, ROUND_CEILING
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
DEGRADATION_DELAY_MS = int(env("DEGRADATION_DELAY_MS", "50"))
DEGRADATION_SECONDS = float(env("DEGRADATION_SECONDS", "8.0"))
DEFERRED_RECONCILIATION_INTERVAL_MS = int(env("DEFERRED_RECONCILIATION_INTERVAL_MS", "250"))
EVENT_COUNT = int(env("EVENT_COUNT", "0"))
DEADLINE_WINDOW_SECONDS = float(env("DEADLINE_WINDOW_SECONDS", "0.0"))
UPDATES_PER_ENTITY = max(1, int(env("UPDATES_PER_ENTITY", "1")))
STATE_OUTAGE_EXPOSED_VERSION = int(env("STATE_OUTAGE_EXPOSED_VERSION", str(UPDATES_PER_ENTITY)))
STATE_OUTAGE_EXPOSED_START_FRACTION = float(env("STATE_OUTAGE_EXPOSED_START_FRACTION", "0.34"))
STATE_FORWARD_RESUMPTION_VERSION = int(env("STATE_FORWARD_RESUMPTION_VERSION", "0"))
STATE_TRANSIENT_DROP_EXPOSED_LATEST = env("STATE_TRANSIENT_DROP_EXPOSED_LATEST", "0") == "1"
TRANSIENT_INTERRUPT_DISCONNECT = env("TRANSIENT_INTERRUPT_DISCONNECT", "0") == "1"

RUN_DIR = Path(env("RUN_DIR", "/run"))
LOGS_DIR = Path(env("LOGS_DIR", "/run/logs"))
ARTIFACTS_DIR = Path(env("ARTIFACTS_DIR", "/run/artifacts"))
for path in (RUN_DIR, LOGS_DIR, ARTIFACTS_DIR):
    path.mkdir(parents=True, exist_ok=True)

producer_sentinel = ARTIFACTS_DIR / "producer_complete.json"
producer_progress_file = ARTIFACTS_DIR / "producer_progress.json"
run_complete = ARTIFACTS_DIR / "run_complete.json"
consumer_summary = LOGS_DIR / "consumer_summary.json"
consumer_log = LOGS_DIR / "consumer.log"
outcome_log = LOGS_DIR / "outcome.log"
metrics_summary = ARTIFACTS_DIR / "metrics_summary.json"
run_report = ARTIFACTS_DIR / "run_report.md"
recovery_shape_summary = ARTIFACTS_DIR / "recovery_shape_summary.json"
unresolved_trace_log = ARTIFACTS_DIR / "unresolved_correctness_trace.jsonl"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} consumer {message}"
    print(line, flush=True)
    with consumer_log.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def append_outcome(payload: dict) -> None:
    with outcome_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload) + "\n")


def parse_event(payload: str) -> dict:
    return json.loads(payload)


def read_producer_count_hints() -> tuple[Optional[int], Optional[int]]:
    if not producer_sentinel.exists():
        return None, None
    try:
        producer_info = json.loads(producer_sentinel.read_text(encoding="utf-8"))
        emitted = int(producer_info.get("produced_case_count", producer_info.get("produced_event_count", 0)))
        logical = int(producer_info.get("logical_case_count", emitted))
        return emitted, logical
    except Exception:
        return None, None


def read_producer_progress_state() -> tuple[int, float, bool]:
    if not producer_progress_file.exists():
        return 0, 0.0, False
    try:
        producer_info = json.loads(producer_progress_file.read_text(encoding="utf-8"))
        produced = int(producer_info.get("produced_case_count", producer_info.get("produced_event_count", 0)))
        fraction = producer_info.get("progress_fraction")
        fraction_value = float(fraction) if fraction is not None else (0.0 if EVENT_COUNT <= 0 else produced / EVENT_COUNT)
        is_complete = str(producer_info.get("status", "")) == "complete"
        return produced, fraction_value, is_complete
    except Exception:
        return 0, 0.0, False


def append_unresolved_trace_sample(*, elapsed_seconds: float, produced_count_observed: int, progress_fraction_observed: float, attained_count: int, pending_case_count: int, retained_buffer_count: int, producer_complete_seen: bool) -> None:
    unresolved_count = max(0, produced_count_observed - attained_count)
    sample = {
        "elapsed_seconds": round(elapsed_seconds, 6),
        "produced_count_observed": int(produced_count_observed),
        "progress_fraction_observed": round(progress_fraction_observed, 6),
        "attained_count": int(attained_count),
        "unresolved_count": int(unresolved_count),
        "unresolved_share_observed": round(0.0 if produced_count_observed <= 0 else unresolved_count / produced_count_observed, 6),
        "pending_case_count": int(pending_case_count),
        "retained_buffer_count": int(retained_buffer_count),
        "producer_complete_seen": bool(producer_complete_seen),
    }
    with unresolved_trace_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample) + "\n")


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


def event_extra_delay_seconds(event: dict) -> float:
    return max(0.0, float(event.get("extra_processing_delay_ms", 0)) / 1000.0)


def reset_transient_subscription(client: redis.Redis, pubsub):
    try:
        if pubsub is not None:
            try:
                pubsub.unsubscribe(CHANNEL_KEY)
            except Exception:
                pass
            try:
                pubsub.close()
            except Exception:
                pass
    finally:
        new_pubsub = client.pubsub(ignore_subscribe_messages=True)
        new_pubsub.subscribe(CHANNEL_KEY)
    return new_pubsub


def maybe_apply_disturbance(run_started: float, interruption_state: dict, client: redis.Redis, pubsub):
    elapsed = time.time() - run_started
    if DISTURBANCE == "degradation" and elapsed <= DEGRADATION_SECONDS and DEGRADATION_DELAY_MS > 0:
        time.sleep(DEGRADATION_DELAY_MS / 1000.0)
        return pubsub
    if DISTURBANCE != "interruption" or interruption_state["applied"]:
        return pubsub
    should_interrupt = False
    trigger_reason = None
    trigger_fraction = 0.0
    if INTERRUPTION_START_MODE == "progress_fraction":
        progress_count, trigger_fraction, _ = read_producer_progress_state()
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
        if DELIVERY_MODE == "transient" and TRANSIENT_INTERRUPT_DISCONNECT:
            log(f"interruption_disconnect_active mode={INTERRUPTION_START_MODE} reason={trigger_reason} duration={INTERRUPTION_SECONDS:.3f} state_drop_exposed_latest={STATE_TRANSIENT_DROP_EXPOSED_LATEST}")
            pubsub = reset_transient_subscription(client, pubsub)
            time.sleep(max(0.0, INTERRUPTION_SECONDS))
            pubsub = reset_transient_subscription(client, pubsub)
            log("interruption_disconnect_complete resubscribed=true")
        else:
            log(f"interruption_active mode={INTERRUPTION_START_MODE} reason={trigger_reason} duration={INTERRUPTION_SECONDS:.3f}")
            time.sleep(max(0.0, INTERRUPTION_SECONDS))
    return pubsub


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    idx = max(0, min(len(values) - 1, int((len(values) - 1) * q)))
    return values[idx]


def reconcile_pending_cases(pending_cases: dict[int, dict], seen_cases: set[int], first_attainment_times: list[float], run_started: float, deadline_counts: dict[str, int], completion_times: list[float], expiry_times: list[float]) -> tuple[int, int, int, int]:
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
    log(f"reconciliation_pass pending_before={pending_before} reconciled={reconciled} newly_attained={newly_attained} delayed_cases={delayed_cases}")
    return reconciled, newly_attained, pending_before, delayed_cases


def attainment_time_at_fraction(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if fraction <= 0:
        return 0.0
    index = max(0, min(len(values) - 1, int((len(values) * fraction) - 1)))
    return float(values[index])


def window(start: float, end: float) -> float:
    return max(0.0, end - start)


def state_outage_first_exposed_entity_id(entity_count: int, fraction: float) -> int:
    if entity_count <= 0:
        return 0
    normalized = max(0.0, min(1.0, fraction))
    threshold = (Decimal(str(normalized)) * Decimal(entity_count)).to_integral_value(rounding=ROUND_CEILING)
    first = int(threshold)
    return max(0, min(entity_count, first))


def expected_state_outage_exposed_count() -> int:
    if BOUNDARY != "state_non_regression" or DISTURBANCE != "interruption":
        return 0
    if EVENT_COUNT <= 0 or STATE_OUTAGE_EXPOSED_VERSION <= 0:
        return 0
    first_exposed = state_outage_first_exposed_entity_id(EVENT_COUNT, STATE_OUTAGE_EXPOSED_START_FRACTION)
    return max(0, EVENT_COUNT - first_exposed)


def expected_state_outage_exposed_entity_ids() -> set[int]:
    if EVENT_COUNT <= 0:
        return set()
    first_exposed = state_outage_first_exposed_entity_id(EVENT_COUNT, STATE_OUTAGE_EXPOSED_START_FRACTION)
    return set(range(first_exposed, EVENT_COUNT))


def main() -> int:
    if BOUNDARY == "state_non_regression" and ENFORCEMENT_TIMING != "immediate":
        raise RuntimeError("state_non_regression pilot currently supports immediate enforcement only")

    client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    pubsub = None
    if DELIVERY_MODE == "transient":
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(CHANNEL_KEY)

    run_started = time.time()
    last_activity = run_started
    processed = 0
    received_event_count = 0
    duplicate_delivery_count = 0
    duplicate_after_attainment_count = 0
    deferred_pending_overwrite_count = 0
    duplicate_side_effect_execution_count = 0
    correction_rewrite_count = 0
    wrong_latest_version_commit_count = 0
    attained = 0
    first_attainment_times: list[float] = []
    completion_times: list[float] = []
    expiry_times: list[float] = []
    deadline_counts = {"completed_in_time": 0, "expired": 0}
    seen_cases: set[int] = set()
    pending_cases: dict[int, dict] = {}
    retained_buffer: list[dict] = []
    last_stream_id = "0-0"
    emitted_count_hint: Optional[int] = None
    logical_count_hint: Optional[int] = None
    producer_complete_seen_elapsed_seconds: Optional[float] = None
    observation_window_expired = False
    status = "complete"
    next_reconciliation_at = run_started + (DEFERRED_RECONCILIATION_INTERVAL_MS / 1000.0)
    next_unresolved_trace_at = run_started
    reconciliation_pass_count = 0
    reconciliation_cases_seen = 0
    reconciliation_attainment_passes = 0
    reconciliation_delayed_cases = 0
    interruption_state = {"applied": False, "trigger_elapsed_seconds": None, "trigger_progress_fraction": None, "trigger_reason": None}

    # state-boundary-specific state
    entity_versions: dict[int, int] = {}
    latest_attained_entities: set[int] = set()
    state_obsolete_suppression_count = 0
    state_same_version_duplicate_count = 0
    state_outage_exposed_event_count = 0
    state_transient_outage_drop_count = 0
    state_latest_version_target = UPDATES_PER_ENTITY
    state_outage_exposed_version = STATE_OUTAGE_EXPOSED_VERSION
    state_forward_resumption_version = STATE_FORWARD_RESUMPTION_VERSION
    state_outage_exposed_expected_event_count = expected_state_outage_exposed_count()
    state_outage_exposed_expected_entity_ids = expected_state_outage_exposed_entity_ids()
    state_forward_resumed_entities: set[int] = set()

    log(f"starting delivery_mode={DELIVERY_MODE} enforcement_timing={ENFORCEMENT_TIMING} boundary={BOUNDARY} disturbance={DISTURBANCE}")

    try:
        while True:
            elapsed = time.time() - run_started
            if elapsed > OBSERVATION_WINDOW_SECONDS:
                observation_window_expired = True
                status = "window_expired"
                log("observation_window_expired")
                break

            pubsub = maybe_apply_disturbance(run_started, interruption_state, client, pubsub)

            now = time.time()
            if now >= next_unresolved_trace_at:
                progress_count, progress_fraction, progress_complete = read_producer_progress_state()
                produced_for_trace = max(logical_count_hint or 0, progress_count)
                append_unresolved_trace_sample(
                    elapsed_seconds=now - run_started,
                    produced_count_observed=produced_for_trace,
                    progress_fraction_observed=progress_fraction,
                    attained_count=attained,
                    pending_case_count=len(pending_cases),
                    retained_buffer_count=len(retained_buffer),
                    producer_complete_seen=producer_sentinel.exists() or progress_complete,
                )
                next_unresolved_trace_at = now + 0.25

            if ENFORCEMENT_TIMING == "deferred" and pending_cases and now >= next_reconciliation_at:
                reconciled, newly_attained, pending_before, delayed_cases = reconcile_pending_cases(pending_cases, seen_cases, first_attainment_times, run_started, deadline_counts, completion_times, expiry_times)
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
                received_event_count += 1
                extra_delay = event_extra_delay_seconds(event)
                if extra_delay > 0:
                    time.sleep(extra_delay)

                if BOUNDARY == "state_non_regression":
                    entity_id = int(event.get("entity_id", event.get("case_id", 0)))
                    version = int(event.get("version", 1))
                    current_version = entity_versions.get(entity_id, 0)
                    outage_exposed = bool(event.get("state_outage_exposed", False))
                    if outage_exposed:
                        state_outage_exposed_event_count += 1
                    if (
                        DELIVERY_MODE == "transient"
                        and DISTURBANCE == "interruption"
                        and STATE_TRANSIENT_DROP_EXPOSED_LATEST
                        and outage_exposed
                        and version == state_outage_exposed_version
                    ):
                        state_transient_outage_drop_count += 1
                        log(f"state_outage_drop entity_id={entity_id} version={version} exposed_version={state_outage_exposed_version}")
                        continue
                    processed += 1
                    if version < current_version:
                        state_obsolete_suppression_count += 1
                        wrong_latest_version_commit_count += 1
                        log(f"obsolete_ignored entity_id={entity_id} version={version} current={current_version}")
                    elif version == current_version:
                        duplicate_delivery_count += 1
                        state_same_version_duplicate_count += 1
                        if entity_id in latest_attained_entities:
                            duplicate_after_attainment_count += 1
                            duplicate_side_effect_execution_count += 1
                    else:
                        entity_versions[entity_id] = version
                        if state_forward_resumption_version > 0 and version >= state_forward_resumption_version and entity_id in state_outage_exposed_expected_entity_ids:
                            state_forward_resumed_entities.add(entity_id)
                        if version >= state_latest_version_target and entity_id not in latest_attained_entities:
                            latest_attained_entities.add(entity_id)
                            attained += 1
                            resolved_epoch = time.time()
                            attained_at = resolved_epoch - run_started
                            first_attainment_times.append(attained_at)
                            completion_times.append(attained_at)
                            append_terminal_outcome(case_id=entity_id, event_id=int(event["event_id"]), resolved_at_seconds=attained_at, resolved_epoch=resolved_epoch, source="immediate_handling", event=event, outcome_kind="completed")
                            log(f"latest_state_attained entity_id={entity_id} version={version} attained={attained}")
                    continue

                case_id = int(event["case_id"])
                event_id = int(event["event_id"])
                if ENFORCEMENT_TIMING == "deferred":
                    if case_id in pending_cases:
                        duplicate_delivery_count += 1
                        deferred_pending_overwrite_count += 1
                        correction_rewrite_count += 1
                    elif case_id in seen_cases:
                        duplicate_delivery_count += 1
                        duplicate_after_attainment_count += 1
                        duplicate_side_effect_execution_count += 1
                    pending_cases[case_id] = event
                    log(f"pending_recorded case_id={case_id} event_id={event_id} pending_count={len(pending_cases)}")
                else:
                    if case_id in seen_cases:
                        duplicate_delivery_count += 1
                        duplicate_after_attainment_count += 1
                        duplicate_side_effect_execution_count += 1
                    else:
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
                emitted_count, logical_count = read_producer_count_hints()
                if emitted_count_hint is None and emitted_count is not None:
                    emitted_count_hint = emitted_count
                    logical_count_hint = logical_count
                    producer_complete_seen_elapsed_seconds = round(time.time() - run_started, 6)
                    log(
                        f"producer_complete_seen emitted_hint={emitted_count_hint} "
                        f"logical_hint={logical_count_hint} "
                        f"seen_elapsed={producer_complete_seen_elapsed_seconds}"
                    )
                quiet_for = time.time() - last_activity
                if BOUNDARY == "state_non_regression":
                    target_reached = True
                elif DELIVERY_MODE == "retained":
                    target_reached = emitted_count_hint is not None and processed >= emitted_count_hint
                else:
                    target_reached = True
                if quiet_for >= QUIET_PERIOD_SECONDS and not retained_buffer and not pending_cases and target_reached:
                    log(
                        f"drain_complete processed={processed} emitted_hint={emitted_count_hint} "
                        f"logical_hint={logical_count_hint} quiet_for={quiet_for:.3f}"
                    )
                    status = "complete"
                    break

        sorted_times = sorted(first_attainment_times)
        mean_tta = sum(sorted_times) / len(sorted_times) if sorted_times else 0.0
        p95 = quantile(sorted_times, 0.95)
        p99 = quantile(sorted_times, 0.99)
        p999 = quantile(sorted_times, 0.999)
        t25 = attainment_time_at_fraction(sorted_times, 0.25)
        t50 = attainment_time_at_fraction(sorted_times, 0.50)
        t75 = attainment_time_at_fraction(sorted_times, 0.75)
        t90 = attainment_time_at_fraction(sorted_times, 0.90)
        t95 = attainment_time_at_fraction(sorted_times, 0.95)
        t99 = attainment_time_at_fraction(sorted_times, 0.99)
        busy_share_1s = bucket_busiest_share(sorted_times, 1.0)
        busy_share_250ms = bucket_busiest_share(sorted_times, 0.25)
        busy_share_100ms = bucket_busiest_share(sorted_times, 0.10)
        distinct_timestamps_1ms = rounded_distinct_count(sorted_times, 3)
        distinct_timestamps_10ms = rounded_distinct_count(sorted_times, 2)
        mean_gap, gap_cv = inter_attainment_gap_stats(sorted_times)
        last_attainment_seconds = sorted_times[-1] if sorted_times else 0.0

        if emitted_count_hint is None:
            emitted_count_hint, logical_count_hint = read_producer_count_hints()
        emitted_total = emitted_count_hint if emitted_count_hint is not None else 0
        produced_total = logical_count_hint if logical_count_hint is not None else emitted_total
        unattained_case_count = max(0, produced_total - attained)
        all_cases_attained_within_window = produced_total > 0 and attained == produced_total

        completed_in_time_count = deadline_counts["completed_in_time"] if BOUNDARY == "deadline_constrained" else attained
        expired_count = deadline_counts["expired"] if BOUNDARY == "deadline_constrained" else 0
        completed_in_time_rate = 0.0 if produced_total == 0 else completed_in_time_count / produced_total
        expired_rate = 0.0 if produced_total == 0 else expired_count / produced_total
        terminal_resolution_rate = 0.0 if produced_total == 0 else (completed_in_time_count + expired_count) / produced_total if BOUNDARY == "deadline_constrained" else attained / produced_total
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
            attained_after_producer_complete_share = attained_after_producer_complete_count / len(sorted_times)

        recovery_shape = {
            "attained_case_count": len(sorted_times),
            "attainment_t25_seconds": round(t25, 6),
            "attainment_t50_seconds": round(t50, 6),
            "attainment_t75_seconds": round(t75, 6),
            "attainment_t90_seconds": round(t90, 6),
            "attainment_t95_seconds": round(t95, 6),
            "attainment_t99_seconds": round(t99, 6),
            "early_bulk_window_25_to_50_seconds": round(window(t25, t50), 6),
            "main_bulk_window_50_to_75_seconds": round(window(t50, t75), 6),
            "bulk_window_25_to_75_seconds": round(window(t25, t75), 6),
            "upper_bulk_window_75_to_90_seconds": round(window(t75, t90), 6),
            "late_region_window_75_to_95_seconds": round(window(t75, t95), 6),
            "tail_window_90_to_99_seconds": round(window(t90, t99), 6),
            "straggler_window_95_to_99_seconds": round(window(t95, t99), 6),
            "tail_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t90, t99) / max(window(t25, t75), 1e-9), 6),
            "upper_bulk_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t75, t90) / max(window(t25, t75), 1e-9), 6),
            "straggler_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t95, t99) / max(window(t25, t75), 1e-9), 6),
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
            "attained_after_producer_complete_count": attained_after_producer_complete_count,
            "attained_after_producer_complete_share": round(attained_after_producer_complete_share, 6),
            "producer_complete_to_last_attainment_seconds": round(producer_complete_to_last_attainment_seconds, 6),
            "producer_complete_to_p95_seconds": round(producer_complete_to_p95_seconds, 6),
            "retained_buffer_remaining": len(retained_buffer),
            "pending_case_count_remaining": len(pending_cases),
            "received_event_count": received_event_count,
            "duplicate_delivery_count": duplicate_delivery_count,
            "duplicate_delivery_rate": round(0.0 if received_event_count == 0 else duplicate_delivery_count / received_event_count, 6),
            "duplicate_after_attainment_count": duplicate_after_attainment_count,
            "deferred_pending_overwrite_count": deferred_pending_overwrite_count,
            "duplicate_side_effect_execution_count": duplicate_side_effect_execution_count,
            "correction_rewrite_count": correction_rewrite_count,
            "wrong_latest_version_commit_count": wrong_latest_version_commit_count,
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

        final_now = time.time()
        progress_count, progress_fraction, progress_complete = read_producer_progress_state()
        produced_for_trace = max(produced_total, progress_count)
        append_unresolved_trace_sample(
            elapsed_seconds=final_now - run_started,
            produced_count_observed=produced_for_trace,
            progress_fraction_observed=progress_fraction,
            attained_count=attained,
            pending_case_count=len(pending_cases),
            retained_buffer_count=len(retained_buffer),
            producer_complete_seen=producer_sentinel.exists() or progress_complete,
        )

        state_latest_version_attainment_count = attained if BOUNDARY == "state_non_regression" else 0
        state_latest_version_attainment_rate = 0.0 if BOUNDARY != "state_non_regression" or produced_total == 0 else attained / produced_total
        state_latest_version_omission_count = max(0, produced_total - attained) if BOUNDARY == "state_non_regression" else 0
        state_latest_version_omission_rate = 0.0 if BOUNDARY != "state_non_regression" or produced_total == 0 else state_latest_version_omission_count / produced_total
        state_obsolete_suppression_rate = 0.0 if BOUNDARY != "state_non_regression" or received_event_count == 0 else state_obsolete_suppression_count / received_event_count
        state_outage_exposed_event_rate = 0.0 if BOUNDARY != "state_non_regression" or received_event_count == 0 else state_outage_exposed_event_count / received_event_count
        state_transient_outage_drop_rate = 0.0 if BOUNDARY != "state_non_regression" or received_event_count == 0 else state_transient_outage_drop_count / received_event_count
        state_outage_exposed_expected_event_rate = 0.0 if BOUNDARY != "state_non_regression" or EVENT_COUNT == 0 else state_outage_exposed_expected_event_count / EVENT_COUNT
        state_outage_exposed_seen_fraction_of_expected = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_expected_event_count == 0 else state_outage_exposed_event_count / state_outage_exposed_expected_event_count
        state_transient_outage_drop_fraction_of_expected = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_expected_event_count == 0 else state_transient_outage_drop_count / state_outage_exposed_expected_event_count
        state_outage_exposed_unseen_count = max(0, state_outage_exposed_expected_event_count - state_outage_exposed_event_count) if BOUNDARY == "state_non_regression" else 0
        state_outage_exposed_unseen_fraction_of_expected = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_expected_event_count == 0 else state_outage_exposed_unseen_count / state_outage_exposed_expected_event_count
        state_outage_exposed_loss_count = max(0, state_outage_exposed_expected_event_count - state_outage_exposed_event_count) + state_transient_outage_drop_count if BOUNDARY == "state_non_regression" else 0
        state_outage_exposed_loss_fraction_of_expected = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_expected_event_count == 0 else state_outage_exposed_loss_count / state_outage_exposed_expected_event_count
        state_forward_resumption_entity_count = len(state_forward_resumed_entities) if BOUNDARY == "state_non_regression" else 0
        state_forward_resumption_adequacy_rate = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_expected_event_count == 0 or state_forward_resumption_version <= 0 else state_forward_resumption_entity_count / state_outage_exposed_expected_event_count
        state_forward_resumption_after_loss_count = min(state_forward_resumption_entity_count, state_outage_exposed_loss_count) if BOUNDARY == "state_non_regression" else 0
        state_forward_resumption_after_loss_rate = 0.0 if BOUNDARY != "state_non_regression" or state_outage_exposed_loss_count == 0 or state_forward_resumption_version <= 0 else state_forward_resumption_after_loss_count / state_outage_exposed_loss_count

        metrics = {
            "status": status,
            "observation_window_expired": observation_window_expired,
            "produced_event_count": produced_total,
            "produced_event_count_emitted": emitted_total,
            "processed_event_count": processed,
            "produced_case_count": produced_total,
            "produced_case_count_emitted": emitted_total,
            "attained_case_count": attained,
            "attainment_rate": round(terminal_resolution_rate, 6),
            "all_cases_attained_within_window": all_cases_attained_within_window,
            "mean_time_to_attainment_seconds": round(mean_tta, 6),
            "p95_time_to_attainment_seconds": round(p95, 6),
            "p99_time_to_attainment_seconds": round(p99, 6),
            "p999_time_to_attainment_seconds": round(p999, 6),
            "attainment_t25_seconds": round(t25, 6),
            "attainment_t50_seconds": round(t50, 6),
            "attainment_t75_seconds": round(t75, 6),
            "attainment_t90_seconds": round(t90, 6),
            "attainment_t95_seconds": round(t95, 6),
            "attainment_t99_seconds": round(t99, 6),
            "early_bulk_window_25_to_50_seconds": round(window(t25, t50), 6),
            "main_bulk_window_50_to_75_seconds": round(window(t50, t75), 6),
            "bulk_window_25_to_75_seconds": round(window(t25, t75), 6),
            "upper_bulk_window_75_to_90_seconds": round(window(t75, t90), 6),
            "late_region_window_75_to_95_seconds": round(window(t75, t95), 6),
            "tail_window_90_to_99_seconds": round(window(t90, t99), 6),
            "straggler_window_95_to_99_seconds": round(window(t95, t99), 6),
            "tail_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t90, t99) / max(window(t25, t75), 1e-9), 6),
            "upper_bulk_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t75, t90) / max(window(t25, t75), 1e-9), 6),
            "straggler_to_bulk_ratio": round(0.0 if window(t25, t75) <= 0 else window(t95, t99) / max(window(t25, t75), 1e-9), 6),
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
            "producer_complete_to_last_attainment_seconds": round(producer_complete_to_last_attainment_seconds, 6),
            "producer_complete_to_p95_seconds": round(producer_complete_to_p95_seconds, 6),
            "attained_after_producer_complete_count": attained_after_producer_complete_count,
            "attained_after_producer_complete_share": round(attained_after_producer_complete_share, 6),
            "reconciliation_pass_count": reconciliation_pass_count,
            "retained_buffer_remaining": len(retained_buffer),
            "pending_case_count_remaining": len(pending_cases),
            "received_event_count": received_event_count,
            "duplicate_delivery_count": duplicate_delivery_count,
            "duplicate_delivery_rate": round(0.0 if received_event_count == 0 else duplicate_delivery_count / received_event_count, 6),
            "duplicate_after_attainment_count": duplicate_after_attainment_count,
            "deferred_pending_overwrite_count": deferred_pending_overwrite_count,
            "duplicate_side_effect_execution_count": duplicate_side_effect_execution_count,
            "correction_rewrite_count": correction_rewrite_count,
            "wrong_latest_version_commit_count": wrong_latest_version_commit_count,
            "deadline_window_seconds": DEADLINE_WINDOW_SECONDS,
            "completed_in_time_count": completed_in_time_count,
            "expired_count": expired_count,
            "completed_in_time_rate": round(completed_in_time_rate, 6),
            "expired_rate": round(expired_rate, 6),
            "terminal_resolution_rate": round(terminal_resolution_rate, 6),
            "median_time_to_completion_in_time": round(median_time_to_completion_in_time, 6),
            "median_time_to_expiry": round(median_time_to_expiry, 6),
            "share_resolved_by_expiry": round(expired_rate, 6),
            "share_resolved_by_completion": round(completed_in_time_rate, 6),
            "state_latest_version_attainment_count": state_latest_version_attainment_count,
            "state_latest_version_attainment_rate": round(state_latest_version_attainment_rate, 6),
            "state_latest_version_omission_count": state_latest_version_omission_count,
            "state_latest_version_omission_rate": round(state_latest_version_omission_rate, 6),
            "state_obsolete_suppression_count": state_obsolete_suppression_count,
            "state_obsolete_suppression_rate": round(state_obsolete_suppression_rate, 6),
            "state_same_version_duplicate_count": state_same_version_duplicate_count,
            "state_outage_exposed_event_count": state_outage_exposed_event_count,
            "state_outage_exposed_event_rate": round(state_outage_exposed_event_rate, 6),
            "state_outage_exposed_expected_event_count": state_outage_exposed_expected_event_count,
            "state_outage_exposed_expected_event_rate": round(state_outage_exposed_expected_event_rate, 6),
            "state_outage_exposed_seen_fraction_of_expected": round(state_outage_exposed_seen_fraction_of_expected, 6),
            "state_outage_exposed_unseen_count": state_outage_exposed_unseen_count,
            "state_outage_exposed_unseen_fraction_of_expected": round(state_outage_exposed_unseen_fraction_of_expected, 6),
            "state_transient_outage_drop_count": state_transient_outage_drop_count,
            "state_transient_outage_drop_rate": round(state_transient_outage_drop_rate, 6),
            "state_transient_outage_drop_fraction_of_expected": round(state_transient_outage_drop_fraction_of_expected, 6),
            "state_outage_exposed_loss_count": state_outage_exposed_loss_count,
            "state_outage_exposed_loss_fraction_of_expected": round(state_outage_exposed_loss_fraction_of_expected, 6),
            "state_outage_exposed_version": state_outage_exposed_version,
            "state_latest_version_target": state_latest_version_target,
            "state_forward_resumption_version": state_forward_resumption_version,
            "state_forward_resumption_entity_count": state_forward_resumption_entity_count,
            "state_forward_resumption_adequacy_rate": round(state_forward_resumption_adequacy_rate, 6),
            "state_forward_resumption_after_loss_count": state_forward_resumption_after_loss_count,
            "state_forward_resumption_after_loss_rate": round(state_forward_resumption_after_loss_rate, 6),
        }
        metrics_summary.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        consumer_summary.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
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
                    f"- produced_case_count: {produced_total}",
                    f"- produced_case_count_emitted: {emitted_total}",
                    f"- received_event_count: {received_event_count}",
                    f"- attained_case_count: {attained}",
                    f"- unattained_case_count: {unattained_case_count}",
                    f"- state_latest_version_attainment_rate: {round(state_latest_version_attainment_rate, 6)}",
                    f"- state_latest_version_omission_rate: {round(state_latest_version_omission_rate, 6)}",
                    f"- state_obsolete_suppression_count: {state_obsolete_suppression_count}",
                    f"- state_same_version_duplicate_count: {state_same_version_duplicate_count}",
                    f"- duplicate_delivery_count: {duplicate_delivery_count}",
                    f"- duplicate_side_effect_execution_count: {duplicate_side_effect_execution_count}",
                    f"- correction_rewrite_count: {correction_rewrite_count}",
                    f"- wrong_latest_version_commit_count: {wrong_latest_version_commit_count}",
                    f"- observation_window_expired: {observation_window_expired}",
                ]
            ) + "\n",
            encoding="utf-8",
        )
        run_complete.write_text(json.dumps({"status": status, "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        status = "failed"
        log(f"failed error={exc!r}")
        try:
            partial_metrics = {
                "status": status,
                "boundary": BOUNDARY,
                "delivery_mode": DELIVERY_MODE,
                "enforcement_timing": ENFORCEMENT_TIMING,
                "disturbance": DISTURBANCE,
                "received_event_count": locals().get("received_event_count", 0),
                "state_outage_exposed_event_count": locals().get("state_outage_exposed_event_count", 0),
                "state_transient_outage_drop_count": locals().get("state_transient_outage_drop_count", 0),
                "error": repr(exc),
            }
            metrics_summary.write_text(json.dumps(partial_metrics, indent=2), encoding="utf-8")
        except Exception:
            pass
        run_complete.write_text(json.dumps({"status": status, "error": repr(exc)}, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
