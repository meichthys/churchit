# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Where a person's data sits outside their own record: every record and child row that names them.

`linked_records` finds them from the site's field definitions, the way Frappe's rename does: each Link field to
Person in DocField, Custom Field and Property Setter metadata (`get_link_fields`), and each Dynamic Link that
holds a Person (`get_dynamic_link_map`). A custom field a church adds is found with no change here. The person's
own child rows are part of their record, so they are not listed.

Merge and anonymize read it. Retention and export read it too.
"""

from dataclasses import dataclass

import frappe
from frappe.model.dynamic_links import get_dynamic_link_map
from frappe.model.rename_doc import get_link_fields

PERSON = "Person"

# Child tables that list a person at most once on each record, by the field that names them.
ROSTERS = {
	"Family Members": "member",
	"Function Attendance": "person",
	"Function Sign-Up Attendee": "person",
	"Group Member": "person",
	"Meeting Attendee": "person",
	"Ministry Team Position Person": "person",
	"Missionary Person": "person",
}


@dataclass(frozen=True)
class LinkedRecord:
	"""A record, or a child row of the record *parent* of *parenttype*, whose *fieldname* names the person."""

	doctype: str
	name: str
	fieldname: str
	parenttype: str | None = None
	parent: str | None = None


def linked_records(person: str) -> list[LinkedRecord]:
	"""Every record and child row that names *person* in a Link or Dynamic Link field."""
	return get_records_naming(PERSON, person)


def get_records_naming(doctype: str, name: str) -> list[LinkedRecord]:
	"""Every record and child row that names the *doctype* record *name* in a Link or Dynamic Link field."""
	found = []
	for parent, fieldname in sorted({(field.parent, field.fieldname) for field in get_link_fields(doctype)}):
		found += find_rows(parent, fieldname, {fieldname: name})
	for df in get_dynamic_link_map().get(doctype, []):
		found += find_rows(df.parent, df.fieldname, {df.options: doctype, df.fieldname: name})
	return found


def find_rows(doctype: str, fieldname: str, filters: dict) -> list[LinkedRecord]:
	"""The rows of *doctype* matching *filters*, as records named through *fieldname*; none for a Single."""
	meta = frappe.get_meta(doctype)
	if meta.issingle or meta.is_virtual:
		return []
	columns = ["name", "parenttype", "parent"] if meta.istable else ["name"]
	# church-scope: finds what names one record, for merge and anonymize; shows nobody anything
	rows = frappe.get_all(doctype, filters=filters, fields=columns, order_by="creation asc")
	return [
		LinkedRecord(doctype, row.name, fieldname, row.get("parenttype"), row.get("parent")) for row in rows
	]
