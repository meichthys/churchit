# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rename the doctypes and the report that ERPNext also ships, so both apps fit on one site.

Frappe keeps one record per name, so ERPNext's Budget, Location and Open Work Orders would take
over Churchit's. This runs before the model sync, so the sync updates the renamed records rather
than adding empty ones beside them. Renaming moves the data, the links to it and the
customizations made on it.
"""

import json

import frappe

RENAMES = (
	("DocType", "Budget", "Church Budget", "Church Finances"),
	("DocType", "Location", "Church Location", "Church Operations"),
	("Report", "Open Work Orders", "Open Church Work Orders", "Church Operations"),
)

SAVED_FILTERS = (
	("Number Card", "document_type", "filters_json"),
	("Number Card", "document_type", "dynamic_filters_json"),
	("Dashboard Chart", "document_type", "filters_json"),
	("Dashboard Chart", "document_type", "dynamic_filters_json"),
	("List Filter", "reference_doctype", "filters"),
	("Kanban Board", "reference_doctype", "filters"),
)


def execute():
	rename_records(RENAMES)


def rename_records(renames: tuple[tuple[str, str, str, str], ...]):
	"""Rename each (doctype, old, new, module) of *renames* whose old name is still Churchit's record."""
	for doctype, old, new, module in renames:
		if frappe.db.get_value(doctype, old, "module") != module:
			continue
		frappe.rename_doc(doctype, old, new, force=True, show_alert=False)
		if doctype == "DocType":
			move_list_settings(old, new)
			move_saved_views(old, new)
			rename_customizations(old, new)


def move_list_settings(old: str, new: str):
	"""Keep each user's list columns, filters and sort, which rename_doc leaves under the old name.

	The saved settings also name the doctype and its table inside them, as `["name", "Budget"]`
	columns, the first item of each filter and a "`tabBudget`.`modified`" sort, so those move too.
	"""
	for user, data in frappe.db.sql("select `user`, `data` from `__UserSettings` where doctype=%s", old):
		settings = rename_doctype_in_settings(json.loads(data or "{}"), old, new)
		frappe.db.sql(
			"update `__UserSettings` set doctype=%s, data=%s where `user`=%s and doctype=%s",
			(new, json.dumps(settings), user, old),
		)
	if frappe.db.exists("List View Settings", old):
		frappe.rename_doc("List View Settings", old, new, force=True, show_alert=False)


def move_saved_views(old: str, new: str):
	"""Rename the doctype inside saved Report Builder reports, cards, charts, list filters and boards.

	rename_doc points them at the new doctype but leaves the old name in their saved columns,
	filters and sort, so they would fail with "DocType <old> not found".
	"""
	reports = frappe.get_all(
		"Report",
		filters={"ref_doctype": new, "report_type": "Report Builder", "json": ("is", "set")},
		fields=["name", "json"],
		as_list=True,
	)
	for name, data in reports:
		settings = rename_doctype_in_settings(json.loads(data), old, new)
		frappe.db.set_value("Report", name, "json", json.dumps(settings), update_modified=False)

	for doctype, link_field, field in SAVED_FILTERS:
		rows = frappe.get_all(
			doctype, filters={link_field: new, field: ("is", "set")}, fields=["name", field], as_list=True
		)
		for name, data in rows:
			filters = rename_doctype_in_filters(json.loads(data), old, new)
			frappe.db.set_value(doctype, name, field, json.dumps(filters), update_modified=False)


def rename_doctype_in_settings(value, old: str, new: str):
	"""Rename each string in *value* that names the doctype *old*."""
	if isinstance(value, dict):
		return {
			key: rename_doctype_in_filters(item, old, new)
			if key == "filters"
			else rename_doctype_in_settings(item, old, new)
			for key, item in value.items()
		}
	if isinstance(value, list):
		return [rename_doctype_in_settings(item, old, new) for item in value]
	if isinstance(value, str):
		return new if value == old else value.replace(f"`tab{old}`", f"`tab{new}`")
	return value


def rename_doctype_in_filters(filters, old: str, new: str):
	"""Rename the doctype of each [doctype, field, operator, value] filter in *filters*.

	Only the first item moves, so a filter on the Skill category keeps the value "Skill". Filters
	saved as {field: value} do not name the doctype.
	"""
	if not isinstance(filters, list):
		return filters
	return [
		[new, *condition[1:]]
		if isinstance(condition, list) and condition and condition[0] == old
		else condition
		for condition in filters
	]


def rename_customizations(old: str, new: str):
	"""Give custom fields and property setters names that start with the new doctype.

	rename_doc points them at the new doctype but keeps names such as "Location-main-field_order",
	which the same customization of ERPNext's Location would need.
	"""
	for doctype, field in (("Custom Field", "dt"), ("Property Setter", "doc_type")):
		for name in frappe.get_all(doctype, filters={field: new, "name": ("like", f"{old}-%")}, pluck="name"):
			frappe.rename_doc(doctype, name, new + name[len(old) :], force=True, show_alert=False)
