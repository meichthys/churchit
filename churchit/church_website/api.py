import re
from pathlib import Path

import frappe

# Code that reads records on every page (navbar brand, footer, PWA manifest).
# No route owns it, so it is scanned as one "every page" source.
SITE_WIDE_MODULES = ("context.py", "footer.py", "pwa.py")
SITE_WIDE_SOURCE = {"title": "Every page (navbar, footer, app name)", "route": ""}

DOCTYPE_CALL = r"""frappe\.(?:get_doc|get_cached_doc|get_list|get_all|db\.get_value)\(\s*["']{doctype}["']"""

# A guest-callable function: from its decorator to the next top-level definition.
GUEST_FUNCTION = re.compile(
	r"@frappe\.whitelist\([^)]*allow_guest=True[^)]*\)\s*\ndef (?P<name>\w+)(?P<body>.*?)(?=\n(?:@|def |class )|\Z)",
	re.S,
)


@frappe.whitelist(allow_guest=False)
def get_published_fields(doctype):
	"""Return fields of *doctype* that are published on the website.

	Scans every public source — published dynamic Web Pages, ``www/`` routes
	(the ``.py`` and its sibling ``.html``), guest-callable API functions and
	the site-wide modules — for calls that fetch *doctype*
	(``frappe.get_doc/get_list/get_all/db.get_value``, or ``get_church()`` for Church). A field counts as published when it is
	quoted inside such a call or read as ``variable.fieldname`` in that source.

	Returns a dict mapping fieldname → list of sources, e.g.::

	    {"title": [{"title": "Missions", "route": "missions"}], ...}
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	known_fields = {f.fieldname for f in frappe.get_meta(doctype).fields if f.fieldname}

	result = {}  # fieldname → [source, …]
	for source, code in public_sources():
		for fieldname in fields_used_in(doctype, known_fields, code):
			result.setdefault(fieldname, []).append(source)
	return result


def public_sources():
	"""Yield ``(source, code)`` for everything that renders on the public website."""
	for page in frappe.get_all(
		"Web Page",
		filters={"published": 1, "dynamic_template": 1},
		fields=["name", "title", "route", "main_section_html"],
	):
		yield (
			{"title": page.title or page.name, "route": page.route or page.name},
			page.main_section_html or "",
		)
	yield from www_sources()
	yield from guest_api_sources()
	website_dir = Path(frappe.get_app_path("churchit")) / "church_website"
	yield SITE_WIDE_SOURCE, "\n".join((website_dir / name).read_text() for name in SITE_WIDE_MODULES)


def www_sources():
	"""Each ``www/<route>.py`` of every installed app, with its ``.html`` when there is one.

	Path inputs (app names from ``frappe.get_installed_apps``; filenames from
	directory listing) are entirely server-derived — no user input reaches the
	filesystem call.
	"""
	for app in frappe.get_installed_apps():
		www_dir = Path(frappe.get_app_path(app)) / "www"
		if not www_dir.is_dir():
			continue
		for entry in www_dir.glob("*.py"):
			if entry.name.startswith("__"):
				continue
			code = entry.read_text()
			template = entry.with_suffix(".html")
			if template.exists():
				code += "\n" + template.read_text()
			route = entry.stem
			yield {"title": route.replace("_", " ").title(), "route": route}, code


def guest_api_sources():
	"""Each ``allow_guest`` function outside ``www/``: data a public page fetches over the API."""
	app_dir = Path(frappe.get_app_path("churchit"))
	for entry in app_dir.rglob("*.py"):
		if "www" in entry.parts or entry.name.startswith("test_"):
			continue
		code = entry.read_text()
		if "allow_guest=True" not in code:
			continue
		module = ".".join(("churchit", *entry.relative_to(app_dir).with_suffix("").parts))
		for match in GUEST_FUNCTION.finditer(code):
			name = match.group("name")
			source = {"title": f"Public API: {frappe.unscrub(name)}", "route": f"api/method/{module}.{name}"}
			yield source, match.group("body")


def fields_used_in(doctype, known_fields, code):
	"""Fields of *doctype* that *code* reads, or none when it never fetches the doctype."""
	calls = doctype_call_arguments(doctype, code)
	if not calls:
		return set()
	quoted = " ".join(calls)
	return {
		fieldname
		for fieldname in known_fields
		if re.search(rf"\b\w+\.{re.escape(fieldname)}\b", code)
		or re.search(rf"""['"]{re.escape(fieldname)}['"]""", quoted)
	}


def doctype_call_arguments(doctype, code):
	"""The argument text of every call in *code* that fetches *doctype*."""
	pattern = DOCTYPE_CALL.format(doctype=re.escape(doctype))
	if doctype == "Church":
		pattern += r"|\bget_church\("
	calls = [call_arguments(code, match.end()) for match in re.finditer(pattern, code)]
	if doctype == "Church" and "get_church_address(" in code:
		calls.append('"address"')  # the helper reads Church.address
	return calls


def call_arguments(code, start):
	"""Text from *start* up to the close of the enclosing call, respecting nested brackets."""
	depth = 0
	for index in range(start, len(code)):
		if code[index] in "([{":
			depth += 1
		elif code[index] in ")]}":
			if depth == 0:
				return code[start:index]
			depth -= 1
	return code[start:]


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
def get_published_web_page(url):
	"""The published Web Page a navbar/footer link points at, or None.

	Only site-relative links can name a Web Page; www/ pages and external links
	have nothing to un-publish.
	"""
	frappe.only_for(["Church Manager", "System Manager"])
	if not url or not url.startswith("/"):
		return None
	route = url.lstrip("/").split("?")[0].split("#")[0]
	if not route:
		return None
	return frappe.db.get_value(
		"Web Page", {"route": route, "published": 1}, ["name", "title", "route"], as_dict=True
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
