# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Member app endpoints for Bible memory and bulletins."""

from urllib.parse import quote

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import formatdate

from churchit.church_scope import church_query_filters
from churchit.church_study.doctype.bible_memory_item.bible_memory_item import (
	get_translation_choices,
)
from churchit.portal.access import require_page, require_person
from churchit.scripture import get_passage_text, get_readable_translations, is_readable

PREVIEW_LENGTH = 160
PDF_METHOD = "/api/method/churchit.church_communications.doctype.bulletin.bulletin.download_pdf"


@frappe.whitelist(methods=["GET"])
def get_memory_list() -> dict:
	"""The member's own memory passages, the translations to add from, and the default. Reads only."""
	require_person()
	require_page("memorize")

	items = frappe.get_list(
		"Bible Memory Item",
		filters={"user": frappe.session.user},
		fields=[
			"name",
			"bible_reference",
			"translation",
			"progress",
			"memorized",
			"memorized_on",
			"times_memorized",
			"assigned_by",
			"group",
		],
		order_by="memorized asc, modified desc",
	)
	choices = get_translation_choices()

	return {
		"items": [describe_item(item) for item in items],
		"translations": choices["names"],
		"translation_titles": {row["name"]: row["translation"] for row in get_readable_translations()},
		"default_translation": choices["default"],
	}


def describe_item(item: dict) -> dict:
	"""One passage of the list with the fields the page shows, and a short preview when its text is ready."""
	group = item.group
	return {
		"name": item.name,
		"bible_reference": item.bible_reference,
		"translation": item.translation,
		"progress": item.progress or 0,
		"memorized": bool(item.memorized),
		"memorized_on": formatdate(item.memorized_on) if item.memorized_on else None,
		"times_memorized": item.times_memorized or 0,
		"assigned_by_name": get_user_name(item.assigned_by),
		"group": group,
		"group_name": frappe.db.get_value("Group", group, "group_name") if group else None,
		"preview": get_preview(item.bible_reference, item.translation),
	}


def get_user_name(user: str | None) -> str | None:
	"""The full name of a user, who is a manager that assigned a passage."""
	return user and (frappe.db.get_value("User", user, "full_name") or user)


def get_preview(reference: str, translation: str) -> str | None:
	"""The start of the passage, only when its translation is ready: a preview never starts a download."""
	status = frappe.get_cached_value("Bible Translation", translation, "status")
	if status != "Ready" or not is_readable(translation):
		return None
	return get_passage_text(reference, translation, PREVIEW_LENGTH)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60, user_based=True)
def add_memory_item(reference: str, translation: str) -> dict:
	"""Add a passage to the member's own memory list. Changes data.

	Only the reference and the translation come from the browser; the item controller checks both.
	"""
	require_person()
	require_page("memorize")

	item = frappe.get_doc(
		{
			"doctype": "Bible Memory Item",
			"user": frappe.session.user,
			"bible_reference": reference,
			"translation": translation,
		}
	).insert()

	return {"name": item.name, "bible_reference": item.bible_reference}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60, user_based=True)
def remove_memory_item(item: str) -> dict:
	"""Remove a passage, assigned or not, from the member's own list. Changes data."""
	require_person()
	require_page("memorize")

	frappe.has_permission("Bible Memory Item", "delete", doc=item, throw=True)
	require_own_item(item)
	frappe.delete_doc("Bible Memory Item", item)

	return {"name": item}


@frappe.whitelist(methods=["GET"])
def get_practice(item: str) -> dict:
	"""The passage text and progress of one of the member's own items, for a practice session. Reads only.

	The first reading of a translation that has no text yet downloads it, so this can be slow once.
	"""
	require_person()
	require_page("memorize")

	frappe.has_permission("Bible Memory Item", "read", doc=item, throw=True)
	doc = require_own_item(item)
	if not is_readable(doc.translation):
		frappe.throw(_("{0} has no text to memorize from yet.").format(doc.translation))

	return {
		"name": doc.name,
		"bible_reference": doc.bible_reference,
		"translation": doc.translation,
		"text": get_passage_text(doc.bible_reference, doc.translation),
		"progress": doc.progress or 0,
		"memorized": bool(doc.memorized),
		"times_memorized": doc.times_memorized or 0,
		"word_mistakes": doc.load_word_mistakes(),
	}


def require_own_item(item: str):
	"""The stored item, when it is the session user's. A manager's read access does not make it theirs."""
	doc = frappe.get_doc("Bible Memory Item", item)
	if doc.user != frappe.session.user:
		frappe.throw(
			_("This memory item belongs to another member. Pick one from your own list."),
			frappe.PermissionError,
		)
	return doc


@frappe.whitelist(methods=["GET"])
def get_bulletins() -> dict:
	"""Published bulletins of the churches the member reads, newest first. Reads only."""
	require_person()
	require_page("bulletins")

	return {
		"items": [
			{
				"name": bulletin.name,
				"title": bulletin.function_name,
				"date": bulletin.function_date and str(bulletin.function_date),
				"date_display": bulletin.function_date and formatdate(bulletin.function_date),
				"digital_url": f"/bulletins?name={quote(bulletin.name)}",
				"pdf_url": f"{PDF_METHOD}?name={quote(bulletin.name)}",
			}
			for bulletin in get_published_bulletins()
		]
	}


def get_published_bulletins():
	"""Published bulletins of the churches the member reads, newest function first.

	The member's own scope decides, not ``?church=``, so another church's bulletins never list.
	"""
	return frappe.get_all(
		"Bulletin",
		filters={"publish": 1, **church_query_filters({})},
		fields=["name", "function_name", "function_date"],
		order_by="function_date desc",
	)
