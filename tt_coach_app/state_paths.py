from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class StatePaths:
    root: Path
    bandit_state: Path
    sessions_log: Path

def get_state_paths(project_root: Path) -> StatePaths:
    state_root = project_root / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    return StatePaths(
        root=state_root,
        bandit_state=state_root / "bandit_state.json",
        sessions_log=state_root / "sessions.jsonl",
    )
