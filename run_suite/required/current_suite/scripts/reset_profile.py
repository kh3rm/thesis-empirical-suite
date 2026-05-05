from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from batch_utils import ROOT, find_latest_batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_name")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    batches_dir = ROOT / "output" / "batches"
    if args.all:
        for path in batches_dir.iterdir():
            if path.is_dir() and path.name.startswith(args.profile_name + "_"):
                shutil.rmtree(path)
                print(f"removed {path}")
    else:
        latest = find_latest_batch(args.profile_name, batches_dir)
        if latest:
            shutil.rmtree(latest)
            print(f"removed {latest}")
        else:
            print(f"no batch found for profile {args.profile_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
