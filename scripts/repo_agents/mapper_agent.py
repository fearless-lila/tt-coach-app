import json
from collections import defaultdict
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
}


def list_repo_files(root: Path) -> list[Path]:
    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        files.append(path)

    return sorted(files)


def group_files_by_area(files: list[Path], root: Path) -> dict[str, list[str]]:
    groups = defaultdict(list)

    for path in files:
        relative = path.relative_to(root)
        parts = relative.parts

        if len(parts) == 1:
            group_name = "(root files)"
        else:
            group_name = parts[0]

        groups[group_name].append(str(relative))

    return dict(sorted(groups.items()))


def detect_entrypoints(files: list[Path], root: Path) -> list[Path]:
    entrypoints = []

    for path in files:
        relative = path.relative_to(root)
        relative_str = str(relative)

        if relative_str == "README.md":
            entrypoints.append(path)
        elif relative_str.endswith("web.py"):
            entrypoints.append(path)
        elif relative_str.endswith("main.py"):
            entrypoints.append(path)
        elif relative_str.endswith("app.js"):
            entrypoints.append(path)
        elif relative_str.endswith("index.html"):
            entrypoints.append(path)
        elif relative_str.endswith("package.json"):
            entrypoints.append(path)
        elif relative_str.endswith("vite.config.ts"):
            entrypoints.append(path)

    return sorted(entrypoints)


def explain_entrypoint(path: Path, root: Path) -> str:
    relative = str(path.relative_to(root))

    if relative == "README.md":
        return "project overview and architecture notes"
    if relative == "tt_coach_app/web.py":
        return "likely backend API entrypoint"
    if relative == "tt_coach_app/main.py":
        return "likely core recommendation logic"
    if relative == "frontend/app.js":
        return "likely frontend UI logic entrypoint"
    if relative == "frontend/index.html":
        return "frontend page shell"
    if relative == "frontend/package.json":
        return "frontend tool and script configuration"
    if relative == "frontend/vite.config.ts":
        return "frontend dev server and build config"
    if relative == "app/main.py":
        return "separate app entry file or older backend entrypoint"

    return "important repo file"


def build_repo_map(root: Path) -> dict:
    files = list_repo_files(root)
    groups = group_files_by_area(files, root)
    entrypoints = detect_entrypoints(files, root)

    return {
        "root": str(root),
        "file_count": len(files),
        "areas": groups,
        "entrypoints": [
            {
                "path": str(path.relative_to(root)),
                "explanation": explain_entrypoint(path, root),
            }
            for path in entrypoints
        ],
    }


def save_repo_map(root: Path, repo_map: dict) -> Path:
    output_path = root / ".repo_map.json"
    output_path.write_text(
        json.dumps(repo_map, indent=2),
        encoding="utf-8",
    )
    return output_path


def load_repo_map(root: Path) -> dict | None:
    map_path = root / ".repo_map.json"

    if not map_path.exists():
        return None

    return json.loads(map_path.read_text(encoding="utf-8"))


def get_or_create_repo_map(root: Path) -> dict:
    repo_map = load_repo_map(root)

    if repo_map is not None:
        return repo_map

    repo_map = build_repo_map(root)
    save_repo_map(root, repo_map)
    return repo_map
