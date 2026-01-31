from __future__ import annotations

import os
import uuid
import re
from dataclasses import dataclass
from pathlib import Path

from tt_coach_app.session_log import AuditEvent, append_jsonl, utc_now_iso
from tt_coach_app.state_paths import get_state_paths
from tt_semantic_search import SearchEngine

from tt_bandit import UCB1Bandit


def bandit_state_path_for_context(paths, ctx_key: str) -> Path:
    # Example: state/bandit_state__skill=intermediate__goal=backhand.json
    return paths.bandit_state.parent / f"bandit_state__{ctx_key}.json"

def build_or_load_bandit_for_context(project_root: Path, ctx_key: str) -> UCB1Bandit:
    paths = get_state_paths(project_root)
    state_path = bandit_state_path_for_context(paths, ctx_key)

    reset = os.getenv("RESET_BANDIT") == "1"
    cold_start = os.getenv("COLD_START") == "1"

    if reset:
        b = UCB1Bandit()
        b.save_json(str(state_path))
        return b

    if cold_start:
        # Cold start = do not load existing + do not persist (handled in caller)
        return UCB1Bandit()

    if state_path.exists():
        return UCB1Bandit.load_json(str(state_path))

    b = UCB1Bandit()
    b.save_json(str(state_path))
    return b


def bandit_snapshot(bandit: UCB1Bandit, arm_ids: list[str]) -> dict[str, dict[str, float]]:
    """
    Return pulls + mean reward for the given arms.
    Snapshot is post-update if called after update().
    """
    snapshot: dict[str, dict[str, float]] = {}
    for arm_id in arm_ids:
        s = bandit.stats.get(arm_id)
        if not s or s.pulls == 0:
            snapshot[arm_id] = {"pulls": 0, "mean": 0.0}
        else:
            snapshot[arm_id] = {
                "pulls": float(s.pulls),
                "mean": float(s.total_reward) / float(s.pulls),
            }
    return snapshot


def build_or_load_bandit(project_root: Path) -> UCB1Bandit:
    """
    Step 20 policy:
    - RESET_BANDIT=1: destructive reset (overwrites bandit_state.json)
    - COLD_START=1: ignore existing state (returns fresh bandit) and should NOT persist
      (persistence is gated in online_recommend_and_learn)
    - default: load if exists, else create + persist initial file
    """
    paths = get_state_paths(project_root)

    reset = os.getenv("RESET_BANDIT") == "1"
    cold_start = os.getenv("COLD_START") == "1"

    if reset:
        bandit = UCB1Bandit()
        bandit.save_json(str(paths.bandit_state))
        return bandit

    if cold_start:
        return UCB1Bandit()

    if paths.bandit_state.exists():
        return UCB1Bandit.load_json(str(paths.bandit_state))

    bandit = UCB1Bandit()
    bandit.save_json(str(paths.bandit_state))
    return bandit


def prompt_rating_1_to_5() -> tuple[float, str]:
    """
    Terminal MVP feedback.
    Returns: (reward in [0,1], raw_input)
    """
    while True:
        raw = input("Rate this recommendation (1-5), or press Enter to skip: ").strip()
        if raw == "":
            # MVP behaviour: treat skip as 0.0
            # If you want production-like behaviour, return (None, "") and don't update.
            return 0.0, ""

        if raw.isdigit():
            rating = int(raw)
            if 1 <= rating <= 5:
                reward = (rating - 1) / 4.0
                return reward, raw

        print("Please enter a number 1-5, or press Enter to skip.")


def online_recommend_and_learn(query: str, top_k: int = 5, context: dict | None = None):
    project_root = Path(".").resolve()
    paths = get_state_paths(project_root)
    ctx = prompt_context()
    ctx_key = context_key(ctx)


    run_id = str(uuid.uuid4())

    search_engine = SearchEngine(mode="hybrid")
    results = search_engine.search(query, top_k=top_k)
    candidates: list[str] = [r.id for r in results]

    # --- Step 19: Priors from search relevance (soft bias) ---
    score_by_id: dict[str, float] = {r.id: float(r.score) for r in results}
    scores = list(score_by_id.values())
    s_min = min(scores) if scores else 0.0
    s_max = max(scores) if scores else 1.0
    denom = (s_max - s_min) if (s_max - s_min) > 1e-12 else 1.0

    def prior_mean_fn(arm_id: str, _context: dict | None = None) -> float:
        raw = score_by_id.get(arm_id, s_min)
        return (raw - s_min) / denom  # normalized to [0, 1]

    prior_pulls = 3
    # --- end Step 19 ---

    bandit = build_or_load_bandit_for_context(project_root, ctx_key)
    chosen_id = bandit.select(
        arm_ids=candidates,
        context=context,
        prior_mean_fn=prior_mean_fn,
        prior_pulls=prior_pulls,
    )

    # Print a simple UI to the terminal
    print("\nTop candidates (search order):")
    for idx, r in enumerate(results, start=1):
        mark = " <== chosen" if r.id == chosen_id else ""
        print(f"{idx:2d}. {r.id} | {r.title} | score={r.score:.3f}{mark}")

    reward, feedback_raw = prompt_rating_1_to_5()
    feedback_source = "explicit_terminal_rating" if feedback_raw != "" else "explicit_terminal_skip"

    # --- Step 20: persistence policy ---
    # Cold start runs should NOT modify bandit_state.json
    persist_learning = os.getenv("COLD_START") != "1"

    persist_learning = os.getenv("COLD_START") != "1"
    state_path = bandit_state_path_for_context(paths, ctx_key)

    bandit.update(chosen_id, reward)
    if persist_learning:
        bandit.save_json(str(state_path))


    # --- end Step 20 ---

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
        context={"skill": ctx.skill, "goal": ctx.goal},
        meta={
            "run_id": run_id,
            "context_key": ctx_key,
            "bandit_state_file": str(state_path.name),
            "prior_pulls": prior_pulls,
            "score_min": s_min,
            "score_max": s_max,
            "cold_start": os.getenv("COLD_START") == "1",
            "persist_learning": persist_learning,
            "bandit_snapshot": bandit_snapshot(bandit, candidates),
        },
        feedback_source=feedback_source,
        feedback_raw=feedback_raw,
    )

    append_jsonl(paths.sessions_log, evt.to_dict())

    print(f"\nRecorded reward={reward:.2f} for chosen_id={chosen_id}")
    return chosen_id, reward


def main() -> None:
    print("Terminal Feedback MVP. Ctrl+C to exit.\n")

    if os.getenv("RESET_LOGS") == "1":
        paths = get_state_paths(Path(".").resolve())
        if paths.sessions_log.exists():
            paths.sessions_log.unlink()

    try:
        last_query = "banana flick short serve"
        while True:
            q = input("Enter a query (or press Enter to reuse last): ").strip()
            if q == "":
                q = last_query
            else:
                last_query = q

            online_recommend_and_learn(q, top_k=5, context=None)
            print("-" * 60)
    except KeyboardInterrupt:
        print("\nExiting.")


@dataclass(frozen=True)
class UserContext:
    skill: str         # beginner | intermediate | advanced
    goal: str          # backhand | forehand | serve | footwork | receive

def prompt_context() -> UserContext:
    def pick(prompt: str, options: list[str], default: str) -> str:
        opts = "/".join(options)
        raw = input(f"{prompt} ({opts}) [default={default}]: ").strip().lower()
        if raw == "":
            return default
        if raw in options:
            return raw
        print(f"Invalid. Using default={default}.")
        return default

    skill = pick("Skill", ["beginner", "intermediate", "advanced"], "intermediate")
    goal = pick("Goal", ["backhand", "forehand", "serve", "footwork", "receive"], "backhand")
    return UserContext(skill=skill, goal=goal)

def context_key(ctx: UserContext) -> str:
    """
    Stable, filesystem-safe key.
    """
    raw = f"skill={ctx.skill}|goal={ctx.goal}"
    safe = re.sub(r"[^a-z0-9=_|.-]+", "-", raw.lower())
    safe = safe.replace("|", "__")
    return safe


if __name__ == "__main__":
    main()

