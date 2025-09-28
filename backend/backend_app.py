# backend_app.py
"""Blog backend with JSON file persistence, likes and comments.

- Stores posts in posts.json (atomic writes, lock-protected)
- Post fields: id, title, content, author, date (YYYY-MM-DD),
               likes (int), comments (list of {id, author, text, date})
- Endpoints:
    GET    /api/health
    GET    /api/posts
    GET    /api/posts/<id>
    POST   /api/posts
    PUT    /api/posts/<id>
    DELETE /api/posts/<id>
    POST   /api/posts/<id>/like
    GET    /api/posts/<id>/comments
    POST   /api/posts/<id>/comments
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from flask import Flask, jsonify, request, make_response

try:
    from flask_cors import CORS  # optional, for dev on different ports
except ImportError:  # pragma: no cover
    CORS = None  # type: ignore

import json
import os
import tempfile
import threading

app = Flask(__name__)
if CORS:
    CORS(app)

# ----------------------- File persistence -----------------------

_STORAGE_FILE = os.path.join(os.path.dirname(__file__), "posts.json")
_LOCK = threading.Lock()

# Realistic date range
MIN_DATE = datetime(1900, 1, 1)
MAX_DATE = datetime(2100, 12, 31)


def _atomic_write(path: str, data: str) -> None:
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
        with _LOCK, open(_STORAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_posts(posts: List[Dict[str, Any]]) -> None:
    with _LOCK:
        payload = json.dumps(posts, ensure_ascii=False, indent=2)
        _atomic_write(_STORAGE_FILE, payload)


def _next_id(posts: List[Dict[str, Any]]) -> int:
    return max((int(p.get("id", 0)) for p in posts), default=0) + 1


# ----------------------- Helpers & validation -----------------------

def _as_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _parse_date_str(date_str: str) -> Optional[datetime]:
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
    return {
        "id": int(p["id"]),
        "title": p.get("title", ""),
        "content": p.get("content", ""),
        "author": p.get("author", ""),
        "date": p.get("date", ""),
        "likes": int(p.get("likes", 0) or 0),
        "comments": list(p.get("comments", [])),
    }


def _find_post(posts: List[Dict[str, Any]], post_id: int) -> Optional[Dict[str, Any]]:
    return next((p for p in posts if int(p.get("id")) == post_id), None)


# ----------------------------- Endpoints -----------------------------

@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def list_posts():
    posts = _load_posts()
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
        return jsonify({
            "message": "Missing or invalid required field(s).",
            "missing": missing_or_invalid,
        }), 400

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
    return make_response(jsonify(_serialize(post)), 201)


@app.put("/api/posts/<int:post_id>")
def update_post(post_id: int):
    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        v = _as_str(data["title"])
        if v:
            target["title"] = v
    if "content" in data:
        v = _as_str(data["content"])
        if v:
            target["content"] = v
    if "author" in data:
        v = _as_str(data["author"])
        if v:
            target["author"] = v
    if "date" in data:
        v = _as_str(data["date"])
        if v:
            if _parse_date_str(v) is None:
                return jsonify({
                    "message": "Invalid date (YYYY-MM-DD within 1900-01-01..2100-12-31)."
                }), 400
            target["date"] = v

    _save_posts(posts)
    return jsonify(_serialize(target))


@app.delete("/api/posts/<int:post_id>")
def delete_post(post_id: int):
    posts = _load_posts()
    remaining = [p for p in posts if int(p.get("id")) != post_id]
    if len(remaining) == len(posts):
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    _save_posts(remaining)
    return jsonify({"message": f"Post with id {post_id} has been deleted successfully."})


# ----------------------------- Likes --------------------------------

@app.post("/api/posts/<int:post_id>/like")
def like_post(post_id: int):
    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404
    target["likes"] = int(target.get("likes", 0) or 0) + 1
    _save_posts(posts)
    return jsonify({"id": post_id, "likes": int(target["likes"])}), 200


# ---------------------------- Comments ------------------------------

@app.get("/api/posts/<int:post_id>/comments")
def list_comments(post_id: int):
    posts = _load_posts()
    target = _find_post(posts, post_id)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404
    return jsonify(list(target.get("comments", [])))


@app.post("/api/posts/<int:post_id>/comments")
def add_comment(post_id: int):
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
    new_comment = {
        "id": (max((int(c.get("id", 0)) for c in comments), default=0) + 1),
        "author": author,
        "text": text,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }
    comments.append(new_comment)
    target["comments"] = comments
    _save_posts(posts)

    return make_response(jsonify(new_comment), 201)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)