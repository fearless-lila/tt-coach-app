from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class EventRow:
    reward: float
    chosen_id: str
    context_key: str
    decision_scope: str
    chosen_rank: int | None


def safe_get(d: dict[str, Any], path: list[str], default=None):
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def load_jsonl(path: Path, last: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Log not found: {path}")

    rows: list[dict[str, Any]] = []
    if last is None:
        # load all (fine for small logs)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    # load last N efficiently
    dq: deque[str] = deque(maxlen=last)
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                dq.append(line)

    for line in dq:
        rows.append(json.loads(line))
    return rows


def compute_chosen_rank(candidates: list[dict[str, Any]], chosen_id: str) -> int | None:
    """
    candidates are in *search order* in your logs.
    Return 1-based rank of chosen in that list, or None if not found.
    """
    for i, c in enumerate(candidates, start=1):
        if c.get("id") == chosen_id:
            return i
    return None


def to_event_rows(raw: list[dict[str, Any]]) -> list[EventRow]:
    out: list[EventRow] = []
    for r in raw:
        if r.get("event") != "recommend_and_learn":
            continue

        reward = r.get("reward")
        chosen_id = r.get("chosen_id")
        if reward is None or chosen_id is None:
            continue

        meta = r.get("meta") or {}
        decision_scope = meta.get("decision_scope", "unknown")
        context_key = meta.get("context_key") or "unknown_context"

        candidates = r.get("candidates") or []
        chosen_rank = compute_chosen_rank(candidates, chosen_id)

        out.append(
            EventRow(
                reward=float(reward),
                chosen_id=str(chosen_id),
                context_key=str(context_key),
                decision_scope=str(decision_scope),
                chosen_rank=chosen_rank,
            )
        )
    return out


def rolling_avg(values: list[float], window: int) -> list[float]:
    out: list[float] = []
    dq: deque[float] = deque()
    s = 0.0
    for v in values:
        dq.append(v)
        s += v
        if len(dq) > window:
            s -= dq.popleft()
        out.append(s / len(dq))
    return out


def print_report(rows: list[EventRow], window: int = 20) -> None:
    if not rows:
        print("No recommend_and_learn rows found.")
        return

    rewards = [r.reward for r in rows]
    avg_reward = sum(rewards) / len(rewards)

    ra = rolling_avg(rewards, window=window)
    first = rewards[: min(50, len(rewards))]
    last = rewards[max(0, len(rewards) - min(50, len(rewards))) :]

    print("\n=== Step 24 Report: sessions.jsonl ===")
    print(f"events: {len(rows)}")
    print(f"avg_reward: {avg_reward:.3f}")
    print(f"first_{len(first)}_avg: {sum(first)/len(first):.3f}")
    print(f"last_{len(last)}_avg:  {sum(last)/len(last):.3f}")
    print(f"rolling_avg_window: {window}")
    print(f"rolling_avg_last: {ra[-1]:.3f}")

    # decision_scope breakdown
    scope_counts = defaultdict(int)
    for r in rows:
        scope_counts[r.decision_scope] += 1
    print("\n--- decision_scope breakdown ---")
    for k, v in sorted(scope_counts.items(), key=lambda x: -x[1]):
        print(f"{k:10s}: {v:4d} ({v/len(rows):.1%})")

    # chosen rank breakdown
    rank_counts = defaultdict(int)
    rank_rewards = defaultdict(list)
    for r in rows:
        if r.chosen_rank is None:
            rank_counts["not_in_candidates"] += 1
            continue
        rank_counts[r.chosen_rank] += 1
        rank_rewards[r.chosen_rank].append(r.reward)

    print("\n--- chosen rank vs search order ---")
    for k, v in sorted(rank_counts.items(), key=lambda x: (999 if isinstance(x[0], str) else x[0])):
        if isinstance(k, int):
            mean = sum(rank_rewards[k]) / len(rank_rewards[k]) if rank_rewards[k] else 0.0
            print(f"rank {k:2d}: {v:4d} ({v/len(rows):.1%}) | avg_reward={mean:.3f}")
        else:
            print(f"{k:16s}: {v:4d} ({v/len(rows):.1%})")

    # per-context winners
    ctx_arm_pulls = defaultdict(lambda: defaultdict(int))
    ctx_arm_rewards = defaultdict(lambda: defaultdict(float))
    ctx_scope = defaultdict(lambda: defaultdict(int))

    for r in rows:
        ctx = r.context_key
        ctx_arm_pulls[ctx][r.chosen_id] += 1
        ctx_arm_rewards[ctx][r.chosen_id] += r.reward
        ctx_scope[ctx][r.decision_scope] += 1

    print("\n--- per context_key summary (top 3 arms) ---")
    for ctx in sorted(ctx_arm_pulls.keys()):
        total = sum(ctx_arm_pulls[ctx].values())
        scopes = ctx_scope[ctx]
        scopes_str = ", ".join(f"{k}:{v}" for k, v in sorted(scopes.items(), key=lambda x: -x[1]))
        print(f"\ncontext_key: {ctx} | events={total} | scopes=({scopes_str})")

        arms = list(ctx_arm_pulls[ctx].items())
        arms.sort(key=lambda x: (-x[1], x[0]))
        for arm_id, pulls in arms[:3]:
            mean = ctx_arm_rewards[ctx][arm_id] / pulls
            print(f"  - {arm_id}: pulls={pulls:3d} mean_reward={mean:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze tt-coach-app sessions.jsonl")
    parser.add_argument("--log", type=str, default="state/sessions.jsonl", help="Path to sessions.jsonl")
    parser.add_argument("--last", type=int, default=500, help="Analyze last N lines")
    parser.add_argument("--window", type=int, default=20, help="Rolling average window size")
    args = parser.parse_args()

    path = Path(args.log)
    raw = load_jsonl(path, last=args.last)
    rows = to_event_rows(raw)
    print_report(rows, window=args.window)


if __name__ == "__main__":
    main()
