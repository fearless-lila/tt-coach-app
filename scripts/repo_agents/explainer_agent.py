from pathlib import Path

from repo_agents.context_builder import build_context
from repo_agents.llm_client import answer_with_ollama
from repo_agents.reader_agent import (
    answer_backend_entrypoint,
    answer_frontend_backend_flow,
    answer_frontend_entrypoint,
)


def answer_from_repo_map(question: str, repo_map: dict) -> str | None:
    q = question.lower()

    if "entrypoints" in q or "entry points" in q:
        lines = ["Known entrypoints:"]
        for item in repo_map["entrypoints"]:
            lines.append(f"- {item['path']}: {item['explanation']}")
        return "\n".join(lines)

    if "areas" in q or "structure" in q or "folders" in q:
        lines = ["Top-level areas:"]
        for area_name, files in repo_map["areas"].items():
            lines.append(f"- {area_name}: {len(files)} files")
        return "\n".join(lines)

    return None


def answer_question(question: str, root: Path, repo_map: dict | None) -> str:
    q = question.lower()

    if "frontend" in q and "backend" in q:
        return answer_frontend_backend_flow(root)

    if "backend" in q and "entry" in q:
        return answer_backend_entrypoint(root)

    if "frontend" in q and "entry" in q:
        return answer_frontend_entrypoint(root)

    if repo_map is not None:
        repo_map_answer = answer_from_repo_map(question, repo_map)
        if repo_map_answer is not None:
            return repo_map_answer

    if "recommend" in q or "bandit" in q:
        return (
            "Core recommendation logic is likely in tt_coach_app/main.py\n"
            "Reason: that file is the best candidate for drill selection and learning logic."
        )

    if "history" in q or "session" in q:
        return (
            "Session-related files:\n"
            "- tt_coach_app/session_log.py\n"
            "- tt_coach_app/analyze_sessions.py\n"
            "- state/sessions.jsonl"
        )

    if "overview" in q or "architecture" in q or "repo" in q:
        context = build_context(question, root, repo_map)
        return answer_with_ollama(question, context)

    context = build_context(question, root, repo_map)
    if not context:
        return (
            "I do not know that yet.\n"
            "Try asking about backend entrypoint, frontend entrypoint, entrypoints, structure, or session history."
        )

    return answer_with_ollama(question, context)
