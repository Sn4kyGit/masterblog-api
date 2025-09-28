# frontend_app.py
"""Frontend for MasterBlog with a hero header, centered layout, likes & comments,
and client-side date validation.
"""

from __future__ import annotations

from flask import Flask, render_template_string, request, redirect, url_for
import requests

app = Flask(__name__)

BACKEND_BASE = "http://localhost:5002"
MIN_DATE = "1900-01-01"
MAX_DATE = "2100-12-31"

# ---------------------------- Styles ----------------------------
BASE_CSS = """
  :root {
    --bg: #0b0b0c;
    --fg: #101012;
    --card: #ffffff;
    --muted: #6a6a6a;
    --border: #e9e9ec;
    --primary: #111111;
    --danger: #b00020;
    --radius: 16px;
    --shadow: 0 2px 10px rgba(0,0,0,.08);
    --shadow-lg: 0 10px 30px rgba(0,0,0,.18);
    --w: min(50vw, 860px); /* ca. Hälfte des Fensters, gedeckelt */
  }

  * { box-sizing: border-box; }
  html, body { height: 100%; }
  body {
    margin: 0;
    font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, "Apple Color Emoji", "Segoe UI Emoji";
    color: #111;
    background: #f6f7f9;
  }

 /* Hero Banner */
.hero {
  background: linear-gradient(135deg, #111827 0%, #1f2937 40%, #3b82f6 100%);
  color: #fff;
  padding: 80px 20px 60px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
  border-bottom: 6px solid #2563eb; /* kräftige Akzentlinie */
}
.hero .title {
  font-size: clamp(42px, 7vw, 64px);
  font-weight: 800;
  margin: 0 0 12px;
  letter-spacing: -0.03em;
  text-shadow: 0 4px 10px rgba(0,0,0,0.4);
}
.hero .subtitle {
  margin: 0;
  font-size: clamp(16px, 2.5vw, 22px);
  font-weight: 500;
  color: rgba(255,255,255,0.9);
}

  /* Centered container ~50% viewport width (responsive fallback) */
  .container {
    width: var(--w);
    max-width: 100%;
    margin: 0 auto;
    padding: 28px 20px 60px;
  }
  @media (max-width: 900px) { :root { --w: min(90vw, 860px); } }

  h1, h2, h3 { margin: 0 0 16px; }
  h2.section { margin-top: 28px; margin-bottom: 12px; }

  form.card, article {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px;
    margin: 14px 0;
    box-shadow: var(--shadow);
  }
  form.inline { border:0; padding:0; margin:0; background: transparent; display:inline; }

  label { display:block; font-weight: 650; margin-top: 10px; }
  input, textarea {
    width: 100%; padding: 12px 14px; border: 1px solid #ddd; border-radius: 12px; font: inherit; background:#fff;
  }
  textarea { min-height: 120px; }

  .error { background:#ffeaea; border:1px solid #ffc7c7; color:#8a1f1f; padding:10px; border-radius:12px; margin: 10px 0 12px; }
  .hint  { color:#666; font-size:.92rem; margin-top: 6px; }

  .meta { color: var(--muted); margin: 4px 0 0; font-size: .95rem; }
  .actions { display:flex; gap:12px; margin-top: 14px; flex-wrap: wrap; }

  .btn, button {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 140px; height: 48px; padding: 0 18px;
    border-radius: 16px; border: 1px solid; font-weight: 800;
    letter-spacing:.2px; text-decoration:none; cursor:pointer;
    box-shadow: var(--shadow);
    transition: transform .06s ease, box-shadow .2s ease, background .2s ease, color .2s ease, border-color .2s ease;
  }
  .btn:hover, button:hover { transform: translateY(-1px); box-shadow: var(--shadow-lg); }
  .btn:active, button:active { transform: translateY(0); box-shadow: var(--shadow); }

  .btn.primary { background: var(--primary); color:#fff; border-color: var(--primary); }
  .btn.danger  { background: var(--danger); color:#fff; border-color: var(--danger); }
  .btn.ghost   { background:#fff; color:#111; border-color:#111; }

  .row { display:flex; gap:12px; margin-top: 12px; flex-wrap: wrap; }
  .muted { color:#777; font-size:.95rem; }
  .comment { padding:8px 0; border-top:1px dashed #e5e5e5; }
  .stack { display:flex; flex-direction:column; gap:6px; }
"""

# ---------------------------- Templates ----------------------------
INDEX_TMPL = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>MasterBlog • Frontend</title>
    <style>{BASE_CSS}</style>
  </head>
  <body>
    <header class="hero">
      <h1 class="title">MasterBlog</h1>
      <p class="subtitle">A minimal blog engine with posts, likes & comments</p>
    </header>

    <main class="container">
      {{% if error %}}
        <div class="error" aria-live="polite">{{{{ error }}}}</div>
      {{% endif %}}

      <form id="createForm" method="post" action="{{{{ url_for('home') }}}}" class="card" novalidate>
        <h2 class="section">New Post</h2>
        <label for="title">Title</label>
        <input id="title" name="title" required />

        <label for="content">Content</label>
        <textarea id="content" name="content" required></textarea>

        <label for="author">Author</label>
        <input id="author" name="author" required />

        <label for="date">Date</label>
        <input id="date" name="date" type="date" required min="{MIN_DATE}" max="{MAX_DATE}" />
        <div id="dateErrorCreate" class="error" style="display:none;" aria-live="polite"></div>
        <div class="hint">Allowed range: {MIN_DATE} … {MAX_DATE}</div>

        <div class="row">
          <button type="submit" class="btn primary">Create</button>
        </div>
      </form>

      <h2 class="section" style="margin-top: 26px;">Posts</h2>
      {{% if posts %}}
        {{% for p in posts %}}
          <article data-post-id="{{{{ p.id }}}}">
            <h3 style="margin-bottom: 6px;">{{{{ p.title }}}}</h3>
            <p class="meta">#{{{{ p.id }}}} – by {{{{ p.author }}}} on {{{{ p.date }}}}</p>
            <p style="margin-top: 10px;">{{{{ p.content }}}}</p>

            <div class="actions">
              <button class="btn primary like-btn" data-id="{{{{ p.id }}}}" aria-label="Like post {{{{ p.id }}}}">
                ❤️ Like (<span class="like-count">{{{{ p.likes }}}}</span>)
              </button>
              <a class="btn ghost" href="{{{{ url_for('edit', post_id=p.id) }}}}">Edit</a>
              <form method="post" action="{{{{ url_for('delete', post_id=p.id) }}}}" class="inline">
                <button type="submit" class="btn danger" onclick="return confirm('Delete post #{{{{p.id}}}}?');">Delete</button>
              </form>
            </div>

            <div class="stack" style="margin-top:12px">
              <div class="muted"><strong>Comments</strong></div>
              <div class="comments" id="comments-{{{{ p.id }}}}">
                {{% for c in p.comments %}}
                  <div class="comment">
                    <div class="muted">{{{{ c.author }}}} • {{{{ c.date }}}}</div>
                    <div>{{{{ c.text }}}}</div>
                  </div>
                {{% endfor %}}
                {{% if not p.comments %}}
                  <div class="muted">No comments yet.</div>
                {{% endif %}}
              </div>

              <form class="inline add-comment-form" data-id="{{{{ p.id }}}}" onsubmit="return false;">
                <div class="row" style="gap:8px; align-items:flex-start;">
                  <input name="author" placeholder="Your name" style="max-width:220px" required />
                  <input name="text" placeholder="Your comment" required style="flex:1" />
                  <button class="btn primary" type="submit">Add</button>
                </div>
              </form>
            </div>
          </article>
        {{% endfor %}}
      {{% else %}}
        <article><p class="muted" style="margin:0;">No posts yet.</p></article>
      {{% endif %}}
    </main>

    <script>
      const BACKEND_BASE = "{BACKEND_BASE}";
      const MIN = "{MIN_DATE}";
      const MAX = "{MAX_DATE}";

      // --- Date validation (Create) ---
      (function() {{
        const form = document.getElementById("createForm");
        const dateInput = document.getElementById("date");
        const err = document.getElementById("dateErrorCreate");

        function ok(s) {{
          if (!s) return false;
          const m = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.exec(s);
          return !!m && s >= MIN && s <= MAX;
        }}

        function show(msg) {{
          err.style.display = "block";
          err.textContent = msg;
          dateInput.setAttribute("aria-invalid", "true");
        }}
        function clear() {{
          err.style.display = "none";
          err.textContent = "";
          dateInput.removeAttribute("aria-invalid");
        }}

        dateInput.addEventListener("input", () => {{
          ok(dateInput.value) ? clear() : show(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
        }});

        form.addEventListener("submit", (e) => {{
          if (!ok(dateInput.value)) {{
            e.preventDefault();
            show(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
            dateInput.focus();
          }}
        }});
      }})();

      // --- Likes (AJAX) ---
      document.querySelectorAll(".like-btn").forEach(btn => {{
        btn.addEventListener("click", async () => {{
          const id = btn.getAttribute("data-id");
          btn.disabled = true;
          try {{
            const res = await fetch(`${{BACKEND_BASE}}/api/posts/${{id}}/like`, {{ method: "POST" }});
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            const countEl = btn.querySelector(".like-count");
            if (countEl) countEl.textContent = data.likes;
          }} catch (err) {{
            alert("Could not like the post: " + err);
          }} finally {{
            btn.disabled = false;
          }}
        }});
      }});

      // --- Comments (AJAX, safe DOM insertion) ---
      document.querySelectorAll(".add-comment-form").forEach(form => {{
        form.addEventListener("submit", async () => {{
          const id = form.getAttribute("data-id");
          const author = form.querySelector('input[name="author"]').value.trim();
          const text = form.querySelector('input[name="text"]').value.trim();
          if (!author || !text) return;

          const btn = form.querySelector("button[type=submit]");
          btn.disabled = true;

          try {{
            const res = await fetch(`${{BACKEND_BASE}}/api/posts/${{id}}/comments`, {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{ author, text }})
            }});
            if (!res.ok) throw new Error(await res.text());
            const c = await res.json();

            const list = document.getElementById(`comments-${{id}}`);
            if (list && list.firstElementChild && list.firstElementChild.classList.contains("muted")) {{
              list.firstElementChild.remove();
            }}

            const wrapper = document.createElement("div");
            wrapper.className = "comment";

            const meta = document.createElement("div");
            meta.className = "muted";
            meta.textContent = `${{c.author}} • ${{c.date}}`;

            const body = document.createElement("div");
            body.textContent = c.text;

            wrapper.append(meta, body);
            list.appendChild(wrapper);

            form.reset();
          }} catch (err) {{
            alert("Could not add comment: " + err);
          }} finally {{
            btn.disabled = false;
          }}
        }});
      }});
    </script>
  </body>
</html>
"""

EDIT_TMPL = f"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Edit Post • MasterBlog</title>
    <style>{BASE_CSS}</style>
  </head>
  <body>
    <header class="hero">
      <h1 class="title">MasterBlog</h1>
      <p class="subtitle">Edit your post</p>
    </header>

    <main class="container">
      {{% if error %}}
        <div class="error" aria-live="polite">{{{{ error }}}}</div>
      {{% endif %}}

      <form id="editForm" method="post" class="card" novalidate>
        <h2 class="section">Edit Post #{{{{ post.id }}}}</h2>

        <label for="title">Title</label>
        <input id="title" name="title" value="{{{{ post.title }}}}" />

        <label for="content">Content</label>
        <textarea id="content" name="content">{{{{ post.content }}}}</textarea>

        <label for="author">Author</label>
        <input id="author" name="author" value="{{{{ post.author }}}}" />

        <label for="date">Date</label>
        <input id="date" name="date" type="date" value="{{{{ post.date }}}}" min="{MIN_DATE}" max="{MAX_DATE}" />
        <div id="dateErrorEdit" class="error" style="display:none;" aria-live="polite"></div>
        <div class="hint">Allowed range: {MIN_DATE} … {MAX_DATE}</div>

        <div class="row">
          <button type="submit" class="btn primary">Save</button>
          <a class="btn ghost" href="{{{{ url_for('home') }}}}">Cancel</a>
        </div>
      </form>
    </main>

    <script>
      const MIN = "{MIN_DATE}";
      const MAX = "{MAX_DATE}";
      (function() {{
        const form = document.getElementById("editForm");
        const dateInput = document.getElementById("date");
        const err = document.getElementById("dateErrorEdit");

        function ok(s) {{
          if (!s) return true; // empty = no change
          const m = /^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.exec(s);
          return !!m && s >= MIN && s <= MAX;
        }}
        function show(msg) {{
          err.style.display = "block";
          err.textContent = msg;
          dateInput.setAttribute("aria-invalid", "true");
        }}
        function clear() {{
          err.style.display = "none";
          err.textContent = "";
          dateInput.removeAttribute("aria-invalid");
        }}

        dateInput.addEventListener("input", () => {{
          ok(dateInput.value) ? clear() : show(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
        }});

        form.addEventListener("submit", (e) => {{
          if (!ok(dateInput.value)) {{
            e.preventDefault();
            show(`Invalid date. Use YYYY-MM-DD between ${{MIN}} and ${{MAX}}.`);
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
    resp = requests.get(f"{BACKEND_BASE}/api/posts", headers={"Accept": "application/json"}, timeout=5)
    posts = resp.json() if resp.ok else []
    if not resp.ok and not error:
      error = _explain_error(resp)
  except Exception as exc:
    error = f"Could not load posts from backend: {exc}"

  return render_template_string(INDEX_TMPL, posts=posts, error=error)


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit(post_id: int):
  """Edit a post (loads current data, then PUTs updates)."""
  error = None
  try:
    resp = requests.get(f"{BACKEND_BASE}/api/posts/{post_id}", timeout=5)
    current = resp.json() if resp.ok else None
  except Exception:
    current = None

  if not current:
    return (
      render_template_string(
        "<main class='container'><p class='error'>Post not found.</p>"
        "<p><a href='{{ url_for(\"home\") }}'>Back</a></p></main>"
      ),
      404,
    )

  if request.method == "POST":
    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    author = (request.form.get("author") or "").strip()
    date = (request.form.get("date") or "").strip()

    payload = {}
    if title: payload["title"] = title
    if content: payload["content"] = content
    if author: payload["author"] = author
    if date: payload["date"] = date

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