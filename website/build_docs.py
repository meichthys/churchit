#!/usr/bin/env python3
"""Generate documentation.html from the churchit "Manual: *" workspaces.

The user-facing manuals live as Frappe workspace content blocks in
`churchit/<module>/workspace/manual:_<name>/manual:_<name>.json`. This script
reads those blocks and renders them into the glassy marketing-site shell so the
documentation on the website always mirrors what's shipped in the app.

Run from the app root (apps/churchit):  python website/build_docs.py
"""

import glob
import json
import os
import re

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(APP_ROOT, "website", "documentation.html")

# Base address of the self-hosted churchit desk that /app/ links point at.
DESK_URL = "http://localhost:1423"

# Display order + presentation metadata (slug is the on-page anchor id).
MODULES = [
    ("Church Foundations",    "foundations",    "🏛️"),
    ("Church People",         "people",         "👥"),
    ("Church Finances",       "finances",       "💰"),
    ("Church Ministries",     "ministries",     "🤝"),
    ("Church Missions",       "missions",       "🌍"),
    ("Church Prayers",        "prayers",        "🙏"),
    ("Church Study",          "study",          "📖"),
    ("Church Communications", "communications", "✉️"),
    ("Church Operations",     "operations",     "🔧"),
    ("Church Website",        "website",        "🌐"),
]


def strip_tags(html):
    return re.sub(r"<[^>]+>", "", html or "").replace("&nbsp;", " ").strip()


def clean_inline(html):
    """Keep meaningful inline markup (links, breaks, emphasis); drop the
    styling <span> wrappers and inline style attributes the desk editor adds."""
    html = re.sub(r"</?span[^>]*>", "", html)          # unwrap styling spans
    html = re.sub(r'\sstyle="[^"]*"', "", html)         # drop inline styles
    html = re.sub(r'\sclass="[^"]*"', "", html)         # drop editor classes
    # Normalise Frappe desk links to a single self-hosted address. The editor
    # bakes in absolute dev URLs (http://development.localhost/app/...), bare
    # relative paths (/app/...), and occasionally mangles "app/x" into
    # "http://app/x". Collapse every variant to the /app/ path, then point it at
    # the local churchit desk. These links only resolve when self-hosting.
    html = re.sub(r'href="https?://app/', 'href="/app/', html)          # mangled host
    html = re.sub(r'href="https?://[^"/]+/app/', 'href="/app/', html)   # absolute dev URL
    html = re.sub(r'href="/app/', f'href="{DESK_URL}/app/', html)       # -> self-hosted desk
    return html.strip()


def load_manual(module):
    matches = glob.glob(
        os.path.join(APP_ROOT, "churchit", "*", "workspace", "manual:_*", "manual:_*.json")
    )
    for f in matches:
        data = json.load(open(f))
        if data.get("module") == module:
            return json.loads(data.get("content") or "[]")
    return []


def render_blocks(blocks):
    """Convert workspace editor blocks -> clean documentation HTML."""
    out = []
    for b in blocks:
        btype = b.get("type")
        data = b.get("data", {})
        raw = data.get("text", "")

        if btype in ("header",):
            lvl = min(int(data.get("level", 2)) + 1, 4)
            out.append(f"<h{lvl}>{strip_tags(raw)}</h{lvl}>")
            continue

        if btype == "list":
            tag = "ol" if data.get("style") == "ordered" else "ul"
            items = "".join(f"<li>{clean_inline(i)}</li>" for i in data.get("items", []))
            out.append(f"<{tag}>{items}</{tag}>")
            continue

        if btype != "paragraph":
            continue

        # Paragraphs carry the manual's headings as styled spans (h1/h2 classes).
        if 'class="h1"' in raw:
            continue  # the manual title — we render our own section header
        if 'class="h2"' in raw:
            out.append(f"<h3>{strip_tags(raw)}</h3>")
            continue

        text = clean_inline(raw)
        if text:
            out.append(f"<p>{text}</p>")
    return "\n          ".join(out)


def build():
    sidebar, sections = [], []
    for module, slug, emoji in MODULES:
        blocks = load_manual(module)
        if not blocks:
            continue
        label = module.replace("Church ", "")
        sidebar.append(
            f'<a href="#{slug}"><span aria-hidden="true">{emoji}</span> {label}</a>'
        )
        sections.append(
            f'''<article class="glass doc-section reveal" id="{slug}">
          <h2><span aria-hidden="true">{emoji}</span> {label} <span class="doc-badge">Manual</span></h2>
          {render_blocks(blocks)}
        </article>'''
        )

    html = TEMPLATE.format(
        sidebar="\n        ".join(sidebar),
        sections="\n\n        ".join(sections),
    )
    with open(OUT, "w") as fh:
        fh.write(html)
    print(f"Wrote {OUT}  ({len(sections)} modules)")


TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Documentation — churchit</title>
  <meta name="description" content="The churchit manual: how every module works, straight from the app's built-in guides." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>

  <header class="nav">
    <div class="wrap nav-inner">
      <a class="brand" href="index.html"><span class="mark">⛪</span> churchit</a>
      <button class="nav-toggle" aria-label="Menu"><span></span><span></span><span></span></button>
      <nav class="nav-links">
        <a href="index.html#features">Features</a>
        <a href="pricing.html">No&nbsp;Pricing</a>
        <a href="documentation.html" class="active">Documentation</a>
        <a href="https://github.com/" target="_blank" rel="noopener">GitHub</a>
        <a class="btn btn-primary" href="pricing.html">Get started</a>
      </nav>
    </div>
  </header>

  <div class="wrap doc-layout">
    <!-- Sidebar -->
    <aside class="glass doc-side reveal">
      <p class="title">Manual</p>
      <nav>
        {sidebar}
      </nav>
    </aside>

    <!-- Content -->
    <main class="doc-main">
      <section class="glass doc-hero reveal" style="padding-top:2.2rem">
        <span class="eyebrow">\U0001f4d8 The churchit manual</span>
        <h1 style="font-size:clamp(2rem,4vw,2.8rem); margin-top:.6rem">Documentation</h1>
        <p class="lead">Every module, explained. This page is generated straight from the in-app manuals, so what you read here is exactly what ships in churchit.</p>
      </section>

        {sections}

      <div class="center" style="margin:2rem 0 1rem">
        <a class="btn btn-primary btn-lg" href="pricing.html">See what all this costs →</a>
      </div>
    </main>
  </div>

  <footer>
    <div class="wrap foot">
      <a class="brand" href="index.html"><span class="mark">⛪</span> churchit</a>
      <nav class="foot-links">
        <a href="index.html#features">Features</a>
        <a href="pricing.html">No Pricing</a>
        <a href="documentation.html">Documentation</a>
        <a href="https://frappeframework.com" target="_blank" rel="noopener">Built on Frappe</a>
      </nav>
    </div>
    <div class="wrap"><small>Generated from the churchit in-app manuals. Re-run <code>website/build_docs.py</code> to refresh.</small></div>
  </footer>

  <script src="assets/app.js"></script>
</body>
</html>
'''


if __name__ == "__main__":
    build()
