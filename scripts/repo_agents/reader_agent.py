from pathlib import Path


def read_file_if_exists(path: Path) -> str:
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8")


def answer_backend_entrypoint(root: Path) -> str:
    backend_file = root / "tt_coach_app" / "web.py"
    content = read_file_if_exists(backend_file)

    if not content:
        return "I could not find tt_coach_app/web.py"

    signals = []

    if "BaseHTTPRequestHandler" in content:
        signals.append("uses BaseHTTPRequestHandler")
    if "do_GET" in content:
        signals.append("defines do_GET")
    if "do_POST" in content:
        signals.append("defines do_POST")
    if "/api/recommend" in content:
        signals.append("handles /api/recommend")

    signal_text = ", ".join(signals) if signals else "it contains backend-related code"

    return (
        "Backend entrypoint: tt_coach_app/web.py\n"
        f"Reason: {signal_text}."
    )


def answer_frontend_entrypoint(root: Path) -> str:
    frontend_file = root / "frontend" / "app.js"
    html_file = root / "frontend" / "index.html"

    js_content = read_file_if_exists(frontend_file)
    html_content = read_file_if_exists(html_file)

    if not js_content:
        return "I could not find frontend/app.js"

    signals = []

    if "document.getElementById" in js_content:
        signals.append("uses document.getElementById")
    if "fetch('/api/recommend'" in js_content or 'fetch("/api/recommend"' in js_content:
        signals.append("calls /api/recommend")
    if "fetch('/api/feedback'" in js_content or 'fetch("/api/feedback"' in js_content:
        signals.append("calls /api/feedback")

    signal_text = ", ".join(signals) if signals else "it contains frontend-related logic"

    extra = ""
    if html_content:
        extra = "\nPage shell: frontend/index.html"

    return (
        "Frontend entrypoint: frontend/app.js\n"
        f"Reason: {signal_text}."
        f"{extra}"
    )


def answer_frontend_backend_flow(root: Path) -> str:
    frontend_file = root / "frontend" / "app.js"
    backend_file = root / "tt_coach_app" / "web.py"

    js_content = read_file_if_exists(frontend_file)
    backend_content = read_file_if_exists(backend_file)

    if not js_content or not backend_content:
        return "I could not inspect both frontend/app.js and tt_coach_app/web.py"

    frontend_calls = []
    backend_routes = []

    if "fetch('/api/recommend'" in js_content or 'fetch("/api/recommend"' in js_content:
        frontend_calls.append("/api/recommend")
    if "fetch('/api/feedback'" in js_content or 'fetch("/api/feedback"' in js_content:
        frontend_calls.append("/api/feedback")
    if "fetch('/api/history'" in js_content or 'fetch("/api/history"' in js_content:
        frontend_calls.append("/api/history")
    if "fetch('/api/stats'" in js_content or 'fetch("/api/stats"' in js_content:
        frontend_calls.append("/api/stats")

    for route in ["/api/recommend", "/api/feedback", "/api/history", "/api/stats"]:
        if route in backend_content:
            backend_routes.append(route)

    frontend_text = ", ".join(frontend_calls) if frontend_calls else "no API calls detected"
    backend_text = ", ".join(backend_routes) if backend_routes else "no matching backend routes detected"

    return (
        "Frontend talks to backend through HTTP API calls.\n"
        f"Frontend evidence: frontend/app.js calls {frontend_text}.\n"
        f"Backend evidence: tt_coach_app/web.py handles {backend_text}."
    )
