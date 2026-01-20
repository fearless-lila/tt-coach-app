from __future__ import annotations

import sys
import json
from pathlib import Path

# --- Add the bandit repo to Python path ---
BANDIT_REPO = Path(__file__).resolve().parents[2] / "table-tennis-multi-armed-bandit"
sys.path.insert(0, str(BANDIT_REPO))

from tt_semantic_search import SearchEngine
from app.bandit import UCB1Bandit



def recommend(query: str, top_k: int = 5, context: dict | None = None):
    search_engine = SearchEngine(mode="hybrid")
    results = search_engine.search(query, top_k=top_k)

    candidates = [r.id for r in results]

    bandit = UCB1Bandit()
    chosen_id = bandit.select(candidates, context=context)

    # Build a richer payload for UI/chat
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

    return {
        "query": query,
        "mode": "hybrid",
        "top_k": top_k,
        "context": context or {},
        "ranked_candidates": ranked,
        "chosen": chosen,
    }

def simulate_reward(chosen_id: str) -> float:
    """
    MVP reward signal.
    Pretend drill_003 is always the 'best' choice.
    """
    return 1.0 if chosen_id == "drill_003" else 0.0

def train_loop(query: str, steps: int = 30):
    search_engine = SearchEngine(mode="hybrid")
    bandit = UCB1Bandit()

    counts: dict[str, int] = {}

    for i in range(steps):
        results = search_engine.search(query, top_k=5)
        candidates = [r.id for r in results]

        chosen = bandit.select(candidates)
        reward = simulate_reward(chosen)

        bandit.update(chosen, reward)

        counts[chosen] = counts.get(chosen, 0) + 1

    return counts

def simulate_feedback(chosen: dict) -> float:
    """
    MVP feedback: return a reward in [0, 1].
    Later this becomes real user input (1-5 rating) or completion signal.
    """
    # Simple heuristic: if difficulty matches skill, reward higher
    # (This is just to prove the learning loop works.)
    return 1.0


if __name__ == "__main__":
    counts = train_loop("banana flick short serve", steps=40)
    print("\nSelection counts after training:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{k}: {v}")


