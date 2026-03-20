from __future__ import annotations

import os
import uuid
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tt_coach_app.session_log import AuditEvent, append_jsonl, utc_now_iso
from tt_coach_app.state_paths import get_state_paths
from tt_semantic_search import SearchEngine

from tt_bandit import UCB1Bandit


_SUPERVISED_PREDICTOR = None


@dataclass(frozen=True)
class UserContext:
    skill: str         # beginner | intermediate | advanced
    goal: str          # backhand | forehand | serve | footwork | receive


@dataclass(frozen=True)
class RecommendationDecision:
    run_id: str
    query: str
    top_k: int
    mode: str
    context: UserContext
    context_key: str
    decision_scope: str
    context_total_pulls: int
    prior_pulls: int
    prior_source: str
    score_min: float
    score_max: float
    candidates: list[dict[str, Any]]
    chosen_id: str


def load_supervised_predictor():
    global _SUPERVISED_PREDICTOR
    if _SUPERVISED_PREDICTOR is not None:
        return _SUPERVISED_PREDICTOR

    supervised_root = Path(__file__).resolve().parents[2] / "tt-supervised-learning"
    model_path = supervised_root / "artifacts" / "model.joblib"
    schema_path = supervised_root / "artifacts" / "schema.json"
    predictor_path = supervised_root / "src"

    if not model_path.exists() or not schema_path.exists():
        return None

    import sys

    if str(predictor_path) not in sys.path:
        sys.path.insert(0, str(predictor_path))

    try:
        from predictor import Predictor
    except Exception:
        return None

    try:
        _SUPERVISED_PREDICTOR = Predictor(model_path=model_path, schema_path=schema_path)
    except Exception:
        return None

    return _SUPERVISED_PREDICTOR


def build_supervised_features(arm_id: str, ctx: UserContext) -> dict[str, Any]:
    return {
        "drill_id": arm_id,
        "focus": ctx.goal,
        "skill_level": ctx.skill,
    }


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
                "pulls": int(s.pulls),
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
MIN_CONTEXT_PULLS = 10

def global_bandit_state_path(paths) -> Path:
    return paths.bandit_state.parent / "bandit_state__global.json"

def build_or_load_global_bandit(project_root: Path) -> UCB1Bandit:
    paths = get_state_paths(project_root)
    p = global_bandit_state_path(paths)

    reset = os.getenv("RESET_BANDIT") == "1"
    cold_start = os.getenv("COLD_START") == "1"

    if reset:
        b = UCB1Bandit()
        b.save_json(str(p))
        return b

    if cold_start:
        # Cold start: ignore existing state; caller decides whether to persist
        return UCB1Bandit()

    if p.exists():
        return UCB1Bandit.load_json(str(p))

    b = UCB1Bandit()
    b.save_json(str(p))
    return b


def total_pulls_for_arms(bandit: UCB1Bandit, arm_ids: list[str]) -> int:
    total = 0
    for a in arm_ids:
        s = bandit.stats.get(a)
        total += s.pulls if s is not None else 0
    return total


def search_candidates(query: str, top_k: int = 5, mode: str = "hybrid") -> list[dict[str, Any]]:
    search_engine = SearchEngine(mode=mode)
    results = search_engine.search(query, top_k=top_k)
    return [
        {"id": r.id, "score": float(getattr(r, "score", 0.0)), "title": getattr(r, "title", r.id)}
        for r in results
    ]


def recommend_drill(query: str, ctx: UserContext, top_k: int = 5, mode: str = "hybrid") -> RecommendationDecision:
    project_root = Path(".").resolve()

    run_id = str(uuid.uuid4())
    ctx_key = context_key(ctx)
    candidates = search_candidates(query, top_k=top_k, mode=mode)
    arm_ids = [c["id"] for c in candidates]

    ctx_bandit = build_or_load_bandit_for_context(project_root, ctx_key)
    global_bandit = build_or_load_global_bandit(project_root)

    ctx_total = total_pulls_for_arms(ctx_bandit, arm_ids)
    use_global_backoff = ctx_total < MIN_CONTEXT_PULLS
    decision_bandit = global_bandit if use_global_backoff else ctx_bandit
    decision_scope = "global" if use_global_backoff else "context"

    score_by_id: dict[str, float] = {c["id"]: float(c["score"]) for c in candidates}
    scores = list(score_by_id.values())
    s_min = min(scores) if scores else 0.0
    s_max = max(scores) if scores else 1.0
    denom = (s_max - s_min) if (s_max - s_min) > 1e-12 else 1.0
    predictor = load_supervised_predictor()
    prior_source = "supervised" if predictor is not None else "search_score"

    def prior_mean_fn(arm_id: str, _context: dict | None = None) -> float:
        if predictor is not None:
            try:
                return float(predictor.predict_rate_one(build_supervised_features(arm_id, ctx)))
            except Exception:
                pass

        raw = score_by_id.get(arm_id, s_min)
        return (raw - s_min) / denom

    prior_pulls = 1 if predictor is not None else 3
    chosen_id = decision_bandit.select(
        arm_ids=arm_ids,
        context={"skill": ctx.skill, "goal": ctx.goal},
        prior_mean_fn=prior_mean_fn,
        prior_pulls=prior_pulls,
    )

    return RecommendationDecision(
        run_id=run_id,
        query=query,
        top_k=top_k,
        mode=mode,
        context=ctx,
        context_key=ctx_key,
        decision_scope=decision_scope,
        context_total_pulls=ctx_total,
        prior_pulls=prior_pulls,
        prior_source=prior_source,
        score_min=s_min,
        score_max=s_max,
        candidates=candidates,
        chosen_id=chosen_id,
    )


def record_feedback(
    decision: RecommendationDecision,
    reward: float,
    feedback_source: str,
    feedback_raw: str | None = None,
) -> tuple[str, float]:
    project_root = Path(".").resolve()
    paths = get_state_paths(project_root)

    persist_learning = os.getenv("COLD_START") != "1"

    ctx_state_path = bandit_state_path_for_context(paths, decision.context_key)
    global_state_path = global_bandit_state_path(paths)
    ctx_bandit = build_or_load_bandit_for_context(project_root, decision.context_key)
    global_bandit = build_or_load_global_bandit(project_root)

    ctx_bandit.update(decision.chosen_id, reward)
    global_bandit.update(decision.chosen_id, reward)

    if persist_learning:
        ctx_bandit.save_json(str(ctx_state_path))
        global_bandit.save_json(str(global_state_path))

    evt = AuditEvent(
        ts_utc=utc_now_iso(),
        event="recommend_and_learn",
        query=decision.query,
        mode=decision.mode,
        top_k=decision.top_k,
        candidates=decision.candidates,
        chosen_id=decision.chosen_id,
        reward=reward,
        context={"skill": decision.context.skill, "goal": decision.context.goal},
        meta={
            "run_id": decision.run_id,
            "context_key": decision.context_key,
            "decision_scope": decision.decision_scope,
            "context_total_pulls": decision.context_total_pulls,
            "min_context_pulls": MIN_CONTEXT_PULLS,
            "ctx_state_file": ctx_state_path.name,
            "global_state_file": global_state_path.name,
            "prior_pulls": decision.prior_pulls,
            "prior_source": decision.prior_source,
            "score_min": decision.score_min,
            "score_max": decision.score_max,
            "cold_start": os.getenv("COLD_START") == "1",
            "persist_learning": persist_learning,
            "bandit_snapshot_ctx": bandit_snapshot(ctx_bandit, [c["id"] for c in decision.candidates]),
            "bandit_snapshot_global": bandit_snapshot(global_bandit, [c["id"] for c in decision.candidates]),
        },
        feedback_source=feedback_source,
        feedback_raw=feedback_raw,
    )
    append_jsonl(paths.sessions_log, evt.to_dict())
    return decision.chosen_id, reward



def online_recommend_and_learn(query: str, top_k: int = 5, context: dict | None = None):
    ctx = prompt_context()
    decision = recommend_drill(query, ctx, top_k=top_k, mode="hybrid")

    # Print a simple UI to the terminal
    print(
        f"\nContext: skill={ctx.skill}, goal={ctx.goal} | "
        f"decision_scope={decision.decision_scope} | ctx_total_pulls={decision.context_total_pulls}"
    )
    print("\nTop candidates (search order):")
    for idx, candidate in enumerate(decision.candidates, start=1):
        mark = " <== chosen" if candidate["id"] == decision.chosen_id else ""
        print(f"{idx:2d}. {candidate['id']} | {candidate['title']} | score={candidate['score']:.3f}{mark}")

    reward, feedback_raw = prompt_rating_1_to_5()
    feedback_source = "explicit_terminal_rating" if feedback_raw != "" else "explicit_terminal_skip"
    chosen_id, reward = record_feedback(
        decision,
        reward=reward,
        feedback_source=feedback_source,
        feedback_raw=feedback_raw,
    )
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
