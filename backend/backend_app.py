# backend_app.py
"""Blog backend with CORS, file persistence, CRUD, search & sorting.
Now includes 'author' and 'date' (YYYY-MM-DD) on posts.

Endpoints:
- GET    /api/health
- GET    /api/posts                      (?sort=title|content|author|date&direction=asc|desc)
- GET    /api/posts/search               (?q=&title=&content=&author=&date=)
- POST   /api/posts
- PUT    /api/posts/<id>
- DELETE /api/posts/<id>
- Swagger UI at /api/docs (serves /static/masterblog.json)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from flask import Flask, jsonify, make_response, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
import json
import os
import tempfile
import threading

app = Flask(__name__, static_folder="static")
CORS(app)  # enable CORS for all routes

# ----------------------- Swagger UI config -----------------------
SWAGGER_URL = "/api/docs"           # (1) UI Endpoint
API_URL = "/static/masterblog.json" # (2) JSON in Flask's static/
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Masterblog API"},  # (3) UI Title
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
    except json.JSONDecodeError:
        return []


def _save_posts(posts: List[Dict[str, Any]]) -> None:
    with _LOCK:
        payload = json.dumps(posts, ensure_ascii=False, indent=2)
        _atomic_write(_STORAGE_FILE, payload)


def _next_id(posts: List[Dict[str, Any]]) -> int:
    return max((int(p.get("id", 0)) for p in posts), default=0) + 1


# ----------------------- validation helpers ----------------------
def _as_str(x: Any) -> str:
    return "" if x is None else str(x).strip()


def _parse_date_str(date_str: str) -> Optional[datetime]:
    """Return a datetime for 'YYYY-MM-DD' or None if invalid/empty."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


# ----------------------------- routes ----------------------------
@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/posts")
def get_posts():
    """Return all posts with optional sorting.

    Query params (optional):
      - sort:      'title' | 'content' | 'author' | 'date'
      - direction: 'asc' | 'desc'   (default 'asc' when sort provided)
    """
    posts = _load_posts()

    sort_field = request.args.get("sort")
    direction = request.args.get("direction")

    if sort_field is None and direction is None:
        return jsonify(
            [
                {
                    "id": int(p["id"]),
                    "title": p["title"],
                    "content": p["content"],
                    "author": p.get("author", ""),
                    "date": p.get("date", ""),
                }
                for p in posts
            ]
        )

    allowed_fields = {"title", "content", "author", "date"}
    if sort_field not in allowed_fields:
        return jsonify({"message": "Invalid 'sort' parameter.", "allowed": sorted(allowed_fields)}), 400

    if direction is None:
        direction = "asc"
    allowed_dirs = {"asc", "desc"}
    if direction not in allowed_dirs:
        return jsonify({"message": "Invalid 'direction' parameter.", "allowed": sorted(allowed_dirs)}), 400

    reverse = direction == "desc"

    if sort_field == "date":
        def key_func(p: Dict[str, Any]):
            d = _parse_date_str(_as_str(p.get("date", "")))
            # Fallback: None -> minimal date for asc, maximal for desc, so None stay at ends consistently
            if d is None:
                return datetime.min if not reverse else datetime.max
            return d
    else:
        def key_func(p: Dict[str, Any]):
            return _as_str(p.get(sort_field, "")).lower()

    sorted_posts = sorted(posts, key=key_func, reverse=reverse)

    return jsonify(
        [
            {
                "id": int(p["id"]),
                "title": p["title"],
                "content": p["content"],
                "author": p.get("author", ""),
                "date": p.get("date", ""),
            }
            for p in sorted_posts
        ]
    )


@app.get("/api/posts/search")
def search_posts():
    """Search posts. Supports AND filters and a convenience 'q' that matches any field.

    Query params (all optional):
      - q:       free-text matches any of: title, content, author, date
      - title:   substring for title
      - content: substring for content
      - author:  substring for author
      - date:    exact 'YYYY-MM-DD' match (or substring if you prefer; here substring for flexibility)
    """
    q = _as_str(request.args.get("q")).lower()
    title_q = _as_str(request.args.get("title")).lower()
    content_q = _as_str(request.args.get("content")).lower()
    author_q = _as_str(request.args.get("author")).lower()
    date_q = _as_str(request.args.get("date")).lower()

    posts = _load_posts()

    def matches(p: Dict[str, Any]) -> bool:
        t = _as_str(p.get("title", "")).lower()
        c = _as_str(p.get("content", "")).lower()
        a = _as_str(p.get("author", "")).lower()
        d = _as_str(p.get("date", "")).lower()

        # 'q' matches any field
        if q and not (q in t or q in c or q in a or q in d):
            return False
        if title_q and title_q not in t:
            return False
        if content_q and content_q not in c:
            return False
        if author_q and author_q not in a:
            return False
        if date_q and date_q not in d:
            return False
        return True

    filtered = [p for p in posts if matches(p)]
    return jsonify(
        [
            {
                "id": int(p["id"]),
                "title": p["title"],
                "content": p["content"],
                "author": p.get("author", ""),
                "date": p.get("date", ""),
            }
            for p in filtered
        ]
    )


@app.post("/api/posts")
def create_post():
    """Create a new post from JSON body:
       {title, content, author, date(YYYY-MM-DD)} -> 201 + post JSON.
    """
    data = request.get_json(silent=True) or {}
    title = _as_str(data.get("title"))
    content = _as_str(data.get("content"))
    author = _as_str(data.get("author"))
    date_str = _as_str(data.get("date"))

    missing = []
    if not title:
        missing.append("title")
    if not content:
        missing.append("content")
    if not author:
        missing.append("author")
    # date required and must be valid YYYY-MM-DD
    dt = _parse_date_str(date_str)
    if dt is None:
        missing.append("date")

    if missing:
        return jsonify({"message": "Missing or invalid required field(s).", "missing": missing}), 400

    posts = _load_posts()
    post = {
        "id": _next_id(posts),
        "title": title,
        "content": content,
        "author": author,
        "date": date_str,  # store canonical string
    }
    posts.append(post)
    _save_posts(posts)

    resp = jsonify(
        {"id": int(post["id"]), "title": title, "content": content, "author": author, "date": date_str}
    )
    return make_response(resp, 201)


@app.put("/api/posts/<int:post_id>")
def update_post(post_id: int):
    """Update an existing post. Any of title/content/author/date can be provided.

    Empty strings are ignored (keep current).
    Date, if provided, must be 'YYYY-MM-DD'.
    """
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
                return jsonify({"message": "Invalid date format, expected YYYY-MM-DD."}), 400
            target["date"] = new_date

    _save_posts(posts)
    return jsonify(
        {
            "id": int(target["id"]),
            "title": target["title"],
            "content": target["content"],
            "author": target.get("author", ""),
            "date": target.get("date", ""),
        }
    ), 200


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