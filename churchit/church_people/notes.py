# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Person Notes: who may read and add each Note Category, and the notes on a person's timeline.

A category's role lists narrow the rights a user holds on Person Note, and a private category is read only by
the note's author. Frappe never restricts Administrator, so it reads every note; a System Manager follows the
categories like everyone else. Church scoping still comes from the church field and User Permissions.
"""

from datetime import datetime

import frappe
from frappe.utils import formatdate, get_fullname, get_url_to_form, now_datetime

from churchit.church_people.doctype.note_category.note_category import has_listed_role

# Rights that only read a note. Every other right changes it, so it needs the category's adders too.
READ_RIGHTS = ("select", "read", "report", "export", "print", "email")
# Pinned notes come first wherever a person's notes are listed.
NOTE_ORDER = "is_pinned desc, noted_on desc, creation desc"
TIMELINE_FIELDS = ["name", "category", "contact_method", "noted_on", "is_pinned", "note", "owner", "creation"]
CARD_TEMPLATE = "churchit/church_people/doctype/person_note/person_note_card.html"


def has_note_permission(doc, ptype: str = "read", user: str | None = None) -> bool:
	"""has_permission hook for Person Note: reading follows the category's readers, adding its adders.

	Changing, deleting or sharing a note needs both. Frappe reads any falsy return as a refusal.
	"""
	user = user or frappe.session.user
	if not doc.category:
		# Only a new note lacks one, and saving it refuses the blank category.
		return ptype == "create"
	category = frappe.get_cached_doc("Note Category", doc.category)
	if ptype == "create":
		return category.can_add(user)
	if not category.can_read(user, doc.owner):
		return False
	return ptype in READ_RIGHTS or category.can_add(user)


def note_query_conditions(user: str | None = None, doctype: str | None = None) -> str:
	"""permission_query_conditions hook for Person Note: the notes in the categories *user* may read."""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""
	readable, private = [], []
	for name in frappe.get_all("Note Category", pluck="name"):
		category = frappe.get_cached_doc("Note Category", name)
		if category.is_private:
			private.append(frappe.db.escape(name))
		elif has_listed_role(user, category.view_roles):
			readable.append(frappe.db.escape(name))
	conditions = [f"`tabPerson Note`.`category` in ({', '.join(readable)})"] if readable else []
	if private:
		conditions.append(
			f"(`tabPerson Note`.`category` in ({', '.join(private)})"
			f" and `tabPerson Note`.`owner` = {frappe.db.escape(user)})"
		)
	return f"({' or '.join(conditions) or '1 = 0'})"


def get_timeline_notes(doctype: str, docname: str) -> list[dict]:
	"""additional_timeline_content hook for Person: the person's notes the reader may read, as cards."""
	if not frappe.has_permission("Person Note"):
		return []
	notes = frappe.get_list(
		"Person Note", filters={"person": docname}, fields=TIMELINE_FIELDS, order_by=NOTE_ORDER
	)
	return [get_timeline_card(note) for note in notes]


def get_timeline_card(note: frappe._dict) -> dict:
	"""One note as a timeline card, placed on the day it records. A pinned note sorts as now, so it stays on top."""
	placed_at = now_datetime() if note.is_pinned else datetime.combine(note.noted_on, note.creation.time())
	context = {
		"author": get_fullname(note.owner),
		"date": formatdate(note.noted_on),
		"heading": " · ".join(filter(None, (note.category, note.contact_method))),
		"url": get_url_to_form("Person Note", note.name),
		"note": note.note,
	}
	return {
		"icon": "pin" if note.is_pinned else "notebook-pen",
		"is_card": True,
		"creation": placed_at,
		"content": frappe.render_template(CARD_TEMPLATE, context),
	}


@frappe.whitelist()
def get_alert_notes(person: str) -> list[dict]:
	"""The alert notes on *person* the caller may read, pinned first, for the top of the Person form."""
	frappe.has_permission("Person", doc=person, throw=True)
	if not frappe.has_permission("Person Note"):
		return []
	return frappe.get_list(
		"Person Note",
		filters={"person": person, "is_alert": 1},
		fields=["name", "category", "note"],
		order_by=NOTE_ORDER,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_categories_to_add(doctype, txt, searchfield, start, page_len, filters) -> list[list[str]]:
	"""Link search for a note's category: only the categories the caller may add a note in."""
	names = frappe.get_list(
		"Note Category", filters={"name": ("like", f"%{txt}%")}, pluck="name", order_by="name asc"
	)
	user = frappe.session.user
	addable = [name for name in names if frappe.get_cached_doc("Note Category", name).can_add(user)]
	return [[name] for name in addable[start : start + page_len]]
