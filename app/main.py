from __future__ import annotations

import sys
from pathlib import Path

# --- Add the bandit repo to Python path ---
BANDIT_REPO = Path(__file__).resolve().parents[2] / "table-tennis-multi-armed-bandit"
sys.path.insert(0, str(BANDIT_REPO))

from tt_semantic_search import SearchEngine
from app.bandit import UCB1Bandit
from tt_coach_app.state_paths import get_state_paths


def build_or_load_bandit(project_root: Path) -> UCB1Bandit:
    paths = get_state_paths(project_root)

    if paths.bandit_state.exists():
        return UCB1Bandit.load_json(str(paths.bandit_state))

    bandit = UCB1Bandit()
    bandit.save_json(str(paths.bandit_state))  # explicit initial state file
    return bandit


def recommend(query: str, top_k: int = 5, context: dict | None = None):
    project_root = Path(".").resolve()  # adjust if your root differs
    paths = get_state_paths(project_root)

    search_engine = SearchEngine(mode="hybrid")
    results = search_engine.search(query, top_k=top_k)
    candidates: list[str] = [r.id for r in results]

    bandit = build_or_load_bandit(project_root)
    chosen_id = bandit.select(candidates, context=context)

    ranked = [
        {
            "id": r.id,
            "title": r.title,
            "score": r.score,
            "difficulty": (r.metadata or {}).get("difficulty"),
            "tags": (r.metadata or {}).get("tags", []),
        }
        for r in results
    ]

    chosen = next((x for x in ranked if x["id"] == chosen_id), {"id": chosen_id})

    # If you have feedback here, you can learn here too:
    # reward = simulate_feedback(chosen)
    # bandit.update(chosen_id, reward)
    # bandit.save_json(str(paths.bandit_state))

    return {
        "query": query,
        "mode": "hybrid",
        "top_k": top_k,
        "context": context or {},
        "ranked_candidates": ranked,
        "chosen": chosen,
    }


def simulate_reward(chosen_id: str) -> float:
    return 1.0 if chosen_id == "drill_003" else 0.0


def train_loop(query: str, steps: int = 30):
    project_root = Path(".").resolve()  # adjust if your root differs
    paths = get_state_paths(project_root)

    search_engine = SearchEngine(mode="hybrid")
    bandit = build_or_load_bandit(project_root)

    counts: dict[str, int] = {}

    for _ in range(steps):
        results = search_engine.search(query, top_k=5)
        candidates: list[str] = [r.id for r in results]

        chosen = bandit.select(candidates)
        reward = simulate_reward(chosen)

        bandit.update(chosen, reward)
        bandit.save_json(str(paths.bandit_state))  # persistence per step

        counts[chosen] = counts.get(chosen, 0) + 1

    return counts


def simulate_feedback(chosen: dict) -> float:
    return 1.0


if __name__ == "__main__":
    counts = train_loop("banana flick short serve", steps=40)
    print("\nSelection counts after training:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{k}: {v}")
