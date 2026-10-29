# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The counts on a form's Connections, limited to the records the reader may see."""

import frappe
from frappe.desk import notifications


@frappe.whitelist()
@frappe.read_only()
def get_open_count(doctype: str, name: str | int, items: str | list[str] | None = None):
	"""Frappe's `get_open_count`, counting only the connected records the caller may read.

	Frappe counts with `get_all` and skips no doctype, so anyone who could open a person learned
	how many counseling cases, care requests or gifts point at them, in every church.
	"""
	links = frappe.get_meta(doctype).get_dashboard_data()
	if items is None:
		items = [item for group in links.transactions for item in group.get("items")]
	readable = [item for item in frappe.parse_json(items) if frappe.has_permission(item, "read")]

	counts = notifications.get_open_count(doctype, name, readable)
	for found in counts["count"]["external_links_found"] if counts["count"] else []:
		# A count over several child tables already came from get_list, with the names it found.
		if found["count"] and found["count"] != "?" and "names" not in found:
			found["count"] = count_readable(found["doctype"], name, links)
	return counts


def count_readable(link_doctype: str, name: str | int, links: dict) -> int | str:
	"""Records of *link_doctype* pointing at *name* that the caller may read, up to Frappe's 100."""
	fieldname = notifications.get_external_link_fieldname(link_doctype, links)
	filters = notifications.get_dynamic_link_filters(link_doctype, links, fieldname) or {}
	filters[fieldname] = name
	try:
		return len(
			frappe.get_list(
				link_doctype, filters=filters, limit=100, distinct=True, order_by=None, pluck="name"
			)
		)
	except Exception as e:
		if frappe.db.is_statement_timeout(e):
			return "?"
		raise
