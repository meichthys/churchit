import re

import frappe


@frappe.whitelist(allow_guest=False)
def get_published_fields(doctype):
	"""Return fields of *doctype* that are published on the website.

	Scans published Web Pages with ``dynamic_template=1`` whose Jinja HTML
	references fields of *doctype* (detected by ``frappe.get_doc("DocType", …)``
	or ``frappe.get_list("DocType", …)`` calls followed by attribute access
	like ``variable.fieldname``).

	Returns a dict mapping fieldname → list of source Web Page titles, e.g.::

	    {"title": ["Missions"], "email": ["Missions"]}
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	meta = frappe.get_meta(doctype)
	known_fields = {f.fieldname for f in meta.fields if f.fieldname}

	result = {}  # fieldname → [source, …]

	web_pages = frappe.get_all(
		"Web Page",
		filters={"published": 1, "dynamic_template": 1},
		fields=["name", "title", "route", "main_section_html"],
	)
	# Pattern: frappe.get_doc("DocType", …) or frappe.get_list("DocType", …)
	dt_escaped = re.escape(doctype)
	ref_pattern = re.compile(
		rf"""frappe\.get_(?:doc|list)\(\s*["']{dt_escaped}["']"""
	)
	for wp in web_pages:
		html = wp.main_section_html or ""
		if not ref_pattern.search(html):
			continue
		# Find all .fieldname attribute accesses in the template
		source = {"title": wp.title or wp.name, "route": wp.route or wp.name}
		for fieldname in known_fields:
			# Match variable.fieldname (e.g. church.legal_name, missionary.email)
			if re.search(rf"\b\w+\.{re.escape(fieldname)}\b", html):
				result.setdefault(fieldname, []).append(source)

	return result


@frappe.whitelist(allow_guest=False)
def get_church_doctypes():
	"""Return non-child doctypes belonging to church app modules."""
	frappe.only_for(["Church User", "Church Manager", "System Manager"])
	return frappe.get_all(
		"DocType",
		filters=[["module", "like", "Church%"], ["istable", "=", 0]],
		fields=["name"],
		order_by="name asc",
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

	or_filters = []
	if txt:
		or_filters.append(["name", "like", f"%{txt}%"])
		if title_field and title_field != "name":
			or_filters.append([title_field, "like", f"%{txt}%"])

	results = frappe.get_all(
		doctype,
		or_filters=or_filters,
		fields=["name"] + ([title_field] if title_field and title_field != "name" else []),
		order_by="name asc",
		limit=20,
	)

	out = []
	for r in results:
		label = (r.get(title_field) or r.name) if title_field and title_field != "name" else r.name
		out.append({"name": r.name, "label": label})
	return out
