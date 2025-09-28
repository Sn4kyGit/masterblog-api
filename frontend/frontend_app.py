# frontend_app.py
"""Frontend for MasterBlog: Create, Update, Delete via backend API."""

from __future__ import annotations

from flask import Flask, render_template_string, request, redirect, url_for
import requests

app = Flask(__name__)

# Backend-API Basis-URL
BACKEND_BASE = "http://localhost:5002"

# ---------------------------- Templates ----------------------------

BASE_CSS = """
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; color:#111; }
  h1 { margin: 0 0 24px; }
  /* Karten-Stil nur für "große" Formulare/Artikel */
  form.card, article {
    border: 1px solid #e5e5e5; border-radius: 14px; padding: 16px; margin: 12px 0; background: #fafafa;
  }
  /* Inline-Form (z.B. Delete) ohne Karte */
  form.inline { border:0; padding:0; margin:0; background: transparent; display:inline; }

  label { display:block; font-weight: 600; margin-top: 8px; }
  input, textarea {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 12px; font: inherit; background:#fff;
  }
  textarea { min-height: 120px; }
  .error { background:#ffeaea; border:1px solid #ffc7c7; color:#8a1f1f; padding:10px; border-radius:12px; margin-bottom:12px; }
  .meta { color:#666; margin-top: 0; }
  .actions { display:flex; gap:12px; margin-top: 12px; flex-wrap: wrap; }

  /* --- Unified button system --- */
  .btn, button {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 140px; height: 48px; padding: 0 18px;
    border-radius: 16px; border: 1px solid; font-weight: 800;
    letter-spacing:.2px; text-decoration:none; cursor:pointer;
    box-shadow: 0 2px 10px rgba(0,0,0,.08);
    transition: transform .06s ease, box-shadow .2s ease, background .2s ease, color .2s ease, border-color .2s ease;
  }
  .btn:hover, button:hover { transform: translateY(-1px); box-shadow: 0 8px 20px rgba(0,0,0,.12); }
  .btn:active, button:active { transform: translateY(0); box-shadow: 0 3px 10px rgba(0,0,0,.12); }

  .btn.primary { background:#111; color:#fff; border-color:#111; }
  /* Delete im gleichen "filled"-Stil, nur rot */
  .btn.danger  { background:#b00020; color:#fff; border-color:#b00020; }
  .btn.danger:hover { box-shadow: 0 8px 20px rgba(176,0,32,.22); }

  .row { display:flex; gap:12px; margin-top: 12px; flex-wrap: wrap; }
"""

INDEX_TMPL = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>MasterBlog • Frontend</title>
    <style>{BASE_CSS}</style>
  </head>
  <body>
    <h1>MasterBlog</h1>

    {{% if error %}}
      <div class="error">{{{{ error }}}}</div>
    {{% endif %}}

    <form method="post" action="{{{{ url_for('home') }}}}" class="card">
      <h2>New Post</h2>
      <label for="title">Title</label>
      <input id="title" name="title" required />

      <label for="content">Content</label>
      <textarea id="content" name="content" required></textarea>

      <div class="row">
        <button type="submit" class="btn primary">Create</button>
      </div>
    </form>

    <h2>Posts</h2>
    {{% if posts %}}
      {{% for p in posts %}}
        <article>
          <h3>{{{{ p.title }}}}</h3>
          <p class="meta">#{{{{ p.id }}}}</p>
          <p>{{{{ p.content }}}}</p>
          <div class="actions">
            <a class="btn primary" href="{{{{ url_for('edit', post_id=p.id) }}}}">Edit</a>
            <form method="post" action="{{{{ url_for('delete', post_id=p.id) }}}}" class="inline">
              <button type="submit" class="btn danger" onclick="return confirm('Delete post #{{{{p.id}}}}?');">Delete</button>
            </form>
          </div>
        </article>
      {{% endfor %}}
    {{% else %}}
      <p>No posts yet.</p>
    {{% endif %}}
  </body>
</html>
"""

EDIT_TMPL = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Edit Post • MasterBlog</title>
    <style>{BASE_CSS}</style>
  </head>
  <body>
    <h1>Edit Post #{{{{ post.id }}}}</h1>

    {{% if error %}}
      <div class="error">{{{{ error }}}}</div>
    {{% endif %}}

    <form method="post" class="card">
      <label for="title">Title</label>
      <input id="title" name="title" value="{{{{ post.title }}}}" />

      <label for="content">Content</label>
      <textarea id="content" name="content">{{{{ post.content }}}}</textarea>

      <div class="row">
        <button type="submit" class="btn primary">Save</button>
        <a class="btn" style="background:#666;border-color:#666;color:#fff;" href="{{{{ url_for('home') }}}}">Cancel</a>
      </div>
    </form>
  </body>
</html>
"""

# ---------------------------- Helpers ----------------------------

def _explain_error(resp: requests.Response) -> str:
  try:
    return f"Error {resp.status_code}: {resp.json()}"
  except Exception:
    return f"Error {resp.status_code}: {resp.text[:200]}"

# ---------------------------- Routes ----------------------------

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
                return redirect(url_for("home"))
            error = _explain_error(r)
        except Exception as exc:
            error = f"Backend not reachable: {exc}"

    posts = []
    try:
        r = requests.get(f"{BACKEND_BASE}/api/posts", headers={"Accept": "application/json"}, timeout=5)
        if r.ok:
            posts = r.json()
        else:
            error = _explain_error(r)
    except Exception as exc:
        error = f"Could not load posts from backend: {exc}"

    return render_template_string(INDEX_TMPL, posts=posts, error=error)


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit(post_id: int):
    error = None

    try:
        r = requests.get(f"{BACKEND_BASE}/api/posts", timeout=5)
        current = next((p for p in r.json() if int(p["id"]) == post_id), None) if r.ok else None
    except Exception:
        current = None

    if not current:
        return render_template_string(EDIT_TMPL, post={"id": post_id, "title": "", "content": ""}, error="Post not found."), 404

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        payload = {}
        if title:
            payload["title"] = title
        if content:
            payload["content"] = content

        try:
            r = requests.put(
                f"{BACKEND_BASE}/api/posts/{post_id}",
                json=payload,
                headers={"Accept": "application/json"},
                timeout=5,
            )
            if r.ok:
                return redirect(url_for("home"))
            error = _explain_error(r)
        except Exception as exc:
            error = f"Backend not reachable: {exc}"

    return render_template_string(EDIT_TMPL, post=current, error=error)


@app.route("/delete/<int:post_id>", methods=["POST"])
def delete(post_id: int):
    try:
        requests.delete(f"{BACKEND_BASE}/api/posts/{post_id}", timeout=5)
    except Exception:
        pass
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4999, debug=True)