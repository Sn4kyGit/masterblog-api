# backend_app.py
"""Blog backend with CORS, GET/POST /api/posts and file persistence."""

from __future__ import annotations

from typing import Any, Dict, List

from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
import json
import os
import tempfile
import threading

app = Flask(__name__)
CORS(app)  # enable CORS for all routes

# ----------------------- file-backed storage -----------------------
_STORAGE_FILE = os.path.join(os.path.dirname(__file__), "posts.json")
_LOCK = threading.Lock()


def _atomic_write(path: str, data: str) -> None:
    """Write data atomically to avoid partial writes."""
    dir_ = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".__tmp__", dir=dir_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(data)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _load_posts() -> List[Dict[str, Any]]:
    if not os.path.exists(_STORAGE_FILE):
        # seed with your initial sample, like in your snippet
        seed = [
            {"id": 1, "title": "First post", "content": "This is the first post."},
            {"id": 2, "title": "Second post", "content": "This is the second post."},
        ]
        _save_posts(seed)
        return seed
    try:
        with _LOCK, open(_STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _save_posts(posts: List[Dict[str, Any]]) -> None:
    with _LOCK:
        payload = json.dumps(posts, ensure_ascii=False, indent=2)
        _atomic_write(_STORAGE_FILE, payload)


def _next_id(posts: List[Dict[str, Any]]) -> int:
    return max((int(p.get("id", 0)) for p in posts), default=0) + 1


# ----------------------------- routes ------------------------------
@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def get_posts():
    """Return all posts (id/title/content)."""
    posts = _load_posts()
    # ensure id is int for the frontend
    return jsonify(
        [{"id": int(p["id"]), "title": p["title"], "content": p["content"]} for p in posts]
    )


@app.post("/api/posts")
def create_post():
    """Create a new post from JSON body: {title, content} -> 201 + post JSON."""
    data = request.get_json(silent=True) or {}

    # robust extraction & trimming
    raw_title = data.get("title")
    raw_content = data.get("content")
    title = (str(raw_title).strip()) if isinstance(raw_title, (str, int, float)) else ""
    content = (str(raw_content).strip()) if isinstance(raw_content, (str, int, float)) else ""

    missing = []
    if not title:
        missing.append("title")
    if not content:
        missing.append("content")

    if missing:
        return (
            jsonify(
                {
                    "message": "Missing or empty required field(s).",
                    "missing": missing,
                }
            ),
            400,
        )

    posts = _load_posts()
    post = {"id": _next_id(posts), "title": title, "content": content}
    posts.append(post)
    _save_posts(posts)

    resp = jsonify({"id": int(post["id"]), "title": post["title"], "content": post["content"]})
    return make_response(resp, 201)


if __name__ == "__main__":
    # same port as your example
    app.run(host="0.0.0.0", port=5002, debug=True)