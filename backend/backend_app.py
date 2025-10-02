"""MasterBlog API (Flask + JSON Persistence).

Features
--------
- CRUD für Posts
- Likes und Comments
- Suche (/api/posts/search) via title/content (case-insensitive)
- Sortierung in /api/posts via ?sort=title|content&direction=asc|desc
- Swagger UI unter /api/docs (liefert /static/masterblog.json)
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, make_response, request
from werkzeug.exceptions import HTTPException

try:
    # Optional: CORS in Dev zulassen (Frontend-Port)
    from flask_cors import CORS
except Exception:  # pragma: no cover
    CORS = None  # type: ignore

# Swagger UI (Dokumentation verlinkt auf /static/masterblog.json)
from flask_swagger_ui import get_swaggerui_blueprint

# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #

APP_NAME = "MasterBlog API"
DEFAULT_PORT = int(os.getenv("BACKEND_PORT", "5002"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_FILE = os.path.join(BASE_DIR, "posts.json")

MAX_REQUEST_BYTES = 256 * 1024  # 256 KB
LOCK = threading.Lock()

DATE_MIN = datetime(1900, 1, 1)
DATE_MAX = datetime(2100, 12, 31)

# --------------------------------------------------------------------------- #
# App-Setup
# --------------------------------------------------------------------------- #

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

if CORS:
    # In Produktion auf konkrete Origins einschränken.
    CORS(app)

SWAGGER_URL = "/api/docs"
API_URL = "/static/masterblog.json"
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": APP_NAME},
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

# --------------------------------------------------------------------------- #
# Storage-Helfer
# --------------------------------------------------------------------------- #


def _atomic_write(path: str, data: str) -> None:
    """Datei atomar schreiben, um Teil-Schreibungen zu vermeiden."""
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".__tmp__", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(data)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            # Best effort cleanup
            pass


def _load_posts() -> List[Dict[str, Any]]:
    """Posts aus JSON laden. Falls Datei fehlt, Seed-Daten erzeugen."""
    if not os.path.exists(STORAGE_FILE):
        seed = [
            {
                "id": 1,
                "title": "First post",
                "content": "This is the first post.",
                "author": "System",
                "date": "2023-01-01",
                "likes": 0,
                "comments": [],
            },
            {
                "id": 2,
                "title": "Second post",
                "content": "This is the second post.",
                "author": "System",
                "date": "2023-01-02",
                "likes": 0,
                "comments": [],
            },
        ]
        _save_posts(seed)
        return seed

    try:
        with open(STORAGE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # Korrupt oder lesefehlerhaft -> leere Liste
        return []


def _save_posts(posts: List[Dict[str, Any]]) -> None:
    """Posts atomar in JSON-Datei schreiben."""
    with LOCK:
        payload = json.dumps(posts, ensure_ascii=False, indent=2)
        _atomic_write(STORAGE_FILE, payload)


def _next_id(posts: List[Dict[str, Any]]) -> int:
    """Nächste ID ermitteln."""
    return max((int(p.get("id", 0)) for p in posts), default=0) + 1


# --------------------------------------------------------------------------- #
# Validierung & Serialisierung
# --------------------------------------------------------------------------- #


def _as_str(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parse_date(date_str: str) -> Optional[datetime]:
    """YYYY-MM-DD prüfen und auf gültigen Bereich validieren."""
    if not date_str:
        return None
    try:
        value = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    if not (DATE_MIN <= value <= DATE_MAX):
        return None
    return value


def _serialize(post: Dict[str, Any]) -> Dict[str, Any]:
    """API-Form für einen Post angleichen."""
    return {
        "id": int(post["id"]),
        "title": post.get("title", ""),
        "content": post.get("content", ""),
        "author": post.get("author", ""),
        "date": post.get("date", ""),
        "likes": int(post.get("likes", 0) or 0),
        "comments": list(post.get("comments", [])),
    }


def _find_post(
    posts: List[Dict[str, Any]], post_id: int
) -> Optional[Dict[str, Any]]:
    """Post nach ID finden."""
    return next((p for p in posts if int(p.get("id")) == post_id), None)


def _require_json():
    """Fehlermeldung liefern, wenn Content-Type nicht JSON ist."""
    if not request.is_json:
        return jsonify({"message": "Content-Type must be application/json"}), 415
    return None


# --------------------------------------------------------------------------- #
# Error Handling
# --------------------------------------------------------------------------- #


@app.errorhandler(HTTPException)
def _handle_http_error(exc: HTTPException):
    return jsonify({"message": exc.description or exc.name}), exc.code


@app.errorhandler(Exception)
def _handle_unexpected(_: Exception):
    # In Produktion sinnvoll loggen.
    return jsonify({"message": "Internal server error"}), 500


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def list_posts():
    """Posts auflisten, optional sortiert."""
    posts = _load_posts()

    sort_field = request.args.get("sort", type=str)
    direction = request.args.get("direction", type=str)

    if sort_field:
        allowed_fields = {"title", "content"}
        if sort_field not in allowed_fields:
            return (
                jsonify(
                    {
                        "message": (
                            "Invalid sort field. Use one of: title, content."
                        )
                    }
                ),
                400,
            )

        if direction is None:
            direction = "asc"

        if direction not in {"asc", "desc"}:
            return jsonify({"message": "Invalid direction. Use asc or desc."}), 400

        reverse = direction == "desc"
        posts = sorted(
            posts,
            key=lambda p: _as_str(p.get(sort_field)).lower(),
            reverse=reverse,
        )

    return jsonify([_serialize(p) for p in posts])


@app.get("/api/posts/<int:post_id>")
def get_post(post_id: int):
    posts = _load_posts()
    post = _find_post(posts, post_id)
    if not post:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404
    return jsonify(_serialize(post))


@app.post("/api/posts")
def create_post():
    err = _require_json()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    title = _as_str(data.get("title"))
    content = _as_str(data.get("content"))
    author = _as_str(data.get("author"))
    date_str = _as_str(data.get("date"))

    missing_or_invalid: List[str] = []
    if not title:
        missing_or_invalid.append("title")
    if not content:
        missing_or_invalid.append("content")
    if not author:
        missing_or_invalid.append("author")
    if _parse_date(date_str) is None:
        missing_or_invalid.append("date")

    if missing_or_invalid:
        return (
            jsonify(
                {
                    "message": "Missing or invalid required field(s).",
                    "missing": missing_or_invalid,
                }
            ),
            400,
        )

    posts = _load_posts()
    post = {
        "id": _next_id(posts),
        "title": title,
        "content": content,
        "author": author,
        "date": date_str,
        "likes": 0,
        "comments": [],
    }
    posts.append(post)
    _save_posts(posts)

    resp = jsonify(_serialize(post))
    out = make_response(resp, 201)
    out.headers["Location"] = f"/api/posts/{post['id']}"
    return out


@app.put("/api/posts/<int:post_id>")
def update_post(post_id: int):
    err = _require_json()
    if err:
        return err

    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        value = _as_str(data["title"])
        if value:
            target["title"] = value
    if "content" in data:
        value = _as_str(data["content"])
        if value:
            target["content"] = value
    if "author" in data:
        value = _as_str(data["author"])
        if value:
            target["author"] = value
    if "date" in data:
        value = _as_str(data["date"])
        if value:
            if _parse_date(value) is None:
                return (
                    jsonify(
                        {
                            "message": (
                                "Invalid date "
                                "(YYYY-MM-DD within 1900-01-01..2100-12-31)."
                            )
                        }
                    ),
                    400,
                )
            target["date"] = value

    _save_posts(posts)
    return jsonify(_serialize(target))


@app.delete("/api/posts/<int:post_id>")
def delete_post(post_id: int):
    posts = _load_posts()
    remaining = [p for p in posts if int(p.get("id")) != post_id]
    if len(remaining) == len(posts):
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    _save_posts(remaining)
    return jsonify(
        {"message": f"Post with id {post_id} has been deleted successfully."}
    )


@app.post("/api/posts/<int:post_id>/like")
def like_post(post_id: int):
    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    target["likes"] = int(target.get("likes", 0) or 0) + 1
    _save_posts(posts)
    return jsonify({"id": post_id, "likes": int(target["likes"])}), 200


@app.get("/api/posts/<int:post_id>/comments")
def list_comments(post_id: int):
    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404
    return jsonify(list(target.get("comments", [])))


@app.post("/api/posts/<int:post_id>/comments")
def add_comment(post_id: int):
    err = _require_json()
    if err:
        return err

    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    data = request.get_json(silent=True) or {}
    author = _as_str(data.get("author"))
    text = _as_str(data.get("text"))
    if not author or not text:
        return jsonify({"message": "author and text are required"}), 400

    comments: List[Dict[str, Any]] = list(target.get("comments", []))
    next_comment_id = max((int(c.get("id", 0)) for c in comments), default=0) + 1
    new_comment = {
        "id": next_comment_id,
        "author": author,
        "text": text,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    comments.append(new_comment)
    target["comments"] = comments
    _save_posts(posts)

    return make_response(jsonify(new_comment), 201)


@app.get("/api/posts/search")
def search_posts():
    """Suche nach title/content (case-insensitive)."""
    title_term = request.args.get("title", type=str)
    content_term = request.args.get("content", type=str)

    posts = _load_posts()

    def _match(entry: Dict[str, Any]) -> bool:
        title_ok = True
        content_ok = True
        if title_term:
            title_ok = title_term.lower() in _as_str(entry.get("title")).lower()
        if content_term:
            content_ok = content_term.lower() in _as_str(entry.get("content")).lower()
        return title_ok and content_ok

    filtered = [p for p in posts if _match(p)]
    return jsonify([_serialize(p) for p in filtered]), 200


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=DEFAULT_PORT, debug=True)