from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tt_coach_app.analyze_sessions import load_jsonl, to_event_rows
from tt_coach_app.main import RecommendationDecision, UserContext, recommend_drill, record_feedback
from tt_coach_app.state_paths import get_state_paths


PENDING_BY_RUN_ID: dict[str, RecommendationDecision] = {}
PENDING_LOCK = threading.Lock()


def reward_from_rating(rating: int) -> float:
    if not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    return (rating - 1) / 4.0


def recent_stats(limit: int = 100) -> dict[str, Any]:
    paths = get_state_paths(Path(".").resolve())
    if not paths.sessions_log.exists():
        return {"events": 0, "avg_reward": None, "recent_avg_reward": None}

    raw = load_jsonl(paths.sessions_log, last=limit)
    rows = to_event_rows(raw)
    if not rows:
        return {"events": 0, "avg_reward": None, "recent_avg_reward": None}

    rewards = [r.reward for r in rows]
    return {
        "events": len(rows),
        "avg_reward": round(sum(rewards) / len(rewards), 3),
        "recent_avg_reward": round(sum(rewards[-10:]) / len(rewards[-10:]), 3),
    }


def history_payload(limit: int = 10) -> dict[str, Any]:
    paths = get_state_paths(Path(".").resolve())
    if not paths.sessions_log.exists():
        return {
            "events": [],
            "summary": {
                "events": 0,
                "avg_reward": 0.0,
                "recent_avg_reward": 0.0,
                "global_count": 0,
                "context_count": 0,
            },
        }

    raw_all = load_jsonl(paths.sessions_log, last=None)
    rows_all = to_event_rows(raw_all)
    if not rows_all:
        return {
            "events": [],
            "summary": {
                "events": 0,
                "avg_reward": 0.0,
                "recent_avg_reward": 0.0,
                "global_count": 0,
                "context_count": 0,
            },
        }

    raw_recent = raw_all[-limit:]
    rows_recent = rows_all[-limit:]

    events: list[dict[str, Any]] = []
    for record, row in zip(raw_recent, rows_recent):
        context = record.get("context") or {"skill": "unknown", "goal": "unknown"}
        query = str(record.get("query") or "")
        timestamp = str(record.get("ts_utc") or "")
        candidates = record.get("candidates") or []
        chosen_title = next(
            (str(item.get("title")) for item in candidates if item.get("id") == row.chosen_id and item.get("title")),
            row.chosen_id,
        )

        events.append(
            {
                "query": query,
                "chosen_id": row.chosen_id,
                "chosen_title": chosen_title,
                "reward": row.reward,
                "decision_scope": row.decision_scope,
                "context": context,
                "timestamp": timestamp,
            }
        )

    global_count = 0
    context_count = 0
    rewards: list[float] = []
    for row in rows_all:
        if row.decision_scope == "global":
            global_count += 1
        elif row.decision_scope == "context":
            context_count += 1

        rewards.append(row.reward)

    return {
        "events": events,
        "summary": {
            "events": len(rows_all),
            "avg_reward": round(sum(rewards) / len(rewards), 3),
            "recent_avg_reward": round(sum(rewards[-10:]) / len(rewards[-10:]), 3),
            "global_count": global_count,
            "context_count": context_count,
        },
    }


class CoachHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "TTCoachHTTP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True, "pending": len(PENDING_BY_RUN_ID)})
            return
        if parsed.path == "/api/stats":
            self._send_json(recent_stats())
            return
        if parsed.path == "/api/history":
            self._send_json(history_payload())
            return
        if parsed.path == "/":
            self._send_json(
                {
                    "ok": True,
                    "message": "TT Coach API is running. Start the frontend dev server and open http://127.0.0.1:3000.",
                }
            )
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/recommend":
            self._handle_recommend()
            return
        if parsed.path == "/api/feedback":
            self._handle_feedback()
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("QUIET_HTTP") == "1":
            return
        super().log_message(format, *args)

    def _handle_recommend(self) -> None:
        payload = self._read_json()
        query = str(payload.get("query", "")).strip()
        skill = str(payload.get("skill", "intermediate")).strip().lower()
        goal = str(payload.get("goal", "backhand")).strip().lower()
        top_k = int(payload.get("top_k", 5))

        if not query:
            self._send_json({"error": "query is required"}, status=HTTPStatus.BAD_REQUEST)
            return

        ctx = UserContext(skill=skill, goal=goal)
        try:
            decision = recommend_drill(query=query, ctx=ctx, top_k=top_k, mode="hybrid")
        except Exception as exc:
            self._send_json(
                {
                    "error": "Recommendation failed. The search model may not be available locally yet.",
                    "detail": str(exc),
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return

        with PENDING_LOCK:
            PENDING_BY_RUN_ID[decision.run_id] = decision

        chosen = next((c for c in decision.candidates if c["id"] == decision.chosen_id), None)
        self._send_json(
            {
                "run_id": decision.run_id,
                "query": decision.query,
                "context": asdict(decision.context),
                "decision_scope": decision.decision_scope,
                "context_total_pulls": decision.context_total_pulls,
                "prior_source": decision.prior_source,
                "chosen_id": decision.chosen_id,
                "chosen": chosen,
                "candidates": decision.candidates,
            }
        )

    def _handle_feedback(self) -> None:
        payload = self._read_json()
        run_id = str(payload.get("run_id", "")).strip()
        rating = payload.get("rating")

        if not run_id:
            self._send_json({"error": "run_id is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        if rating is None:
            self._send_json({"error": "rating is required"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            rating_int = int(rating)
            reward = reward_from_rating(rating_int)
        except (TypeError, ValueError):
            self._send_json({"error": "rating must be an integer between 1 and 5"}, status=HTTPStatus.BAD_REQUEST)
            return

        with PENDING_LOCK:
            decision = PENDING_BY_RUN_ID.pop(run_id, None)

        if decision is None:
            self._send_json({"error": "unknown or expired run_id"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            chosen_id, saved_reward = record_feedback(
                decision,
                reward=reward,
                feedback_source="explicit_web_rating",
                feedback_raw=str(rating_int),
            )
        except Exception as exc:
            self._send_json(
                {"error": "Feedback could not be recorded.", "detail": str(exc)},
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
            return
        self._send_json({"ok": True, "chosen_id": chosen_id, "reward": saved_reward, "stats": recent_stats()})

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    host = os.getenv("TT_COACH_HOST", "127.0.0.1")
    port = int(os.getenv("TT_COACH_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), CoachHTTPRequestHandler)
    print(f"TT Coach web UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
