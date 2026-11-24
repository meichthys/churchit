# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Markdown sources of the manuals in manual/, and the Manual workspaces built from them.

Each folder of manual/ is one manual: a README.md with the intro, and one Markdown file for each
feature. Frappe Wiki's GitHub Sync reads the same folder, so the files use plain Markdown with front
matter, the wiki's callouts (:::note to :::), <picture> screenshots, tables, Mermaid diagrams and
relative links between pages. The README names the workspace JSON that the folder builds. docs/build_manuals.py writes the
JSON, and tests/test_manual_hygiene.py fails when it is out of date. churchit.ai.manual_knowledge gives
the pages to Flow. Standard library only, so that docs/build_manuals.py runs without Frappe.
"""

import base64
import datetime
import glob
import hashlib
import html
import json
import os
import re

APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(APP_ROOT, "manual")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"^(#{1,3}) (.+)$")
CODE = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BOLD = re.compile(r"\*\*(.+?)\*\*")
ITALIC = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
COMMENT = re.compile(r"<!--.*?-->", re.S)
CALLOUT = re.compile(r"^:::(note|tip|caution|danger)(?:\[([^\]]*)\])?\n(.*?)\n:::$", re.M | re.S)
CALLOUT_TITLES = {"note": "Note", "tip": "Tip", "caution": "Caution", "danger": "Danger"}
DIAGRAM = re.compile(r"^```mermaid\n.*?\n```$", re.M | re.S)
DIAGRAM_MARK = "\x00diagram\x00"
PICTURE = re.compile(r"^<picture>.*?</picture>$", re.M | re.S)
PICTURE_DARK = re.compile(r'<source srcset="([^"]+)"')
PICTURE_LIGHT = re.compile(r'<img src="([^"]+)" alt="([^"]*)"')
PUBLIC = os.path.join(APP_ROOT, "churchit", "public")
# The Frappe Wiki space that syncs manual/: manual/<folder>/<page>.md is at <ONLINE_MANUAL>/<folder>/<page>.
ONLINE_MANUAL = "https://docs.churchit.app/manual"


def build_all(check: bool = False) -> list[str]:
	"""Write the workspace JSON of each manual folder, and return the files that changed.

	With *check*, nothing is written: the result names the files that are out of date.
	"""
	changed = []
	for folder in get_folders():
		path = get_workspace_path(folder)
		if write_workspace(path, get_blocks(folder), check):
			changed.append(os.path.relpath(path, APP_ROOT))
	return changed


def get_folders() -> list[str]:
	"""The folder of each manual: each folder of manual/ that has a README.md."""
	return sorted(os.path.dirname(path) for path in glob.glob(os.path.join(SOURCES, "*", "README.md")))


def get_workspace_path(folder: str) -> str:
	"""The workspace JSON that a manual folder builds."""
	return os.path.join(APP_ROOT, read_source(os.path.join(folder, "README.md"))[0]["workspace"])


def get_workspace_name(folder: str) -> str:
	"""The name of the workspace that a manual folder builds, such as "Manual: People"."""
	with open(get_workspace_path(folder), encoding="utf-8") as file:
		return json.load(file)["name"]


def read_source(path: str) -> tuple[dict, str]:
	"""The front matter (simple key: value lines) and the Markdown body of *path*."""
	with open(path, encoding="utf-8") as file:
		text = file.read()
	match = FRONT_MATTER.match(text)
	if not match:
		return {}, text
	keys = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
	return {key.strip(): value.strip() for key, value in keys.items()}, text[match.end() :]


def get_pages(folder: str) -> list[tuple[dict, str]]:
	"""The feature pages of a manual folder, in the order of their sidebar_position.

	Each page's front matter also gets its "route" in the online manual, such as people/person.
	"""
	pages = []
	for path in glob.glob(os.path.join(folder, "*.md")):
		front, body = read_source(path)
		if "sidebar_position" in front:
			route = f"{os.path.basename(folder)}/{os.path.basename(path)[:-3]}"
			pages.append(({**front, "route": route}, body))
	return sorted(pages, key=lambda page: (int(page[0]["sidebar_position"]), page[0]["title"]))


def get_blocks(folder: str) -> list[dict]:
	"""The editor blocks of a manual: its title and intro, then a level 2 heading and the body of each page.

	A page's own ## headings become level 3 headings, because its title is the level 2 heading.
	"""
	front, intro = read_source(os.path.join(folder, "README.md"))
	manual = os.path.basename(folder)
	chunks: list[tuple] = [("heading", 1, front["desk_title"])] if front.get("desk_title") else []
	chunks += get_chunks(intro, 0, manual)
	for page, body in get_pages(folder):
		chunks.append(("heading", 2, page.get("emoji", "") + page["title"]))
		chunks += get_chunks(body, 1, page["route"])
	return to_blocks(chunks, manual)


def get_chunks(markdown: str, shift: int, route: str = "") -> list[tuple]:
	"""Each block of *markdown* as (kind, *parts), with each callout kept whole.

	*route* is the page in the online manual, where the desk sends a reader for a diagram.
	"""
	chunks: list[tuple] = []
	text = DIAGRAM.sub(f"\n\n{DIAGRAM_MARK}\n\n", COMMENT.sub("", markdown))
	start = 0
	for match in CALLOUT.finditer(text):
		chunks += get_text_chunks(text[start : match.start()], shift, route)
		callout, title, body = match.groups()
		lines = [line.rstrip() for line in body.split("\n") if line.strip()]
		chunks.append(("callout", callout, title or CALLOUT_TITLES[callout], lines))
		start = match.end()
	return chunks + get_text_chunks(text[start:], shift, route)


def get_text_chunks(markdown: str, shift: int, route: str) -> list[tuple]:
	"""Each block of *markdown* that is not a callout, with headings moved down *shift* levels."""
	chunks: list[tuple] = []
	for chunk in re.split(r"\n\s*\n", markdown.strip()):
		lines = [line.rstrip() for line in chunk.strip("\n").split("\n") if line.strip()]
		if lines:
			chunks.append(get_chunk(lines, shift, route))
	return chunks


def get_chunk(lines: list[str], shift: int, route: str) -> tuple:
	"""One block: a heading, a picture, a table, a diagram or text."""
	heading = HEADING.match(lines[0]) if len(lines) == 1 else None
	if heading:
		return ("heading", len(heading.group(1)) + shift, heading.group(2).strip())
	if lines[0].startswith("<picture>"):
		return ("picture", " ".join(lines))
	if lines == [DIAGRAM_MARK]:
		return ("diagram", route)
	if all(line.startswith("|") for line in lines):
		return ("table", lines)
	return ("text", lines)


def to_blocks(chunks: list[tuple], manual: str) -> list[dict]:
	"""Paragraph blocks with ids that stay the same while their text does."""
	blocks: list[dict] = []
	seen: dict[str, int] = {}
	for kind, *parts in chunks:
		text = RENDERERS[kind](*parts, manual=manual)
		seen[text] = seen.get(text, 0) + 1
		digest = hashlib.sha1(f"{manual}:{text}:{seen[text]}".encode()).digest()
		block_id = base64.urlsafe_b64encode(digest).decode()[:10]
		blocks.append({"id": block_id, "type": "paragraph", "data": {"text": text, "col": 12}})
	return blocks


def render_heading(level: int, text: str, manual: str) -> str:
	return f'<span class="h{level}">{inline(text, manual)}</span>'


def render_text(lines: list[str], manual: str) -> str:
	return "<br>".join(inline(line, manual) for line in lines)


def render_callout(callout: str, title: str, lines: list[str], manual: str) -> str:
	"""The callout's title, then its lines. desk.css draws the block as a box."""
	text = f'<span class="manual-callout manual-callout-{callout}">{inline(title, manual)}</span>'
	return text + "".join("<br>" + inline(line, manual) for line in lines)


def render_picture(picture: str, manual: str) -> str:
	"""The light and the dark image of a <picture>. desk.css shows the one of the desk's theme."""
	dark, light = PICTURE_DARK.search(picture), PICTURE_LIGHT.search(picture)
	alt = light.group(2)
	return get_image(light.group(1), alt, "light", manual) + get_image(dark.group(1), alt, "dark", manual)


def get_image(source: str, alt: str, theme: str, manual: str) -> str:
	"""An <img> of the desk for an image in churchit/public, versioned by its content so no cache keeps an old one."""
	path = os.path.normpath(os.path.join(SOURCES, manual, source))
	if not path.startswith(PUBLIC + os.sep):
		raise ValueError(f"{source} in the {manual} manual is not in churchit/public, which the desk serves")
	with open(path, "rb") as file:
		version = hashlib.sha1(file.read()).hexdigest()[:8]
	url = "/assets/churchit/" + os.path.relpath(path, PUBLIC).replace(os.sep, "/")
	return f'<img class="manual-image manual-image-{theme}" src="{url}?v={version}" alt="{alt}">'


def render_table(lines: list[str], manual: str) -> str:
	"""A Markdown table as an HTML table. Its second line is the line under the header."""
	rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
	head = "".join(f"<th>{inline(cell, manual)}</th>" for cell in rows[0])
	body = "".join(
		"<tr>" + "".join(f"<td>{inline(cell, manual)}</td>" for cell in row) + "</tr>" for row in rows[2:]
	)
	return f'<table class="manual-table"><tr>{head}</tr>{body}</table>'


def render_diagram(route: str, manual: str) -> str:
	"""A link to the diagram in the online manual, because the desk cannot draw one."""
	return (
		f'<i><a href="{ONLINE_MANUAL}/{route}" target="_blank">See the diagram in the online manual</a></i>'
	)


RENDERERS = {
	"heading": render_heading,
	"text": render_text,
	"callout": render_callout,
	"picture": render_picture,
	"table": render_table,
	"diagram": render_diagram,
}


def inline(text: str, manual: str) -> str:
	"""HTML for one line of Markdown: code, links, bold and italic."""
	codes: list[str] = []

	def keep_code(match):
		codes.append(f"<code>{html.escape(match.group(1), quote=False)}</code>")
		return f"\x00{len(codes) - 1}\x00"

	text = html.escape(CODE.sub(keep_code, text), quote=False)
	text = LINK.sub(lambda match: get_link(match.group(1), match.group(2), manual), text)
	text = ITALIC.sub(r"<i>\1</i>", BOLD.sub(r"<b>\1</b>", text))
	return re.sub("\x00(\\d+)\x00", lambda match: codes[int(match.group(1))], text)


def get_link(text: str, target: str, manual: str) -> str:
	"""A link of the desk. A link to a page of another manual opens that manual. A link within the
	manual is plain text, because the desk shows the whole manual on one page."""
	path = target.split("#")[0]
	if not path.endswith(".md"):
		return f'<a href="{target}">{text}</a>'
	folder = os.path.normpath(os.path.join(SOURCES, manual, os.path.dirname(path)))
	if os.path.basename(folder) == manual:
		return text
	route = get_workspace_name(folder).lower().replace(" ", "-").replace(":", "%3A")
	return f'<a href="/desk/{route}">{text}</a>'


def write_workspace(path: str, blocks: list[dict], check: bool) -> bool:
	"""Put *blocks* in the workspace JSON at *path*, and say whether its content changed.

	The JSON keeps its own formatting. `modified` moves to now only when the content changes, because
	migrate skips a workspace whose `modified` is not newer than the copy on the site.
	"""
	with open(path, encoding="utf-8") as file:
		raw = file.read()
	doc = json.loads(raw)
	is_ascii = json.dumps(json.loads(doc["content"]), ensure_ascii=True) == doc["content"]
	is_file_ascii = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n" != raw
	content = json.dumps(blocks, ensure_ascii=is_ascii)
	if content == doc["content"]:
		return False
	if not check:
		doc["content"] = content
		doc["modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
		with open(path, "w", encoding="utf-8") as file:
			file.write(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=is_file_ascii) + "\n")
	return True
