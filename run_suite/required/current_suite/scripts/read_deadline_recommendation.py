from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCHES = ROOT / "output" / "batches"


def latest_calibration_batch() -> Path | None:
    candidates = sorted([p for p in BATCHES.iterdir() if p.is_dir() and p.name.startswith("deadline_calibration_")])
    return candidates[-1] if candidates else None


def main(argv: list[str]) -> int:
    batch = latest_calibration_batch()
    if batch is None:
        return 1
    path = batch / "aggregates" / "deadline_selection_recommendation.json"
    if not path.exists():
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("recommended_deadline_window_seconds")
    if value is None:
        return 1
    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
