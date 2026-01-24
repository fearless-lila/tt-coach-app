from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@dataclass
class AuditEvent:
    ts_utc: str
    event: str                  # e.g. "train_step" or "recommend"
    query: str
    mode: str
    top_k: int
    candidates: list[dict[str, Any]]
    chosen_id: str
    reward: Optional[float] = None
    context: Optional[dict[str, Any]] = None
    meta: Optional[dict[str, Any]] = None
    # in AuditEvent dataclass
    feedback_source: str | None = None   # e.g. "explicit_terminal"
    feedback_raw: str | None = None      # e.g. "4"


    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
