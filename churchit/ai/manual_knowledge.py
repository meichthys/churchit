# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The churchit manuals as Flow knowledge, so the Church Office agent answers how-to questions.

A long-queue job (churchit.ai.flow.sync_manual_knowledge) keeps the "Churchit Manual" knowledge base
equal to the manuals in manual/, with one Text source per page. It runs only while AI is
on, on a Frappe with Flow, with an enabled embedding model: Flow sends each section to that model.
The manuals hold no church records.
"""

import os

import frappe
from frappe.utils import get_url_to_workspace

from churchit.ai.switch import has_flow, is_ai_on
from churchit.manual_sources import COMMENT, get_folders, get_pages, get_workspace_name, read_source

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
	"""Each page of the manuals in manual/ as {"title", "content"}, the content in Markdown.

	A manual's README is the manual's own section. The title names the manual, the page and the
	manual's desk page, because a knowledge search gives the model each passage with its title. A page
	with no text is left out.
	"""
	sections = []
	for folder in get_folders():
		name = get_workspace_name(folder)
		link = get_url_to_workspace(name, is_public=True)
		pages = [(None, read_source(os.path.join(folder, "README.md"))[1])]
		pages += [(page["title"], body) for page, body in get_pages(folder)]
		for heading, body in pages:
			title = f"{name} > {heading} ({link})" if heading else f"{name} ({link})"
			if text := to_text(body):
				sections.append({"title": title, "content": f"{title}\n\n{text}"})
	return sections


def to_text(markdown: str) -> str:
	"""A page's Markdown without its comments.

	"<" and ">" are escaped: Frappe's XSS filter strips tag-like text such as <your site> on save,
	and the sync matches each source by its saved text.
	"""
	return COMMENT.sub("", markdown).strip().replace("<", "&lt;").replace(">", "&gt;")
