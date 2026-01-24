from __future__ import annotations

from tt_coach_app.session_log import AuditEvent, append_jsonl, utc_now_iso

import sys
from pathlib import Path

# --- Add the bandit repo to Python path ---
BANDIT_REPO = Path(__file__).resolve().parents[2] / "table-tennis-multi-armed-bandit"
sys.path.insert(0, str(BANDIT_REPO))

from tt_semantic_search import SearchEngine
from app.bandit import UCB1Bandit
from tt_coach_app.state_paths import get_state_paths

import uuid
from tt_coach_app.session_log import AuditEvent, append_jsonl, utc_now_iso

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

    evt = AuditEvent(
        ts_utc=utc_now_iso(),
        event="recommend",
        query=query,
        mode="hybrid",
        top_k=top_k,
        candidates=[{"id": r.id, "score": r.score, "title": r.title} for r in results],
        chosen_id=chosen_id,
        reward=None,
        context=context or {},
        meta=None,
    )
    append_jsonl(paths.sessions_log, evt.to_dict())

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
    project_root = Path(".").resolve()
    paths = get_state_paths(project_root)

    search_engine = SearchEngine(mode="hybrid")
    bandit = build_or_load_bandit(project_root)

    counts: dict[str, int] = {}

    for i in range(steps):
        results = search_engine.search(query, top_k=5)
        candidates: list[str] = [r.id for r in results]

        chosen = bandit.select(candidates)
        reward = simulate_reward(chosen)

        bandit.update(chosen, reward)
        bandit.save_json(str(paths.bandit_state))

        # --- Step 17: audit log (append-only) ---
        candidate_payload = [
            {
                "id": r.id,
                "score": getattr(r, "score", None),
                "title": getattr(r, "title", None),
            }
            for r in results
        ]

        evt = AuditEvent(
            ts_utc=utc_now_iso(),
            event="train_step",
            query=query,
            mode="hybrid",
            top_k=5,
            candidates=candidate_payload,
            chosen_id=chosen,
            reward=reward,
            context=None,
            meta={"step": i},
        )
        append_jsonl(paths.sessions_log, evt.to_dict())
        # --- end audit log ---

        counts[chosen] = counts.get(chosen, 0) + 1

    return counts



def simulate_feedback(chosen: dict) -> float:
    return 1.0

def prompt_rating_1_to_5() -> tuple[float, str]:
    """
    Terminal MVP feedback.
    Returns: (reward in [0,1], raw_input)
    """
    while True:
        raw = input("Rate this recommendation (1-5), or press Enter to skip: ").strip()
        if raw == "":
            return 0.0, ""  # treat skip as neutral/zero for MVP; you can change later

        if raw.isdigit():
            rating = int(raw)
            if 1 <= rating <= 5:
                reward = (rating - 1) / 4.0
                return reward, raw

        print("Please enter a number 1-5, or press Enter to skip.")

def online_recommend_and_learn(query: str, top_k: int = 5, context: dict | None = None):
    project_root = Path(".").resolve()
    paths = get_state_paths(project_root)

    run_id = str(uuid.uuid4())

    search_engine = SearchEngine(mode="hybrid")
    results = search_engine.search(query, top_k=top_k)

    candidates: list[str] = [r.id for r in results]

    bandit = build_or_load_bandit(project_root)
    chosen_id = bandit.select(candidates, context=context)

    # Print a simple UI to the terminal
    print("\nTop candidates (search order):")
    for idx, r in enumerate(results, start=1):
        mark = " <== chosen" if r.id == chosen_id else ""
        print(f"{idx:2d}. {r.id} | {r.title} | score={r.score:.3f}{mark}")

    # --- Step 18: collect explicit feedback ---
    reward, feedback_raw = prompt_rating_1_to_5()
    feedback_source = "explicit_terminal_rating" if feedback_raw != "" else "explicit_terminal_skip"

    # Update + persist
    bandit.update(chosen_id, reward)
    bandit.save_json(str(paths.bandit_state))

    # Audit log
    candidate_payload = [
        {"id": r.id, "score": getattr(r, "score", None), "title": getattr(r, "title", None)}
        for r in results
    ]

    evt = AuditEvent(
        ts_utc=utc_now_iso(),
        event="recommend_and_learn",
        query=query,
        mode="hybrid",
        top_k=top_k,
        candidates=candidate_payload,
        chosen_id=chosen_id,
        reward=reward,
        context=context or {},
        meta={"run_id": run_id},
        feedback_source=feedback_source,
        feedback_raw=feedback_raw,
    )
    append_jsonl(paths.sessions_log, evt.to_dict())

    print(f"\nRecorded reward={reward:.2f} for chosen_id={chosen_id}")
    return chosen_id, reward

if __name__ == "__main__":
    print("Terminal Feedback MVP (Step 18). Ctrl+C to exit.\n")

    while True:
        q = input("Enter a query (or press Enter to reuse last): ").strip()
        if q == "":
            q = "banana flick short serve"

        online_recommend_and_learn(q, top_k=5, context=None)
        print("-" * 60)

