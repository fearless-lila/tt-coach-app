from __future__ import annotations

from pathlib import Path


MAX_CHARS_PER_FILE = 4000


def read_file_snippet(path: Path, max_chars: int = MAX_CHARS_PER_FILE) -> str:
    if not path.exists() or not path.is_file():
        return ""

    content = path.read_text(encoding="utf-8")
    if len(content) <= max_chars:
        return content

    return content[:max_chars] + "\n... [truncated]"


def candidate_paths_for_question(question: str, root: Path) -> list[Path]:
    q = question.lower()
    paths: list[Path] = []

    def add(relative_path: str) -> None:
        path = root / relative_path
        if path.exists() and path not in paths:
            paths.append(path)

    add("README.md")

    if "frontend" in q:
        add("frontend/index.html")
        add("frontend/app.js")
        add("frontend/styles.css")
        add("frontend/vite.config.ts")

    if "backend" in q or "api" in q:
        add("tt_coach_app/web.py")

    if "recommend" in q or "bandit" in q or "drill" in q:
        add("tt_coach_app/main.py")

    if "history" in q or "session" in q or "log" in q:
        add("tt_coach_app/session_log.py")
        add("tt_coach_app/analyze_sessions.py")
        add("tt_coach_app/state_paths.py")

    if "structure" in q or "repo" in q or "architecture" in q or "overview" in q:
        add("tt_coach_app/web.py")
        add("tt_coach_app/main.py")
        add("frontend/app.js")
        add("scripts/repo_agent.py")

    if len(paths) == 1:
        add("tt_coach_app/web.py")
        add("tt_coach_app/main.py")
        add("frontend/app.js")

    return paths


def build_context(question: str, root: Path, repo_map: dict | None) -> str:
    sections: list[str] = []

    if repo_map is not None:
        lines = ["Repository map:"]
        for item in repo_map.get("entrypoints", []):
            lines.append(f"- {item['path']}: {item['explanation']}")
        areas = repo_map.get("areas", {})
        if areas:
            lines.append("Top-level areas:")
            for area_name, files in areas.items():
                lines.append(f"- {area_name}: {len(files)} files")
        sections.append("\n".join(lines))

    for path in candidate_paths_for_question(question, root):
        relative = path.relative_to(root)
        snippet = read_file_snippet(path)
        if snippet:
            sections.append(f"File: {relative}\n```python\n{snippet}\n```")

    return "\n\n".join(sections).strip()
