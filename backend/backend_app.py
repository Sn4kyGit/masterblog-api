# backend_app.py
"""Blog backend with JSON file persistence.

- Stores posts in posts.json (atomic writes, lock-protected)
- CRUD endpoints:
    * GET    /api/posts
    * GET    /api/posts/<id>
    * POST   /api/posts
    * PUT    /api/posts/<id>
    * DELETE /api/posts/<id>
- Post fields: id (int), title (str), content (str),
  author (str), date (YYYY-MM-DD, limited range)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from flask import Flask, jsonify, request, make_response

try:
    # Optional: enable CORS during dev if frontend runs on another port
    from flask_cors import CORS
except ImportError:  # pragma: no cover
    CORS = None  # type: ignore

import json
import os
import tempfile
import threading

app = Flask(__name__)

if CORS:
    CORS(app)  # enable CORS for all routes

# ----------------------- File persistence -----------------------

_STORAGE_FILE = os.path.join(os.path.dirname(__file__), "posts.json")
_LOCK = threading.Lock()

# Realistischer Datumsbereich
MIN_DATE = datetime(1900, 1, 1)
MAX_DATE = datetime(2100, 12, 31)


def _atomic_write(path: str, data: str) -> None:
    """Atomically write data to disk to avoid partial writes."""
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
    """Load posts list from JSON; create file with seed if missing/invalid."""
    if not os.path.exists(_STORAGE_FILE):
        seed = [
            {
                "id": 1,
                "title": "First post",
                "content": "This is the first post.",
                "author": "System",
                "date": "2023-01-01",
            },
            {
                "id": 2,
                "title": "Second post",
                "content": "This is the second post.",
                "author": "System",
                "date": "2023-01-02",
            },
        ]
        _save_posts(seed)
        return seed

    try:
        with _LOCK, open(_STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable file -> fall back to empty list
        return []


def _save_posts(posts: List[Dict[str, Any]]) -> None:
    """Persist full posts list to disk (thread-safe, atomic)."""
    with _LOCK:
        payload = json.dumps(posts, ensure_ascii=False, indent=2)
        _atomic_write(_STORAGE_FILE, payload)


def _next_id(posts: List[Dict[str, Any]]) -> int:
    """Generate next available ID for a post list."""
    return max((int(p.get("id", 0)) for p in posts), default=0) + 1


# ----------------------- Helpers & validation -----------------------

def _as_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _parse_date_str(date_str: str) -> Optional[datetime]:
    """Validate 'YYYY-MM-DD' within MIN_DATE..MAX_DATE."""
    if not date_str:
        return None
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    if not (MIN_DATE <= d <= MAX_DATE):
        return None
    return d


def _serialize(p: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure consistent API shape."""
    return {
        "id": int(p["id"]),
        "title": p.get("title", ""),
        "content": p.get("content", ""),
        "author": p.get("author", ""),
        "date": p.get("date", ""),
    }


# ----------------------------- Endpoints -----------------------------

@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def list_posts():
    """Return all posts (as stored)."""
    posts = _load_posts()
    return jsonify([_serialize(p) for p in posts])


@app.get("/api/posts/<int:post_id>")
def get_post(post_id: int):
    """Return a single post by ID."""
    posts = _load_posts()
    post = next((p for p in posts if int(p.get("id")) == post_id), None)
    if not post:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404
    return jsonify(_serialize(post))


@app.post("/api/posts")
def create_post():
    """Create a new post. Body JSON must include: title, content, author, date."""
    data = request.get_json(silent=True) or {}
    title = _as_str(data.get("title"))
    content = _as_str(data.get("content"))
    author = _as_str(data.get("author"))
    date_str = _as_str(data.get("date"))

    missing_or_invalid = []
    if not title:
        missing_or_invalid.append("title")
    if not content:
        missing_or_invalid.append("content")
    if not author:
        missing_or_invalid.append("author")
    if _parse_date_str(date_str) is None:
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
    }
    posts.append(post)
    _save_posts(posts)

    resp = jsonify(_serialize(post))
    return make_response(resp, 201)


@app.put("/api/posts/<int:post_id>")
def update_post(post_id: int):
    """Update an existing post. Any of title/content/author/date may be provided."""
    posts = _load_posts()
    target = next((p for p in posts if int(p.get("id")) == post_id), None)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        new_title = _as_str(data["title"])
        if new_title:
            target["title"] = new_title
    if "content" in data:
        new_content = _as_str(data["content"])
        if new_content:
            target["content"] = new_content
    if "author" in data:
        new_author = _as_str(data["author"])
        if new_author:
            target["author"] = new_author
    if "date" in data:
        new_date = _as_str(data["date"])
        if new_date:
            if _parse_date_str(new_date) is None:
                return jsonify(
                    {"message": "Invalid date (YYYY-MM-DD within 1900-01-01..2100-12-31)."}
                ), 400
            target["date"] = new_date

    _save_posts(posts)
    return jsonify(_serialize(target))


@app.delete("/api/posts/<int:post_id>")
def delete_post(post_id: int):
    """Delete a post by ID."""
    posts = _load_posts()
    remaining = [p for p in posts if int(p.get("id")) != post_id]
    if len(remaining) == len(posts):
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    _save_posts(remaining)
    return jsonify({"message": f"Post with id {post_id} has been deleted successfully."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)