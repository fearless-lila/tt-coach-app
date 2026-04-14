from __future__ import annotations

import os
import subprocess


SYSTEM_PROMPT = (
    "You explain codebases for developers. "
    "Use only the provided repository context. "
    "When you make a claim, mention the relevant file path. "
    "If the context is insufficient, say so clearly instead of guessing."
)


def configured_model() -> str | None:
    return os.getenv("REPO_AGENT_OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL") or "llama3.2"


def answer_with_ollama(question: str, context: str) -> str:
    model = configured_model()
    if not model:
        return (
            "AI mode is not configured.\n"
            "Set REPO_AGENT_OLLAMA_MODEL or OLLAMA_MODEL to an installed Ollama model."
        )

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Question:\n{question}\n\n"
        f"Repository context:\n{context}\n"
    )

    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "Ollama is not installed or not on PATH."
    except Exception as exc:
        return f"Ollama call failed: {exc}"

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        return f"Ollama call failed: {detail}"

    answer = result.stdout.strip()
    if not answer:
        return "Ollama returned an empty response."

    return answer
