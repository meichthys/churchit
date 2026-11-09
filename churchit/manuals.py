# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Manual: <Module> workspaces, churchit's user documentation, read from the app's files.

docs/build_docs.py renders them as the churchit.app documentation page and churchit.ai.manual_knowledge
gives them to Flow, both through read_blocks. Standard library only: the docs build runs without Frappe.
"""

import glob
import json
import os
import re
from collections.abc import Iterator

FILES = os.path.join(
	os.path.dirname(os.path.abspath(__file__)), "*", "workspace", "manual:_*", "manual:_*.json"
)


def get_manuals() -> list[dict]:
	"""Each manual's workspace JSON, in file order."""
	manuals = []
	for path in sorted(glob.glob(FILES)):
		with open(path) as file:
			manuals.append(json.load(file))
	return manuals


def get_blocks(manual: dict) -> list[dict]:
	"""The editor blocks of a manual's workspace."""
	return json.loads(manual.get("content") or "[]")


def read_blocks(blocks: list[dict]) -> Iterator[tuple]:
	"""Each block as ("heading", level, text), ("list", is_ordered, items) or ("paragraph", html).

	The manual's own title (a paragraph styled h1) and blocks of other types are left out. A paragraph
	styled h2 is a heading of level 2. A heading's text has no tags.
	"""
	for block in blocks:
		kind, data = block.get("type"), block.get("data", {})
		text = data.get("text", "")
		if kind == "header":
			yield "heading", int(data.get("level", 2)), strip_tags(text)
		elif kind == "list":
			yield "list", data.get("style") == "ordered", data.get("items", [])
		elif kind != "paragraph" or 'class="h1"' in text:
			continue
		elif 'class="h2"' in text:
			yield "heading", 2, strip_tags(text)
		else:
			yield "paragraph", text


def strip_tags(html: str) -> str:
	return re.sub(r"<[^>]+>", "", html or "").replace("&nbsp;", " ").strip()
