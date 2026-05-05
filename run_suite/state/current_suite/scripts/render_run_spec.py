from __future__ import annotations

import json
import sys
from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def convert(value: str):
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        if value.startswith("0") and value not in {"0", "0.0"} and not value.startswith("0."):
            raise ValueError
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("Usage: render_run_spec.py <scenario.env> <output.json>")
    env_path = Path(argv[1])
    out_path = Path(argv[2])
    raw = parse_env(env_path)
    rendered = {key.lower(): convert(value) for key, value in raw.items()}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rendered, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
