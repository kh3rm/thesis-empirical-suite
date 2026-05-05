import json
import os
import random
import time
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

import redis


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


REDIS_HOST = env("REDIS_HOST", "redis")
EVENT_COUNT = int(env("EVENT_COUNT", "200"))
EVENT_INTERVAL_MS = int(env("EVENT_INTERVAL_MS", "5"))
DELIVERY_MODE = env("DELIVERY_MODE", "transient")
STREAM_KEY = env("STREAM_KEY", "events")
CHANNEL_KEY = env("CHANNEL_KEY", "events")
DISTURBANCE = env("DISTURBANCE", "none")
BOUNDARY = env("BOUNDARY", "required_effect")
PRODUCER_START_DELAY_SECONDS = float(env("PRODUCER_START_DELAY_SECONDS", "1.0"))
BASE_EVENT_INTERVAL_MS = int(env("BASE_EVENT_INTERVAL_MS", str(EVENT_INTERVAL_MS)))
OVERLOAD_EVENT_INTERVAL_MS = int(env("OVERLOAD_EVENT_INTERVAL_MS", str(EVENT_INTERVAL_MS)))
OVERLOAD_START_SECONDS = float(env("OVERLOAD_START_SECONDS", "0.0"))
OVERLOAD_DURATION_SECONDS = float(env("OVERLOAD_DURATION_SECONDS", "0.0"))
SKEWED_TAIL_FRACTION = float(env("SKEWED_TAIL_FRACTION", "0.0"))
SKEWED_TAIL_EXTRA_DELAY_MS = int(env("SKEWED_TAIL_EXTRA_DELAY_MS", "0"))
SCENARIO_SEED = int(env("SCENARIO_SEED", "1"))
DEADLINE_WINDOW_SECONDS = float(env("DEADLINE_WINDOW_SECONDS", "0.0"))
DUPLICATE_FRACTION = float(env("DUPLICATE_FRACTION", "0.0"))
DUPLICATE_DELAY_MS = int(env("DUPLICATE_DELAY_MS", "0"))
DUPLICATE_MODE = env("DUPLICATE_MODE", "selected_cases_once")
DUPLICATE_REPEATS = int(env("DUPLICATE_REPEATS", "1"))
DUPLICATE_JITTER_MS = int(env("DUPLICATE_JITTER_MS", "0"))
OMISSION_FRACTION = float(env("OMISSION_FRACTION", "0.0"))
OMISSION_MODE = env("OMISSION_MODE", "selected_cases_skip")
UPDATES_PER_ENTITY = max(1, int(env("UPDATES_PER_ENTITY", "1")))
STATE_OBSOLETE_REPLAY_FRACTION = float(env("STATE_OBSOLETE_REPLAY_FRACTION", "0.0"))
INTERRUPTION_START_FRACTION = float(env("INTERRUPTION_START_FRACTION", "0.0"))
STATE_OUTAGE_EXPOSED_VERSION = int(env("STATE_OUTAGE_EXPOSED_VERSION", str(UPDATES_PER_ENTITY)))
STATE_OUTAGE_EXPOSED_START_FRACTION = float(env("STATE_OUTAGE_EXPOSED_START_FRACTION", "0.34"))
STATE_FORWARD_RESUMPTION_VERSION = int(env("STATE_FORWARD_RESUMPTION_VERSION", "0"))

ARTIFACTS_DIR = Path(env("ARTIFACTS_DIR", "/run/artifacts"))
LOGS_DIR = Path(env("LOGS_DIR", "/run/logs"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_path = LOGS_DIR / "producer.log"
producer_started = ARTIFACTS_DIR / "producer_started.json"
producer_complete = ARTIFACTS_DIR / "producer_complete.json"
producer_progress = ARTIFACTS_DIR / "producer_progress.json"


def log(message: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} producer {message}"
    print(line, flush=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def current_interval_ms(started: float) -> int:
    if DISTURBANCE != "overload_burst":
        return EVENT_INTERVAL_MS
    elapsed = time.time() - started
    overload_end = OVERLOAD_START_SECONDS + OVERLOAD_DURATION_SECONDS
    if OVERLOAD_START_SECONDS <= elapsed <= overload_end:
        return OVERLOAD_EVENT_INTERVAL_MS
    return BASE_EVENT_INTERVAL_MS


def write_progress(*, status: str, produced_event_count: int, produced_case_count: int, logical_case_count: int, started: float, progress_fraction_override: float | None = None) -> None:
    fraction = progress_fraction_override if progress_fraction_override is not None else (0.0 if logical_case_count <= 0 else round(produced_case_count / logical_case_count, 6))
    producer_progress.write_text(
        json.dumps(
            {
                "status": status,
                "produced_event_count": produced_event_count,
                "produced_case_count": produced_case_count,
                "event_count": logical_case_count,
                "progress_fraction": fraction,
                "elapsed_seconds": round(time.time() - started, 6),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def publish_payload(client: redis.Redis, payload: str) -> None:
    if DELIVERY_MODE == "retained":
        client.xadd(STREAM_KEY, {"payload": payload})
    else:
        client.publish(CHANNEL_KEY, payload)


def state_outage_first_exposed_entity_id(entity_count: int, fraction: float) -> int:
    if entity_count <= 0:
        return 0
    normalized = max(0.0, min(1.0, fraction))
    threshold = (Decimal(str(normalized)) * Decimal(entity_count)).to_integral_value(rounding=ROUND_CEILING)
    first = int(threshold)
    return max(0, min(entity_count, first))


def emit_standard_events(client: redis.Redis, started: float, rand: random.Random) -> tuple[int, int, int, int, int]:
    emitted = 0
    logical_seen = 0
    delayed_case_ids = set()
    duplicate_case_ids = set()
    omitted_case_ids = set()
    duplicate_emissions = 0
    progress_interval = max(1, EVENT_COUNT // 20)

    if DISTURBANCE == "skewed_tail" and SKEWED_TAIL_FRACTION > 0 and SKEWED_TAIL_EXTRA_DELAY_MS > 0:
        delayed_count = max(1, int(EVENT_COUNT * SKEWED_TAIL_FRACTION))
        delayed_case_ids = set(rand.sample(range(EVENT_COUNT), min(EVENT_COUNT, delayed_count)))
        log(f"skewed_tail_selected delayed_count={len(delayed_case_ids)} extra_delay_ms={SKEWED_TAIL_EXTRA_DELAY_MS}")
    # Allow explicit per-scenario composition by activating duplicate/omission
    # behavior whenever the corresponding fractions are set, independent of
    # the coarse DISTURBANCE label.
    duplicate_active = (
        DISTURBANCE in {"duplicate_pressure", "mixed_pressure"}
        or DUPLICATE_FRACTION > 0
    )
    omission_active = (
        DISTURBANCE in {"omission_pressure", "mixed_pressure"}
        or OMISSION_FRACTION > 0
    )

    if duplicate_active and DUPLICATE_FRACTION > 0:
        duplicate_count = max(1, int(EVENT_COUNT * DUPLICATE_FRACTION))
        duplicate_case_ids = set(rand.sample(range(EVENT_COUNT), min(EVENT_COUNT, duplicate_count)))
        log(f"duplicate_pressure_selected duplicate_case_count={len(duplicate_case_ids)} duplicate_delay_ms={DUPLICATE_DELAY_MS} duplicate_repeats={DUPLICATE_REPEATS} duplicate_jitter_ms={DUPLICATE_JITTER_MS} mode={DUPLICATE_MODE}")
    if omission_active and OMISSION_FRACTION > 0:
        omission_count = max(1, int(EVENT_COUNT * OMISSION_FRACTION))
        omitted_case_ids = set(rand.sample(range(EVENT_COUNT), min(EVENT_COUNT, omission_count)))
        log(f"omission_pressure_selected omitted_case_count={len(omitted_case_ids)} mode={OMISSION_MODE}")

    for idx in range(EVENT_COUNT):
        logical_seen += 1
        if omission_active and idx in omitted_case_ids:
            if logical_seen == 1 or logical_seen % progress_interval == 0 or logical_seen == EVENT_COUNT:
                write_progress(
                    status="in_progress" if logical_seen < EVENT_COUNT else "complete",
                    produced_event_count=emitted,
                    produced_case_count=logical_seen,
                    logical_case_count=EVENT_COUNT,
                    started=started,
                )
            interval_ms = current_interval_ms(started)
            if interval_ms > 0:
                time.sleep(interval_ms / 1000.0)
            continue
        produced_at_epoch = time.time()
        event = {
            "event_id": idx,
            "case_id": idx,
            "boundary": BOUNDARY,
            "timestamp": produced_at_epoch,
            "produced_at_epoch": produced_at_epoch,
            "delivery_mode": DELIVERY_MODE,
            "extra_processing_delay_ms": SKEWED_TAIL_EXTRA_DELAY_MS if idx in delayed_case_ids else 0,
        }
        if DEADLINE_WINDOW_SECONDS > 0:
            event["deadline_window_seconds"] = DEADLINE_WINDOW_SECONDS
            event["deadline_at_epoch"] = produced_at_epoch + DEADLINE_WINDOW_SECONDS
        payload = json.dumps(event)
        publish_payload(client, payload)
        if duplicate_active and idx in duplicate_case_ids:
            repeats = max(1, DUPLICATE_REPEATS) if DUPLICATE_MODE == "selected_cases_twice" else 1
            for attempt in range(1, repeats + 1):
                if DUPLICATE_DELAY_MS > 0:
                    time.sleep(DUPLICATE_DELAY_MS / 1000.0)
                if DUPLICATE_JITTER_MS > 0:
                    jitter = rand.randint(0, DUPLICATE_JITTER_MS) / 1000.0
                    if jitter > 0:
                        time.sleep(jitter)
                duplicate_payload = json.loads(payload)
                duplicate_payload["duplicate_attempt"] = attempt
                duplicate_payload["original_event_id"] = idx
                duplicate_payload["duplicate_mode"] = DUPLICATE_MODE
                publish_payload(client, json.dumps(duplicate_payload))
                duplicate_emissions += 1
        emitted += 1
        if logical_seen == 1 or logical_seen % progress_interval == 0 or logical_seen == EVENT_COUNT:
            write_progress(
                status="in_progress" if logical_seen < EVENT_COUNT else "complete",
                produced_event_count=emitted,
                produced_case_count=logical_seen,
                logical_case_count=EVENT_COUNT,
                started=started,
            )
        interval_ms = current_interval_ms(started)
        if interval_ms > 0:
            time.sleep(interval_ms / 1000.0)
    return emitted, len(delayed_case_ids), len(duplicate_case_ids), duplicate_emissions, len(omitted_case_ids)


def emit_state_non_regression_events(client: redis.Redis, started: float, rand: random.Random) -> tuple[int, int, int, int]:
    entity_count = EVENT_COUNT
    obsolete_replay_entities: set[int] = set()
    if STATE_OBSOLETE_REPLAY_FRACTION > 0 and UPDATES_PER_ENTITY >= 2:
        replay_count = max(1, int(entity_count * STATE_OBSOLETE_REPLAY_FRACTION))
        obsolete_replay_entities = set(rand.sample(range(entity_count), min(entity_count, replay_count)))
        log(f"state_obsolete_replay_selected entity_count={len(obsolete_replay_entities)} updates_per_entity={UPDATES_PER_ENTITY}")

    emitted_events = 0
    total_primary_events = max(1, entity_count * UPDATES_PER_ENTITY)

    # Emit by version rounds rather than per entity. A bounded exposed slice is defined
    # within one chosen version round so that the run can distinguish between
    # recoverability-sensitive loss of that slice and later forward resumption to a newer
    # state. This supports both the current non-regression pilot and the lighter
    # ephemeral-display interpretation without changing the overall suite skeleton.
    first_exposed_entity_id = state_outage_first_exposed_entity_id(entity_count, STATE_OUTAGE_EXPOSED_START_FRACTION)

    for version in range(1, UPDATES_PER_ENTITY + 1):
        for entity_id in range(entity_count):
            produced_at_epoch = time.time()
            outage_exposed = bool(
                DISTURBANCE == "interruption"
                and version == STATE_OUTAGE_EXPOSED_VERSION
                and entity_id >= first_exposed_entity_id
            )
            event = {
                "event_id": emitted_events,
                "case_id": entity_id,
                "entity_id": entity_id,
                "version": version,
                "latest_version": UPDATES_PER_ENTITY,
                "state_outage_exposed_version": STATE_OUTAGE_EXPOSED_VERSION,
                "state_forward_resumption_version": STATE_FORWARD_RESUMPTION_VERSION,
                "boundary": BOUNDARY,
                "timestamp": produced_at_epoch,
                "produced_at_epoch": produced_at_epoch,
                "delivery_mode": DELIVERY_MODE,
                "extra_processing_delay_ms": 0,
                "state_obsolete_replay": False,
                "state_version_round": version,
                "state_outage_exposed": outage_exposed,
            }
            publish_payload(client, json.dumps(event))
            emitted_events += 1
            if emitted_events == 1 or emitted_events % max(1, entity_count // 5) == 0 or emitted_events == total_primary_events:
                approx_cases = min(entity_count, max(0, emitted_events // UPDATES_PER_ENTITY))
                write_progress(
                    status="in_progress",
                    produced_event_count=emitted_events,
                    produced_case_count=approx_cases,
                    logical_case_count=entity_count,
                    started=started,
                    progress_fraction_override=round(emitted_events / total_primary_events, 6),
                )
            interval_ms = current_interval_ms(started)
            if interval_ms > 0:
                time.sleep(interval_ms / 1000.0)

    # Optional stale replays happen after the latest-version round so they are genuinely obsolete.
    for idx, entity_id in enumerate(sorted(obsolete_replay_entities), start=1):
        produced_at_epoch = time.time()
        stale_version = max(1, UPDATES_PER_ENTITY - 1)
        replay = {
            "event_id": emitted_events,
            "case_id": entity_id,
            "entity_id": entity_id,
            "version": stale_version,
            "latest_version": UPDATES_PER_ENTITY,
            "boundary": BOUNDARY,
            "timestamp": produced_at_epoch,
            "produced_at_epoch": produced_at_epoch,
            "delivery_mode": DELIVERY_MODE,
            "extra_processing_delay_ms": 0,
            "state_obsolete_replay": True,
            "state_version_round": stale_version,
        }
        publish_payload(client, json.dumps(replay))
        emitted_events += 1
        interval_ms = current_interval_ms(started)
        if interval_ms > 0:
            time.sleep(interval_ms / 1000.0)
        if idx == len(obsolete_replay_entities):
            write_progress(
                status="complete",
                produced_event_count=emitted_events,
                produced_case_count=entity_count,
                logical_case_count=entity_count,
                started=started,
                progress_fraction_override=1.0,
            )

    if not obsolete_replay_entities:
        write_progress(
            status="complete",
            produced_event_count=emitted_events,
            produced_case_count=entity_count,
            logical_case_count=entity_count,
            started=started,
            progress_fraction_override=1.0,
        )
    return emitted_events, 0, 0, 0


def main() -> int:
    producer_started.write_text(
        json.dumps(
            {
                "status": "started",
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "delivery_mode": DELIVERY_MODE,
                "boundary": BOUNDARY,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(
        f"starting delivery_mode={DELIVERY_MODE} boundary={BOUNDARY} event_count={EVENT_COUNT} disturbance={DISTURBANCE} start_delay={PRODUCER_START_DELAY_SECONDS}"
    )
    if PRODUCER_START_DELAY_SECONDS > 0:
        time.sleep(PRODUCER_START_DELAY_SECONDS)
    client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    started = time.time()
    rand = random.Random(SCENARIO_SEED)

    if BOUNDARY == "state_non_regression":
        produced_events, delayed_count, duplicate_case_count, duplicate_emissions = emit_state_non_regression_events(client, started, rand)
        omitted_case_count = 0
        produced_case_count = EVENT_COUNT
        logical_case_count = EVENT_COUNT
    else:
        produced_events, delayed_count, duplicate_case_count, duplicate_emissions, omitted_case_count = emit_standard_events(client, started, rand)
        produced_case_count = produced_events
        logical_case_count = EVENT_COUNT

    producer_complete.write_text(
        json.dumps(
            {
                "status": "complete",
                "produced_event_count": produced_events,
                "produced_case_count": produced_case_count,
                "duration_seconds": round(time.time() - started, 6),
                "delivery_mode": DELIVERY_MODE,
                "scenario_seed": SCENARIO_SEED,
                "skewed_tail_delayed_case_count": delayed_count,
                "boundary": BOUNDARY,
                "deadline_window_seconds": DEADLINE_WINDOW_SECONDS,
                "duplicate_case_count": duplicate_case_count,
                "duplicate_emissions": duplicate_emissions,
                "omitted_case_count": omitted_case_count,
                "logical_case_count": logical_case_count,
                "updates_per_entity": UPDATES_PER_ENTITY,
                "state_obsolete_replay_fraction": STATE_OBSOLETE_REPLAY_FRACTION,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"finished produced_events={produced_events} produced_cases={produced_case_count}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(f"failed error={exc!r}")
        producer_complete.write_text(
            json.dumps({"status": "failed", "error": repr(exc)}, indent=2),
            encoding="utf-8",
        )
        raise
