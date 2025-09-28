# frontend_app.py
"""Frontend for MasterBlog: Create, Update, Delete (with author & date).
Adds client-side date validation with inline error messages.
"""

from __future__ import annotations

from flask import Flask, render_template_string, request, redirect, url_for
import requests

app = Flask(__name__)

# Backend-API base URL
BACKEND_BASE = "http://localhost:5002"

# Date constraints (must match backend!)
MIN_DATE = "1900-01-01"
MAX_DATE = "2100-12-31"

# ---------------------------- Styles ----------------------------
BASE_CSS = """
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; margin: 40px; color:#111; }
  h1 { margin: 0 0 24px; }
  form.card, article {
    border: 1px solid #e5e5e5; border-radius: 14px; padding: 16px; margin: 12px 0; background: #fafafa;
  }
  form.inline { border:0; padding:0; margin:0; background: transparent; display:inline; }

  label { display:block; font-weight: 600; margin-top: 8px; }
  input, textarea {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd; border-radius: 12px; font: inherit; background:#fff;
  }
  textarea { min-height: 120px; }

  .error { background:#ffeaea; border:1px solid #ffc7c7; color:#8a1f1f; padding:10px; border-radius:12px; margin-bottom:12px; }
  .hint  { color:#666; font-size:.9rem; margin-top: 4px; }

  .meta { color:#666; margin-top: 0; }
  .actions { display:flex; gap:12px; margin-top: 12px; flex-wrap: wrap; }

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
  .btn.danger  { background:#b00020; color:#fff; border-color:#b00020; }
  .btn.danger:hover { box-shadow: 0 8px 20px rgba(176,0,32,.22); }
  .btn.ghost   { background:#fff; color:#111; border-color:#111; }

  .row { display:flex; gap:12px; margin-top: 12px; flex-wrap: wrap; }
"""

# ---------------------------- Templates ----------------------------
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

    <form id="createForm" method="post" action="{{{{ url_for('home') }}}}" class="card" novalidate>
      <h2>New Post</h2>
      <label for="title">Title</label>
      <input id="title" name="title" required />

      <label for="content">Content</label>
      <textarea id="content" name="content" required></textarea>

      <label for="author">Author</label>
      <input id="author" name="author" required />

      <label for="date">Date</label>
      <input id="date" name="date" type="date" required min="{MIN_DATE}" max="{MAX_DATE}" />
      <div id="dateErrorCreate" class="error" style="display:none;"></div>
      <div class="hint">Allowed range: {MIN_DATE} … {MAX_DATE}</div>

      <div class="row">
        <button type="submit" class="btn primary">Create</button>
      </div>
    </form>

    <h2>Posts</h2>
    {{% if posts %}}
      {{% for p in posts %}}
        <article>
          <h3>{{{{ p.title }}}}</h3>
          <p class="meta">#{{{{ p.id }}}} – by {{{{ p.author }}}} on {{{{ p.date }}}}</p>
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

    <script>
      // --- Client-side date validation (Create form) ---
      (function() {{
        const MIN = "{MIN_DATE}";
        const MAX = "{MAX_DATE}";
        const form = document.getElementById("createForm");
        const dateInput = document.getElementById("date");
        const err = document.getElementById("dateErrorCreate");

        function isValidDateStr(s) {{
          if (!s) return false;
          // Simple YYYY-MM-DD check
          const m = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.exec(s);
          if (!m) return false;
          // Range check using lexicographic compare works for YYYY-MM-DD
          return (s >= MIN && s <= MAX);
        }}

        function showError(msg) {{
          err.style.display = "block";
          err.textContent = msg;
          dateInput.setAttribute("aria-invalid", "true");
        }}

        function clearError() {{
          err.style.display = "none";
          err.textContent = "";
          dateInput.removeAttribute("aria-invalid");
        }}

        dateInput.addEventListener("input", function() {{
          if (isValidDateStr(dateInput.value)) {{
            clearError();
          }} else {{
            showError(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
          }}
        }});

        form.addEventListener("submit", function(e) {{
          if (!isValidDateStr(dateInput.value)) {{
            e.preventDefault();
            showError(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
            dateInput.focus();
          }}
        }});
      }})();
    </script>
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

    <form id="editForm" method="post" class="card" novalidate>
      <label for="title">Title</label>
      <input id="title" name="title" value="{{{{ post.title }}}}" />

      <label for="content">Content</label>
      <textarea id="content" name="content">{{{{ post.content }}}}</textarea>

      <label for="author">Author</label>
      <input id="author" name="author" value="{{{{ post.author }}}}" />

      <label for="date">Date</label>
      <input id="date" name="date" type="date" value="{{{{ post.date }}}}" min="{MIN_DATE}" max="{MAX_DATE}" />
      <div id="dateErrorEdit" class="error" style="display:none;"></div>
      <div class="hint">Allowed range: {MIN_DATE} … {MAX_DATE}</div>

      <div class="row">
        <button type="submit" class="btn primary">Save</button>
        <a class="btn ghost" href="{{{{ url_for('home') }}}}">Cancel</a>
      </div>
    </form>

    <script>
      // --- Client-side date validation (Edit form) ---
      (function() {{
        const MIN = "{MIN_DATE}";
        const MAX = "{MAX_DATE}";
        const form = document.getElementById("editForm");
        const dateInput = document.getElementById("date");
        const err = document.getElementById("dateErrorEdit");

        function isValidDateStr(s) {{
          if (!s) return false;
          const m = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.exec(s);
          if (!m) return false;
          return (s >= MIN && s <= MAX);
        }}

        function showError(msg) {{
          err.style.display = "block";
          err.textContent = msg;
          dateInput.setAttribute("aria-invalid", "true");
        }}

        function clearError() {{
          err.style.display = "none";
          err.textContent = "";
          dateInput.removeAttribute("aria-invalid");
        }}

        dateInput.addEventListener("input", function() {{
          if (isValidDateStr(dateInput.value)) {{
            clearError();
          }} else {{
            showError(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
          }}
        }});

        form.addEventListener("submit", function(e) {{
          // only block if user provided a value (empty means "no change" for PUT)
          const val = dateInput.value;
          if (val && !isValidDateStr(val)) {{
            e.preventDefault();
            showError(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
            dateInput.focus();
          }}
        }});
      }})();
    </script>
  </body>
</html>
"""

# ---------------------------- Helpers ----------------------------
def _explain_error(resp: requests.Response) -> str:
    """Return readable error message from a requests.Response."""
    try:
        return f"Error {resp.status_code}: {resp.json()}"
    except Exception:
        return f"Error {resp.status_code}: {resp.text[:200]}"


# ---------------------------- Routes ----------------------------
@app.route("/", methods=["GET", "POST"])
def home():
    """List posts and handle creation of new posts."""
    error = None

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        author = (request.form.get("author") or "").strip()
        date = (request.form.get("date") or "").strip()

        try:
            resp = requests.post(
                f"{BACKEND_BASE}/api/posts",
                json={"title": title, "content": content, "author": author, "date": date},
                headers={"Accept": "application/json"},
                timeout=5,
            )
            if resp.status_code == 201:
                return redirect(url_for("home"))
            error = _explain_error(resp)
        except Exception as exc:
            error = f"Backend not reachable: {exc}"

    posts = []
    try:
        resp = requests.get(
            f"{BACKEND_BASE}/api/posts",
            headers={"Accept": "application/json"},
            timeout=5,
        )
        if resp.ok:
            posts = resp.json()
        else:
            error = _explain_error(resp)
    except Exception as exc:
        error = f"Could not load posts from backend: {exc}"

    return render_template_string(INDEX_TMPL, posts=posts, error=error)


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit(post_id: int):
    """Edit a post (loads current data, then PUTs updates)."""
    error = None

    # Load current post
    try:
        resp = requests.get(f"{BACKEND_BASE}/api/posts/{post_id}", timeout=5)
        current = resp.json() if resp.ok else None
    except Exception:
        current = None

    if not current:
        return (
            render_template_string(
                EDIT_TMPL,
                post={"id": post_id, "title": "", "content": "", "author": "", "date": ""},
                error="Post not found.",
            ),
            404,
        )

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        author = (request.form.get("author") or "").strip()
        date = (request.form.get("date") or "").strip()

        payload = {}
        if title:
            payload["title"] = title
        if content:
            payload["content"] = content
        if author:
            payload["author"] = author
        if date:
            payload["date"] = date

        try:
            resp = requests.put(
                f"{BACKEND_BASE}/api/posts/{post_id}",
                json=payload,
                headers={"Accept": "application/json"},
                timeout=5,
            )
            if resp.ok:
                return redirect(url_for("home"))
            error = _explain_error(resp)
        except Exception as exc:
            error = f"Backend not reachable: {exc}"

    return render_template_string(EDIT_TMPL, post=current, error=error)


@app.route("/delete/<int:post_id>", methods=["POST"])
def delete(post_id: int):
    """Delete a post and return to list."""
    try:
        requests.delete(f"{BACKEND_BASE}/api/posts/{post_id}", timeout=5)
    except Exception:
        pass
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4999, debug=True)