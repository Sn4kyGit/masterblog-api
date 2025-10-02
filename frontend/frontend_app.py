"""MasterBlog Frontend (Flask).

Render-Logik
------------
- Listet Posts (mit Suche/Sortierung) und bietet ein Create-Form
- Edit/Save/Delete via Backend-API
- Templates: templates/index.html, templates/edit.html
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests
from flask import Flask, redirect, render_template, request, url_for

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "4999"))
BACKEND_BASE = os.getenv("BACKEND_BASE", "http://localhost:5002")
MIN_DATE = "1900-01-01"
MAX_DATE = "2100-12-31"

HTTP_TIMEOUT = 5  # Sekunden

# Eine Session spart Verbindungen & setzt Defaults zentral
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = Flask(__name__)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _explain_error(resp: requests.Response) -> str:
    """Gibt eine kompakte Fehlerbeschreibung für API-Antworten zurück."""
    try:
        data: Dict[str, Any] = resp.json()  # type: ignore[assignment]
        message = data.get("message") or ""
    except Exception:
        message = (resp.text or "").strip()
    reason = resp.reason or "Error"
    return f"{resp.status_code} {reason}: {message}"


def _get_json(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET-Helper mit Fehlertext (wirft keine Exceptions)."""
    url = f"{BACKEND_BASE}{path}"
    try:
        resp = SESSION.get(url, params=params, timeout=HTTP_TIMEOUT)
        ok = 200 <= resp.status_code < 300
        return {"ok": ok, "data": resp.json() if ok else None, "error": None if ok else _explain_error(resp)}  # noqa: E501
    except Exception as exc:  # Netzwerk etc.
        return {"ok": False, "data": None, "error": f"Backend not reachable: {exc}"}


def _post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}{path}"
    try:
        resp = SESSION.post(url, json=payload, timeout=HTTP_TIMEOUT)
        ok = 200 <= resp.status_code < 300
        return {"ok": ok, "data": resp.json() if ok else None, "error": None if ok else _explain_error(resp)}  # noqa: E501
    except Exception as exc:
        return {"ok": False, "data": None, "error": f"Backend not reachable: {exc}"}


def _put_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}{path}"
    try:
        resp = SESSION.put(url, json=payload, timeout=HTTP_TIMEOUT)
        ok = 200 <= resp.status_code < 300
        return {"ok": ok, "data": resp.json() if ok else None, "error": None if ok else _explain_error(resp)}  # noqa: E501
    except Exception as exc:
        return {"ok": False, "data": None, "error": f"Backend not reachable: {exc}"}


def _delete(path: str) -> Dict[str, Any]:
    url = f"{BACKEND_BASE}{path}"
    try:
        resp = SESSION.delete(url, timeout=HTTP_TIMEOUT)
        ok = 200 <= resp.status_code < 300
        return {"ok": ok, "data": None, "error": None if ok else _explain_error(resp)}
    except Exception as exc:
        return {"ok": False, "data": None, "error": f"Backend not reachable: {exc}"}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.route("/", methods=["GET", "POST"])
def home():
    """Startseite: Posts anzeigen, Suche/Sortierung, Create-Form behandeln."""
    error: Optional[str] = None

    # Create (POST)
    if request.method == "POST":
        payload = {
            "title": (request.form.get("title") or "").strip(),
            "content": (request.form.get("content") or "").strip(),
            "author": (request.form.get("author") or "").strip(),
            "date": (request.form.get("date") or "").strip(),
        }
        result = _post_json("/api/posts", payload)
        if not result["ok"] and result["error"]:
            error = str(result["error"])

    # GET-Parameter einlesen (Suche & Sortierung)
    q_title = (request.args.get("title") or "").strip()
    q_content = (request.args.get("content") or "").strip()
    sort_field = (request.args.get("sort") or "").strip() or None  # "title"|"content"|None
    direction = (request.args.get("direction") or "").strip() or None  # "asc"|"desc"|None

    allowed_fields = {"title", "content"}
    allowed_dirs = {"asc", "desc"}

    posts: list[dict[str, Any]] = []
    # Entscheiden, ob Search-Endpoint oder List-Endpoint genutzt wird
    if q_title or q_content:
        params: Dict[str, Any] = {}
        if q_title:
            params["title"] = q_title
        if q_content:
            params["content"] = q_content
        result = _get_json("/api/posts/search", params=params)
        if result["ok"]:
            posts = list(result["data"] or [])
        elif not error and result["error"]:
            error = str(result["error"])

        # Sortierung clientseitig auf Suchergebnis anwenden (optional)
        if sort_field in allowed_fields and direction in allowed_dirs:
            posts = sorted(
                posts,
                key=lambda p: (p.get(sort_field) or "").lower(),
                reverse=(direction == "desc"),
            )
    else:
        params = {}
        if sort_field in allowed_fields:
            params["sort"] = sort_field
            if direction in allowed_dirs:
                params["direction"] = direction
        result = _get_json("/api/posts", params=params)
        if result["ok"]:
            posts = list(result["data"] or [])
        elif not error and result["error"]:
            error = str(result["error"])

    return render_template(
        "index.html",
        posts=posts,
        error=error,
        MIN_DATE=MIN_DATE,
        MAX_DATE=MAX_DATE,
        q_title=q_title,
        q_content=q_content,
        sort_field=sort_field or "",
        direction=direction or "asc",
    )


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit(post_id: int):
    """Post bearbeiten."""
    # Vorab aktuellen Post laden
    current = _get_json(f"/api/posts/{post_id}")
    if not current["ok"] or not current["data"]:
        return (
            "<p style='font-family: system-ui'>Post not found. "
            "<a href='/'>Back</a></p>",
            404,
        )
    post: Dict[str, Any] = current["data"]

    # Speichern
    if request.method == "POST":
        payload = {
            "title": (request.form.get("title") or "").strip(),
            "content": (request.form.get("content") or "").strip(),
            "author": (request.form.get("author") or "").strip(),
            "date": (request.form.get("date") or "").strip(),
        }
        result = _put_json(f"/api/posts/{post_id}", payload)
        if result["ok"]:
            return redirect(url_for("home"))

        error_msg = result["error"] or "Unknown error"
        return render_template(
            "edit.html",
            post=post,
            error=error_msg,
            MIN_DATE=MIN_DATE,
            MAX_DATE=MAX_DATE,
        )

    # GET: Formular zeigen
    return render_template(
        "edit.html",
        post=post,
        error=None,
        MIN_DATE=MIN_DATE,
        MAX_DATE=MAX_DATE,
    )


@app.route("/delete/<int:post_id>", methods=["POST"])
def delete(post_id: int):
    """Post löschen und zurück zur Liste."""
    _delete(f"/api/posts/{post_id}")
    return redirect(url_for("home"))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FRONTEND_PORT, debug=True)