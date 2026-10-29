# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Person Link search that also finds people by a phone number or an email address."""

import re

import frappe
from frappe.desk.search import get_std_fields_list, relevance_sorter
from frappe.model.db_query import get_order_by

from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, phone_digits

# Fewer digits than this are too common to search for, the same rule as the Check-In Station.
MIN_SEARCH_DIGITS = 4
# The field types Frappe's own Link search looks in.
SEARCHED_FIELDTYPES = (
	"Autocomplete",
	"Data",
	"Link",
	"Long Text",
	"Read Only",
	"Select",
	"Small Text",
	"Text",
	"Text Editor",
)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_people(doctype, txt, searchfield, start, page_len, filters, as_dict=False, reference_doctype=None):
	"""standard_queries for Person: Frappe's own Link search, plus the people holding *txt* as a phone or email.

	It reads through `frappe.get_list` like Frappe does, so the user's permissions, the field's filters and the
	page length all apply as usual.
	"""
	meta = frappe.get_meta("Person")
	or_filters = []
	if txt:
		or_filters = [["Person", field, "like", f"%{txt}%"] for field in get_searched_fields(meta)]
		if holders := get_contact_holders(txt):
			or_filters.append(["Person", "name", "in", holders])

	fields = get_std_fields_list(meta, searchfield or "name")
	if meta.show_title_field_in_link and meta.title_field:
		fields.insert(1, f"{meta.title_field} as label")

	people = frappe.get_list(
		"Person",
		filters=filters,
		or_filters=or_filters,
		fields=fields,
		offset=start,
		limit=page_len,
		order_by=f"idx desc, {get_order_by('Person', meta)}",
		reference_doctype=reference_doctype,
		as_list=not as_dict,
		strict=False,
	)
	return sorted(people, key=lambda person: relevance_sorter(person, txt, as_dict))


def get_searched_fields(meta) -> list[str]:
	"""The fields Frappe's Link search looks in: the name, the title and the search fields."""
	fields = dict.fromkeys(["name", meta.title_field, *meta.get_search_fields()])
	return [
		field
		for field in fields
		if field == "name"
		or (meta.get_field(field) and meta.get_field(field).fieldtype in SEARCHED_FIELDTYPES)
	]


def get_contact_holders(txt: str) -> list[str]:
	"""People with an email address containing *txt*, or a phone number containing its digits.

	An email needs its @, and a phone at least four digits and no letters, so typing a name looks up neither.
	"""
	if "@" in txt:
		child_doctype, condition = EMAIL_DOCTYPE, {"email_address": ("like", f"%{txt}%")}
	elif len(digits := phone_digits(txt)) >= MIN_SEARCH_DIGITS and not re.search(r"[^\W\d_]", txt):
		child_doctype, condition = PHONE_DOCTYPE, {"digits": ("like", f"%{digits}%")}
	else:
		return []
	return frappe.get_all(
		child_doctype, filters={"parenttype": "Person", **condition}, pluck="parent", distinct=True
	)
