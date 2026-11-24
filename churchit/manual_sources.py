# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Markdown sources of the manuals in manual/, and the Manual workspaces built from them.

Each folder of manual/ is one manual: a README.md with the intro, and one Markdown file for each
feature. Frappe Wiki's GitHub Sync reads the same folder, so the files use plain Markdown with front
matter, the wiki's callouts (:::note to :::) and relative links between pages. The README names the
workspace JSON that the folder builds. docs/build_manuals.py writes the
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
	"""The feature pages of a manual folder, in the order of their sidebar_position."""
	pages = [read_source(path) for path in glob.glob(os.path.join(folder, "*.md"))]
	pages = [page for page in pages if "sidebar_position" in page[0]]
	return sorted(pages, key=lambda page: (int(page[0]["sidebar_position"]), page[0]["title"]))


def get_blocks(folder: str) -> list[dict]:
	"""The editor blocks of a manual: its title and intro, then a level 2 heading and the body of each page.

	A page's own ## headings become level 3 headings, because its title is the level 2 heading.
	"""
	front, intro = read_source(os.path.join(folder, "README.md"))
	chunks: list[tuple] = [("heading", 1, front["desk_title"])] if front.get("desk_title") else []
	chunks += get_chunks(intro, 0)
	for page, body in get_pages(folder):
		chunks.append(("heading", 2, page.get("emoji", "") + page["title"]))
		chunks += get_chunks(body, 1)
	return to_blocks(chunks, os.path.basename(folder))


def get_chunks(markdown: str, shift: int) -> list[tuple]:
	"""Each block of *markdown*, with each callout as ("callout", type, title, lines) and kept whole."""
	chunks: list[tuple] = []
	text = COMMENT.sub("", markdown)
	start = 0
	for match in CALLOUT.finditer(text):
		chunks += get_text_chunks(text[start : match.start()], shift)
		callout, title, body = match.groups()
		lines = [line.rstrip() for line in body.split("\n") if line.strip()]
		chunks.append(("callout", callout, title or CALLOUT_TITLES[callout], lines))
		start = match.end()
	return chunks + get_text_chunks(text[start:], shift)


def get_text_chunks(markdown: str, shift: int) -> list[tuple]:
	"""Each block of *markdown* as ("heading", level, text) or ("text", lines), with headings moved down *shift* levels."""
	chunks: list[tuple] = []
	for chunk in re.split(r"\n\s*\n", markdown.strip()):
		lines = [line.rstrip() for line in chunk.strip("\n").split("\n") if line.strip()]
		heading = HEADING.match(lines[0]) if len(lines) == 1 else None
		if heading:
			chunks.append(("heading", len(heading.group(1)) + shift, heading.group(2).strip()))
		elif lines:
			chunks.append(("text", lines))
	return chunks


def to_blocks(chunks: list[tuple], manual: str) -> list[dict]:
	"""Paragraph blocks with ids that stay the same while their text does.

	A callout is one block led by its title, which desk.css draws as a box.
	"""
	blocks: list[dict] = []
	seen: dict[str, int] = {}
	for kind, *parts in chunks:
		if kind == "heading":
			text = f'<span class="h{parts[0]}">{inline(parts[1], manual)}</span>'
		elif kind == "callout":
			callout, title, lines = parts
			text = f'<span class="manual-callout manual-callout-{callout}">{inline(title, manual)}</span>'
			text += "".join("<br>" + inline(line, manual) for line in lines)
		else:
			text = "<br>".join(inline(line, manual) for line in parts[0])
		seen[text] = seen.get(text, 0) + 1
		digest = hashlib.sha1(f"{manual}:{text}:{seen[text]}".encode()).digest()
		block_id = base64.urlsafe_b64encode(digest).decode()[:10]
		blocks.append({"id": block_id, "type": "paragraph", "data": {"text": text, "col": 12}})
	return blocks


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
