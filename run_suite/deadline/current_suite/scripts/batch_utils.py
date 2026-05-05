from __future__ import annotations

import csv
import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def slugify_project_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() else '_' for ch in value.lower()).strip('_')


def timestamped_batch_name(profile_name: str) -> str:
    from datetime import datetime
    return f"{profile_name}_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def summarize_numeric(values: list[float]) -> dict[str, float]:
    return {
        'mean': round(mean(values), 6),
        'std': round(std(values), 6),
        'median': round(median(values), 6),
        'min': round(min(values), 6) if values else 0.0,
        'max': round(max(values), 6) if values else 0.0,
    }


def group_by(rows: list[dict[str, Any]], key_fields: list[str]) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        grouped[key].append(row)
    return grouped


def find_latest_batch(profile_name: str, output_batches_dir: Path) -> Path | None:
    candidates = sorted([p for p in output_batches_dir.iterdir() if p.is_dir() and p.name.startswith(profile_name + '_')])
    return candidates[-1] if candidates else None
