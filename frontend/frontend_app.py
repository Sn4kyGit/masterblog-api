# frontend_app.py
"""Tiny demo-frontend that calls the backend API to list/add posts."""

from __future__ import annotations

from flask import Flask, render_template_string, request, redirect
import requests

app = Flask(__name__)

# Backend läuft auf 5002 (siehe backend_app.py)
BACKEND_BASE = "http://localhost:5002"

TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>MasterBlog • Frontend</title>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; }
      h1 { margin-top: 0; }
      form, article { border: 1px solid #e5e5e5; border-radius: 10px; padding: 16px; margin: 12px 0; background: #fafafa; }
      label { display:block; font-weight: 600; margin-top: 8px; }
      input, textarea { width: 100%; padding: 8px 10px; border: 1px solid #ddd; border-radius: 8px; font: inherit; }
      button { padding: 8px 14px; border-radius: 8px; background:#111; color:#fff; border:1px solid #111; cursor:pointer; }
      .error { background:#ffeaea; border:1px solid #ffc7c7; color:#8a1f1f; padding:10px; border-radius:8px; }
      .meta { color:#666; margin-top: 0; }
    </style>
  </head>
  <body>
    <h1>MasterBlog</h1>

    {% if error %}
      <div class="error">{{ error }}</div>
    {% endif %}

    <form method="post">
      <h2>New Post</h2>
      <label for="title">Title</label>
      <input id="title" name="title" required />

      <label for="content">Content</label>
      <textarea id="content" name="content" required></textarea>

      <div style="margin-top:10px;">
        <button type="submit">Create</button>
      </div>
    </form>

    <h2>Posts</h2>
    {% if posts %}
      {% for p in posts %}
        <article>
          <h3>{{ p.title }}</h3>
          <p class="meta">#{{ p.id }}</p>
          <p>{{ p.content }}</p>
        </article>
      {% endfor %}
    {% else %}
      <p>No posts yet.</p>
    {% endif %}
  </body>
</html>
"""

def _explain_error(resp: requests.Response) -> str:
    try:
        return f"Error {resp.status_code}: {resp.json()}"
    except Exception:
        return f"Error {resp.status_code}: {resp.text[:200]}"

@app.route("/", methods=["GET", "POST"])
def home():
    error = None
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        try:
            r = requests.post(
                f"{BACKEND_BASE}/api/posts",
                json={"title": title, "content": content},
                headers={"Accept": "application/json"},
                timeout=5,
            )
            if r.status_code == 201:
                return redirect("/")
            error = _explain_error(r)
        except Exception as exc:
            error = f"Backend not reachable: {exc}"

    posts = []
    try:
        r = requests.get(
            f"{BACKEND_BASE}/api/posts",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if r.ok:
            posts = r.json()
        else:
            error = _explain_error(r)
    except Exception as exc:
        error = f"Could not load posts from backend: {exc}"

    return render_template_string(TEMPLATE, posts=posts, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4999, debug=True)