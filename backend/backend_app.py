# backend_app.py
"""Blog backend with CORS, file persistence, search, sorting and Swagger UI.

Endpoints:
- GET    /api/health
- GET    /api/posts                      (?sort=title|content&direction=asc|desc)
- GET    /api/posts/search?title=&content=
- POST   /api/posts
- PUT    /api/posts/<id>
- DELETE /api/posts/<id>

Docs:
- Swagger UI at /api/docs (serves backend/static/masterblog.json)
"""

from __future__ import annotations

from typing import Any, Dict, List

from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint  # <-- Swagger UI
import json
import os
import tempfile
import threading

app = Flask(__name__, static_folder="static")
CORS(app)  # enable CORS for all routes

# ----------------------- Swagger UI config -----------------------
# (1) UI Endpoint
SWAGGER_URL = "/api/docs"
# (2) JSON definition served from Flask's /static directory
API_URL = "/static/masterblog.json"
# (3) App name in the UI header
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Masterblog API"},
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

# ----------------------- file-backed storage ---------------------
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
    """Load list of posts from JSON file (seed if missing)."""
    if not os.path.exists(_STORAGE_FILE):
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


# ----------------------------- routes ----------------------------
@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def get_posts():
    """Return all posts with optional sorting.

    Query params (optional):
      - sort:      'title' | 'content'
      - direction: 'asc' | 'desc'   (default 'asc' when sort is provided)
    """
    posts = _load_posts()

    sort_field = request.args.get("sort")
    direction = request.args.get("direction")

    if sort_field is None and direction is None:
        return jsonify(
            [{"id": int(p["id"]), "title": p["title"], "content": p["content"]} for p in posts]
        )

    allowed_fields = {"title", "content"}
    if sort_field not in allowed_fields:
        return jsonify({"message": "Invalid 'sort' parameter.", "allowed": sorted(allowed_fields)}), 400

    if direction is None:
        direction = "asc"
    allowed_dirs = {"asc", "desc"}
    if direction not in allowed_dirs:
        return jsonify({"message": "Invalid 'direction' parameter.", "allowed": sorted(allowed_dirs)}), 400

    reverse = direction == "desc"
    sorted_posts = sorted(posts, key=lambda p: str(p.get(sort_field, "")).lower(), reverse=reverse)

    return jsonify(
        [{"id": int(p["id"]), "title": p["title"], "content": p["content"]} for p in sorted_posts]
    )


@app.get("/api/posts/search")
def search_posts():
    """Search posts by title and/or content (case-insensitive contains)."""
    title_q = (request.args.get("title") or "").strip().lower()
    content_q = (request.args.get("content") or "").strip().lower()

    posts = _load_posts()

    def matches(p: Dict[str, Any]) -> bool:
        t = str(p.get("title", "")).lower()
        c = str(p.get("content", "")).lower()
        if title_q and title_q not in t:
            return False
        if content_q and content_q not in c:
            return False
        return True

    filtered = [p for p in posts if matches(p)]
    return jsonify(
        [{"id": int(p["id"]), "title": p["title"], "content": p["content"]} for p in filtered]
    )


@app.post("/api/posts")
def create_post():
    """Create a new post from JSON body: {title, content} -> 201 + post JSON."""
    data = request.get_json(silent=True) or {}
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
        return jsonify({"message": "Missing or empty required field(s).", "missing": missing}), 400

    posts = _load_posts()
    post = {"id": _next_id(posts), "title": title, "content": content}
    posts.append(post)
    _save_posts(posts)

    resp = jsonify({"id": int(post["id"]), "title": post["title"], "content": post["content"]})
    return make_response(resp, 201)


@app.put("/api/posts/<int:post_id>")
def update_post(post_id: int):
    """Update an existing post (title/content optional)."""
    posts = _load_posts()
    target = next((p for p in posts if int(p.get("id")) == post_id), None)
    if not target:
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        new_title = "" if data["title"] is None else str(data["title"]).strip()
        if new_title:
            target["title"] = new_title

    if "content" in data:
        new_content = "" if data["content"] is None else str(data["content"]).strip()
        if new_content:
            target["content"] = new_content

    _save_posts(posts)
    return jsonify({"id": int(target["id"]), "title": target["title"], "content": target["content"]}), 200


@app.delete("/api/posts/<int:post_id>")
def delete_post(post_id: int):
    """Delete a post by its ID."""
    posts = _load_posts()
    remaining = [p for p in posts if int(p.get("id")) != post_id]
    if len(remaining) == len(posts):
        return jsonify({"message": f"Post with id {post_id} was not found."}), 404

    _save_posts(remaining)
    return jsonify({"message": f"Post with id {post_id} has been deleted successfully."}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)