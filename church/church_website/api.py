import frappe


@frappe.whitelist(allow_guest=False)
def get_church_doctypes():
	"""Return non-child doctypes belonging to church app modules."""
	return frappe.get_all(
		"DocType",
		filters=[["module", "like", "Church%"], ["istable", "=", 0]],
		fields=["name"],
		order_by="name asc",
		ignore_permissions=True,
	)


@frappe.whitelist(allow_guest=False)
def search_church_recipient(doctype, txt):
	"""Search records of the given church doctype, returning name and display label."""
	allowed = frappe.get_all(
		"DocType",
		filters=[["module", "like", "Church%"], ["istable", "=", 0]],
		fields=["name"],
		ignore_permissions=True,
		pluck="name",
	)
	if doctype not in allowed:
		frappe.throw("Not allowed", frappe.PermissionError)

	meta = frappe.get_meta(doctype)
	title_field = meta.title_field or None

	results = frappe.get_all(
		doctype,
		filters=[["name", "like", f"%{txt}%"]] if txt else [],
		or_filters=([[title_field, "like", f"%{txt}%"]] if txt and title_field and title_field != "name" else []),
		fields=["name"] + ([title_field] if title_field and title_field != "name" else []),
		order_by="name asc",
		limit=20,
		ignore_permissions=True,
	)

	out = []
	for r in results:
		label = (r.get(title_field) or r.name) if title_field and title_field != "name" else r.name
		out.append({"name": r.name, "label": label})
	return out
