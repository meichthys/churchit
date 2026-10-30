# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rename the doctypes and the report that ERPNext also ships, so both apps fit on one site.

Frappe keeps one record per name, so ERPNext's Budget, Location and Open Work Orders would take
over Churchit's. This runs before the model sync, so the sync updates the renamed records rather
than adding empty ones beside them. Renaming moves the data, the links to it and the
customizations made on it.
"""

import frappe

RENAMES = (
	("DocType", "Budget", "Church Budget", "Church Finances"),
	("DocType", "Location", "Church Location", "Church Operations"),
	("Report", "Open Work Orders", "Open Church Work Orders", "Church Operations"),
)


def execute():
	for doctype, old, new, module in RENAMES:
		if frappe.db.get_value(doctype, old, "module") != module:
			continue
		frappe.rename_doc(doctype, old, new, force=True, show_alert=False)
		if doctype == "DocType":
			move_list_settings(old, new)
			rename_customizations(old, new)


def move_list_settings(old: str, new: str):
	"""Keep each user's list columns, filters and sort, which rename_doc leaves under the old name.

	The saved settings also name the doctype and its table inside them, as `["name", "Budget"]`
	columns and a "`tabBudget`.`modified`" sort, so those move too.
	"""
	frappe.db.sql(
		"""update `__UserSettings`
		set doctype=%s, data=replace(replace(data, %s, %s), %s, %s)
		where doctype=%s""",
		(new, f'"{old}"', f'"{new}"', f"`tab{old}`", f"`tab{new}`", old),
	)
	if frappe.db.exists("List View Settings", old):
		frappe.rename_doc("List View Settings", old, new, force=True, show_alert=False)


def rename_customizations(old: str, new: str):
	"""Give custom fields and property setters names that start with the new doctype.

	rename_doc points them at the new doctype but keeps names such as "Location-main-field_order",
	which the same customization of ERPNext's Location would need.
	"""
	for doctype, field in (("Custom Field", "dt"), ("Property Setter", "doc_type")):
		for name in frappe.get_all(doctype, filters={field: new, "name": ("like", f"{old}-%")}, pluck="name"):
			frappe.rename_doc(doctype, name, new + name[len(old) :], force=True, show_alert=False)
