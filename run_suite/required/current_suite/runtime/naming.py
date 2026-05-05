from __future__ import annotations

def run_dir_name(scenario_id: str, repeat_index: int) -> str:
    return f"{scenario_id}__rep{repeat_index:02d}"
