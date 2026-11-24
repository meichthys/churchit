#!/usr/bin/env python3
"""Generate the churchit.app pages that mirror content shipped in the repo.

- getting-started.html comes from README.md ("Installing Churchit") and the
  setup one-liner in deploy/README.md.
- screenshots.html comes from SHOTS in docs/screenshots.py, which also takes
  the pictures.

The manual is not on churchit.app: Frappe Wiki on docs.churchit.app syncs it
from manual/, and the pages link to it. Page shells live in docs/_templates/
(Jekyll skips underscore folders, so GitHub Pages does not serve them). Needs
markdown2, which the bench env has:

    ../../env/bin/python docs/build_docs.py     # from the app root
"""

import glob
import html
import os
import re

import markdown2

from screenshots import SHOTS, THEMES

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(APP_ROOT, "docs")
TEMPLATES = os.path.join(DOCS, "_templates")
MANUAL = os.path.join(APP_ROOT, "manual")
README = os.path.join(APP_ROOT, "README.md")
DEPLOY_README = os.path.join(APP_ROOT, "deploy", "README.md")

# The online manual: the Frappe Wiki space that syncs manual/. manual/<folder>/<page>.md is at
# <MANUAL_URL>/<folder>/<page>, and a folder's README.md at <MANUAL_URL>/<folder>.
MANUAL_URL = "https://docs.churchit.app/manual"

# Relative README links are rewritten to the file on GitHub's default branch.
REPO_BLOB_URL = "https://github.com/meichthys/churchit/blob/HEAD"
INSTALL_HEADING = "## 📥 Installing Churchit"
FIRST_STEPS_HEADING = "### First steps after installing"
DOMAIN_HEADING = "### Setting up a public domain"
DEFAULT_PATH = "frappe-cloud"  # heading slug of the deployment tab shown first
FENCE = re.compile(r"```\w*\n(.*?)```\n?", re.S)
FENCE_TOKEN = re.compile("\x00(\\d+)\x00")

# The colour of each module's icon in the desk, for the screenshots page.
MODULE_COLORS = {
	"Desk": "#6366f1",
	"Ministries": "#ec4899",
	"People": "#14b8a6",
	"Study": "#f59e0b",
	"Website": "#06b6d4",
}


def build_getting_started():
	readme = Readme(README)
	intro, subsections = split_subsections(readme.section(INSTALL_HEADING))
	labels, table = parse_paths_table(intro)
	paths = [(title, body) for title, body in subsections if github_slug(title) in table]
	if len(paths) != len(table):
		raise SystemExit("README.md: install table rows do not match the ### sections below it")
	if DEFAULT_PATH not in table:
		raise SystemExit(f"README.md: default path {DEFAULT_PATH!r} is not in the install table")
	write_page(
		"getting-started.html",
		one_liner=html.escape(load_one_liner()),
		tabs="\n          ".join(render_tab(title) for title, _ in paths),
		paths="\n        ".join(
			render_path(readme, title, body, labels, table[github_slug(title)]) for title, body in paths
		),
		first_steps=readme.render(readme.section(FIRST_STEPS_HEADING)),
		domain_setup=readme.render(readme.section(DOMAIN_HEADING)),
	)
	print(f"Wrote getting-started.html  ({len(paths)} paths)")


def build_screenshots():
	write_page(
		"screenshots.html",
		index="\n      ".join(f'<a href="#{shot.slug}">{html.escape(shot.title)}</a>' for shot in SHOTS),
		shots="\n\n    ".join(render_shot(shot) for shot in SHOTS),
	)
	print(f"Wrote screenshots.html  ({len(SHOTS)} features)")


def render_shot(shot):
	"""One feature: its text above the desktop picture, with the phone picture beside it."""
	devices = " ".join(f"has-{device}" for device in shot.views)
	frames = "".join(render_frame(shot, device) for device in shot.views)
	manual = f'\n        <a href="{MANUAL_URL}/{shot.manual}">Read the manual →</a>' if shot.manual else ""
	return f"""<section class="shot" id="{shot.slug}">
      <div class="shot-text">
        <p class="shot-module" style="--module: {MODULE_COLORS[shot.module]}">{html.escape(shot.module)}</p>
        <h2>{html.escape(shot.title)}</h2>
        <p>{html.escape(shot.caption)}</p>{manual}
      </div>
      <div class="shot-media {devices}">{frames}</div>
    </section>"""


def render_frame(shot, device):
	"""Both themes' pictures, of which the page's own theme shows one (see .img-light in style.css)."""
	viewport = shot.get_viewport(device)
	alt = html.escape(f"{shot.title} on a {'computer' if device == 'desktop' else 'phone'}")
	images = ""
	for theme in THEMES:
		src = shot.get_image_path(device, theme)
		if not os.path.exists(os.path.join(DOCS, src)):
			raise SystemExit(f"{src} is missing. Take it with: uv run docs/screenshots.py {shot.slug}")
		images += (
			f'<img class="img-{theme}" src="{src}" alt="{alt}" width="{viewport["width"]}" '
			f'height="{viewport["height"]}" loading="lazy" decoding="async" />'
		)
	href = shot.get_image_path(device, THEMES[0])
	return f'<a class="shot-frame shot-{device}" href="{href}" data-zoom>{images}</a>'


class Readme:
	"""README.md with fenced code masked out, so a `#` comment inside a code
	block is never mistaken for a heading. Fences are restored by render()."""

	def __init__(self, path):
		self.fences = []
		self.text = FENCE.sub(self.mask_fence, read(path))

	def mask_fence(self, match):
		self.fences.append(match.group(1))
		return f"\x00{len(self.fences) - 1}\x00"

	def section(self, heading):
		"""Body of a markdown section, up to the next heading of the same or higher level."""
		level = len(heading.split(" ", 1)[0])
		match = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^#{{1,{level}}} |\Z)", self.text, re.S | re.M)
		if not match:
			raise SystemExit(f"README.md: heading not found: {heading!r}")
		return match.group(1)

	def render(self, text):
		"""Section markdown -> page HTML. Fenced code becomes a command block with a copy button."""
		parts = FENCE_TOKEN.split(text)
		rendered = "".join(
			command_block(self.fences[int(part)]) if i % 2 else markdown2.markdown(part, extras=["tables"])
			for i, part in enumerate(parts)
		)
		return re.sub(r'href="(?!https?:|#|mailto:)', f'href="{REPO_BLOB_URL}/', rendered)


def load_one_liner():
	"""The curl setup command from deploy/README.md, checked against README.md."""
	match = re.search(r"```bash\n(curl .+?)\n```", read(DEPLOY_README))
	if not match:
		raise SystemExit("deploy/README.md: no curl one-liner found")
	if match.group(1) not in read(README):
		raise SystemExit("README.md and deploy/README.md disagree on the setup one-liner")
	return match.group(1)


def render_tab(title):
	slug = github_slug(title)
	selected = "true" if slug == DEFAULT_PATH else "false"
	return (
		f'<button role="tab" type="button" id="tab-{slug}" aria-controls="path-{slug}" '
		f'aria-selected="{selected}">{path_name(title)}</button>'
	)


def render_path(readme, title, body, labels, cells):
	"""One deployment-path tab panel: the table row as a definition list beside the section body."""
	slug = github_slug(title)
	hidden = "" if slug == DEFAULT_PATH else " hidden"
	tag = '<span class="tag">Recommended</span>' if "(recommended)" in title.lower() else ""
	meta = "".join(
		f"<dt>{label}</dt><dd>{inline_markdown(cell)}</dd>" for label, cell in zip(labels, cells, strict=True)
	)
	return (
		f'<article class="glass path" id="path-{slug}" role="tabpanel" aria-labelledby="tab-{slug}"{hidden}>'
		f'<div class="path-head">{tag}<h3>{path_name(title)}</h3><dl class="path-meta">{meta}</dl></div>'
		f'<div class="path-body">{readme.render(body)}</div></article>'
	)


def path_name(title):
	return re.sub(r"\s*\(recommended\)", "", title, flags=re.I)


def parse_paths_table(intro):
	"""The install comparison table -> (column labels, {heading slug: cells})."""
	labels, rows = [], {}
	for line in intro.splitlines():
		if not line.startswith("|"):
			continue
		cells = [cell.strip() for cell in line.strip("|").split("|")]
		link = re.match(r"\[.+?\]\(#(.+?)\)", cells[0])
		if link:
			rows[link.group(1)] = cells[1:]
		elif cells[0] == "" and not labels:
			labels = cells[1:]
	if not labels or not rows:
		raise SystemExit("README.md: install comparison table not found")
	return labels, rows


def split_subsections(body):
	"""(text before the first ### heading, [(title, body), ...])."""
	parts = re.split(r"^### (.+)\n", body, flags=re.M)
	return parts[0], list(zip(parts[1::2], parts[2::2], strict=True))


def github_slug(heading):
	return re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def inline_markdown(text):
	return re.sub(r"^<p>|</p>$", "", markdown2.markdown(text).strip())


def command_block(code):
	return (
		f'<div class="cmd"><code>{html.escape(code.strip())}</code>'
		'<button class="btn cmd-copy" type="button" data-copy>Copy</button></div>'
	)


def check_manual_links():
	"""Fail when a site page links to a page of the online manual that manual/ does not have."""
	for page in sorted(glob.glob(os.path.join(DOCS, "*.html"))):
		paths = re.findall(rf'href="{re.escape(MANUAL_URL)}/([^"#]+)', read(page))
		missing = sorted({path for path in paths if not os.path.exists(get_manual_file(path))})
		if missing:
			raise SystemExit(f"{os.path.basename(page)} links to missing manual pages: {', '.join(missing)}")


def get_manual_file(path):
	"""The Markdown file of a page of the online manual: <folder> is its README, <folder>/<page> a page."""
	folder, _, name = path.partition("/")
	return os.path.join(MANUAL, folder, f"{name or 'README'}.md")


def write_page(name, **slots):
	page = read(os.path.join(TEMPLATES, name.replace("-", "_")))
	for key, value in slots.items():
		page = page.replace("{" + key + "}", value)
	with open(os.path.join(DOCS, name), "w") as fh:
		fh.write(page)


def read(path):
	with open(path) as fh:
		return fh.read()


if __name__ == "__main__":
	build_getting_started()
	build_screenshots()
	check_manual_links()
