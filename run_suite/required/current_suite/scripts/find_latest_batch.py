from __future__ import annotations

import sys
from pathlib import Path

from batch_utils import ROOT, find_latest_batch


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit('Usage: find_latest_batch.py <profile_name>')
    profile_name = argv[1]
    output_batches = ROOT / 'output' / 'batches'
    latest = find_latest_batch(profile_name, output_batches)
    if latest is None:
        return 1
    print(latest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
