import json
import os
import random
import time
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
PRODUCER_PROGRESS_INTERVAL_MS = int(env("PRODUCER_PROGRESS_INTERVAL_MS", "100"))

ARTIFACTS_DIR = Path(env("ARTIFACTS_DIR", "/run/artifacts"))
LOGS_DIR = Path(env("LOGS_DIR", "/run/logs"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

log_path = LOGS_DIR / "producer.log"
producer_started = ARTIFACTS_DIR / "producer_started.json"
producer_complete = ARTIFACTS_DIR / "producer_complete.json"
producer_progress = ARTIFACTS_DIR / "producer_progress.json"
producer_timeline = ARTIFACTS_DIR / "producer_timeline.csv"


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


def main() -> int:
    producer_started.write_text(
        json.dumps(
            {
                "status": "started",
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "delivery_mode": DELIVERY_MODE,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(
        f"starting delivery_mode={DELIVERY_MODE} event_count={EVENT_COUNT} disturbance={DISTURBANCE} start_delay={PRODUCER_START_DELAY_SECONDS}"
    )
    if PRODUCER_START_DELAY_SECONDS > 0:
        time.sleep(PRODUCER_START_DELAY_SECONDS)
    client = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    produced = 0
    started = time.time()
    rand = random.Random(SCENARIO_SEED)
    progress_interval = max(1, EVENT_COUNT // 20)
    last_progress_write = 0.0
    producer_timeline.write_text("case_id,produced_at_epoch,deadline_at_epoch\n", encoding="utf-8")

    delayed_case_ids = set()
    if DISTURBANCE == "skewed_tail" and SKEWED_TAIL_FRACTION > 0 and SKEWED_TAIL_EXTRA_DELAY_MS > 0:
        delayed_count = max(1, int(EVENT_COUNT * SKEWED_TAIL_FRACTION))
        delayed_case_ids = set(rand.sample(range(EVENT_COUNT), min(EVENT_COUNT, delayed_count)))
        log(f"skewed_tail_selected delayed_count={len(delayed_case_ids)} extra_delay_ms={SKEWED_TAIL_EXTRA_DELAY_MS}")

    for idx in range(EVENT_COUNT):
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
        deadline_at_epoch = event.get("deadline_at_epoch")
        with producer_timeline.open("a", encoding="utf-8") as fh:
            fh.write(f"{idx},{produced_at_epoch:.6f},{'' if deadline_at_epoch is None else f'{float(deadline_at_epoch):.6f}'}\n")
        if DELIVERY_MODE == "retained":
            client.xadd(STREAM_KEY, {"payload": payload})
        else:
            client.publish(CHANNEL_KEY, payload)
        produced += 1
        now = time.time()
        should_write_progress = (
            produced == 1
            or produced % progress_interval == 0
            or produced == EVENT_COUNT
            or ((now - last_progress_write) * 1000.0) >= PRODUCER_PROGRESS_INTERVAL_MS
        )
        if should_write_progress:
            producer_progress.write_text(
                json.dumps(
                    {
                        "status": "in_progress" if produced < EVENT_COUNT else "complete",
                        "produced_event_count": produced,
                        "event_count": EVENT_COUNT,
                        "progress_fraction": round(produced / EVENT_COUNT, 6) if EVENT_COUNT > 0 else 0.0,
                        "elapsed_seconds": round(now - started, 6),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            last_progress_write = now
        interval_ms = current_interval_ms(started)
        if interval_ms > 0:
            time.sleep(interval_ms / 1000.0)

    producer_complete.write_text(
        json.dumps(
            {
                "status": "complete",
                "produced_event_count": produced,
                "duration_seconds": round(time.time() - started, 6),
                "delivery_mode": DELIVERY_MODE,
                "scenario_seed": SCENARIO_SEED,
                "skewed_tail_delayed_case_count": len(delayed_case_ids),
                "boundary": BOUNDARY,
                "deadline_window_seconds": DEADLINE_WINDOW_SECONDS,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"finished produced={produced}")
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
