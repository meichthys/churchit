# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The churchit manuals as Flow knowledge, so the Church Office agent answers how-to questions.

A long-queue job (churchit.ai.flow.sync_manual_knowledge) keeps the "Churchit Manual" knowledge base
equal to the Manual: <Module> workspaces, with one Text source per section. It runs only while AI is
on, on a Frappe with Flow, with an enabled embedding model: Flow sends each section to that model.
The manuals hold no church records.
"""

import html
import re

import frappe
from frappe.utils import get_url_to_workspace

from churchit.ai.switch import has_flow, is_ai_on
from churchit.manuals import get_blocks, get_manuals, read_blocks, strip_tags

KNOWLEDGE_BASE = "Churchit Manual"
SYNC_JOB = "churchit.ai.flow.sync_manual_knowledge"


def queue_sync() -> None:
	"""after_migrate, and Church AI Settings when AI is turned on: queue the manual sync once."""
	if is_ai_on() and has_flow() and has_embedding_model():
		frappe.enqueue(SYNC_JOB, queue="long", job_id=SYNC_JOB, deduplicate=True, enqueue_after_commit=True)


def has_embedding_model() -> bool:
	"""True when Flow Knowledge Settings names an enabled embedding model. Call it after has_flow()."""
	model = frappe.db.get_single_value("Flow Knowledge Settings", "embedding_model")
	return bool(model and frappe.db.get_value("Flow Model", model, "enabled"))


def get_manual_sections() -> list[dict]:
	"""Each section of the Manual: <Module> workspaces as {"title", "content"} in plain text.

	A section runs from one heading to the next; the text before the first heading is the manual's
	own. The title names the manual, the heading and the manual's desk page, because a knowledge
	search gives the model each passage with its title. A section with no text is left out.
	"""
	sections = []
	for manual in get_manuals():
		link = get_url_to_workspace(manual["name"], is_public=True)
		for heading, lines in split_sections(get_blocks(manual)):
			title = f"{manual['name']} > {heading} ({link})" if heading else f"{manual['name']} ({link})"
			if text := "\n".join(filter(None, lines)):
				sections.append({"title": title, "content": f"{title}\n\n{text}"})
	return sections


def split_sections(blocks: list[dict]) -> list[tuple[str | None, list[str]]]:
	"""A manual's blocks as (heading, lines of plain text), split at each heading."""
	sections: list[tuple[str | None, list[str]]] = [(None, [])]
	for kind, *parts in read_blocks(blocks):
		if kind == "heading":
			sections.append((parts[1], []))
		elif kind == "list":
			sections[-1][1].extend(f"- {to_text(item)}" for item in parts[1])
		else:
			sections[-1][1].append(to_text(parts[0]))
	return sections


def to_text(markup: str) -> str:
	"""The plain text of a block's HTML: a new line for each <br>, link text without the link.

	"<" and ">" stay escaped: Frappe's XSS filter strips tag-like text such as <your site> on save,
	and the sync matches each source by its saved text.
	"""
	text = html.unescape(strip_tags(re.sub(r"<br\s*/?>", "\n", markup))).replace("\xa0", " ").strip()
	return text.replace("<", "&lt;").replace(">", "&gt;")
