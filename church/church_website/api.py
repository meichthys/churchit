import os
import re

import frappe


@frappe.whitelist(allow_guest=False)
def get_published_fields(doctype):
	"""Return fields of *doctype* that are published on the website.

	Two scan paths:

	1. Published Web Pages with ``dynamic_template=1`` whose Jinja HTML
	   references fields of *doctype* (detected by ``frappe.get_doc("DocType", …)``
	   or ``frappe.get_list("DocType", …)`` calls followed by attribute access
	   like ``variable.fieldname``).
	2. ``www/*.py`` files (public web routes) that pull *doctype* records via
	   ``frappe.get_all/get_list("DocType", …, fields=[…])`` — the explicit
	   field list there is what gets sent to the client.

	Returns a dict mapping fieldname → list of sources, e.g.::

	    {"title": [{"title": "Missions", "route": "missions"}], ...}
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	meta = frappe.get_meta(doctype)
	known_fields = {f.fieldname for f in meta.fields if f.fieldname}

	result = {}  # fieldname → [source, …]
	_scan_web_pages(doctype, known_fields, result)
	_scan_www_python(doctype, known_fields, result)
	return result


def _scan_web_pages(doctype, known_fields, result):
	web_pages = frappe.get_all(
		"Web Page",
		filters={"published": 1, "dynamic_template": 1},
		fields=["name", "title", "route", "main_section_html"],
	)
	dt_escaped = re.escape(doctype)
	ref_pattern = re.compile(rf"""frappe\.get_(?:doc|list)\(\s*["']{dt_escaped}["']""")
	for wp in web_pages:
		html = wp.main_section_html or ""
		if not ref_pattern.search(html):
			continue
		source = {"title": wp.title or wp.name, "route": wp.route or wp.name}
		for fieldname in known_fields:
			if re.search(rf"\b\w+\.{re.escape(fieldname)}\b", html):
				result.setdefault(fieldname, []).append(source)


def _scan_www_python(doctype, known_fields, result):
	"""In any installed app's www/*.py files that mention *doctype*, treat every
	quoted field name as a published field. Filename = route."""
	doctype_re = re.compile(rf"""['"]{re.escape(doctype)}['"]""")
	for app in frappe.get_installed_apps():
		www_dir = os.path.join(frappe.get_app_path(app), "www")
		if not os.path.isdir(www_dir):
			continue
		for fname in os.listdir(www_dir):
			if not fname.endswith(".py") or fname.startswith("__"):
				continue
			code = open(os.path.join(www_dir, fname), encoding="utf-8").read()
			if not doctype_re.search(code):
				continue
			used = {f for f in known_fields if re.search(rf"""['"]{re.escape(f)}['"]""", code)}
			if not used:
				continue
			route = os.path.splitext(fname)[0]
			source = {"title": route.replace("_", " ").title(), "route": route}
			for fieldname in used:
				result.setdefault(fieldname, []).append(source)


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
