# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Person Link search that also finds people by a phone number or an email address."""

import re

import frappe
from frappe import _
from frappe.desk.search import get_std_fields_list, relevance_sorter
from frappe.model.db_query import get_order_by
from frappe.utils.data import make_filter_tuple

from churchit.church_people.privacy import ANONYMIZED
from churchit.church_scope import CHURCH_FIELD, is_multi_church, session_church
from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, phone_digits

DECEASED_FIELD = "is_deceased"
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


@frappe.whitelist(methods=["GET"])
@frappe.validate_and_sanitize_search_inputs
def search_people(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict | list | None,
	as_dict: bool = False,
	reference_doctype: str | None = None,
) -> list:
	"""Person Link search: Frappe's own, plus the people holding *txt* as a phone or email. Reads only.

	hooks.py makes it the standard_queries for Person. It reads through `frappe.get_list` like Frappe does,
	so the user's permissions, the field's filters and the page length all apply as usual. People whose
	personal data was removed are left out, so no form links them.
	"""
	meta = frappe.get_meta("Person")
	if isinstance(filters, dict):
		filters = [make_filter_tuple("Person", key, value) for key, value in filters.items()]
	filters = [*(filters or []), ["Person", "first_name", "!=", ANONYMIZED]]

	or_filters = []
	if txt:
		or_filters = [["Person", field, "like", f"%{txt}%"] for field in get_searched_fields(meta)]
		if holders := get_contact_holders(txt):
			or_filters.append(["Person", "name", "in", holders])

	fields = get_std_fields_list(meta, searchfield or "name")
	if meta.show_title_field_in_link and meta.title_field:
		fields.insert(1, f"{meta.title_field} as label")
	is_multi = is_multi_church()
	if is_multi:
		fields.append(CHURCH_FIELD)
	fields.append(DECEASED_FIELD)

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
	home_church = session_church() if is_multi else None
	people = [describe_person(person, as_dict, is_multi, home_church) for person in people]
	return sorted(people, key=lambda person: relevance_sorter(person, txt, as_dict))


def describe_person(person, as_dict: bool, is_multi: bool, home_church: str | None):
	"""*person* with the church column swapped for the church's title, or dropped for the reader's own church,
	and the deceased column swapped for a "Deceased" description, so a picker marks who has died."""
	is_deceased = person[DECEASED_FIELD] if as_dict else person[-1]
	title = None
	if is_multi:
		church = person[CHURCH_FIELD] if as_dict else person[-2]
		if church and church != home_church:
			title = frappe.get_cached_value("Church", church, "church_name")

	if as_dict:
		# A frappe._dict, because Frappe's relevance_sorter reads `.name`.
		row = frappe._dict(person)
		row.pop(DECEASED_FIELD)
		if is_multi:
			row.pop(CHURCH_FIELD)
		if title:
			row[CHURCH_FIELD] = title
		if is_deceased:
			row[DECEASED_FIELD] = _("Deceased")
		return row

	row = person[: -2 if is_multi else -1]
	return (*row, *filter(None, (title, _("Deceased") if is_deceased else None)))


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
