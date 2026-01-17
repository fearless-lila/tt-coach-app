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



if __name__ == "__main__":
    out = recommend(
        "banana flick short serve",
        top_k=5,
        context={"skill": "intermediate"}
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))

