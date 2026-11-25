# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Which fields the website shows, behind the desk's published-field badge."""

import ast
import re
from collections import defaultdict
from pathlib import Path

import frappe

from churchit.church_people.member_access import PERSONAL_DETAILS_EDITABLE, PERSONAL_DETAILS_READ_ONLY
from churchit.church_website.pages import (
	get_switched_off_pages,
	is_page_off,
	is_public_website_on,
	sends_guests_to_login,
)

# Code that reads records on every page (navbar brand, footer, PWA manifest).
# No route owns it, so it is scanned as one "every page" source.
SITE_WIDE_MODULES = ("context.py", "footer.py", "pwa.py")

# Who reaches a source: anyone, only a signed-in member, or only whoever holds an emailed link.
PUBLIC = "public"
MEMBERS = "members"
LINK_HOLDERS = "link holders"

SITE_WIDE_SOURCE = {"title": "Every page (navbar, footer, app name)", "route": "", "access": PUBLIC}

# Pages that show a Function's schedule, where a row shows the title of the record it links to: the
# digital bulletin and the member app's Serving page.
SCHEDULE_SOURCES = (
	{"title": "Bulletins", "route": "bulletins", "access": MEMBERS},
	{"title": "Member Portal: Serving", "route": "portal/ministry-team", "access": MEMBERS},
)

# The member app's My Details page: portal.account reads the Person fields of PERSONAL_DETAILS_EDITABLE
# and PERSONAL_DETAILS_READ_ONLY by names held in a variable, which the scan cannot see.
PERSONAL_DETAILS_SOURCE = {
	"title": "Member Portal: Account",
	"route": "portal/personal-details",
	"access": MEMBERS,
}

# The member app's Memorize page: portal.faith.get_practice sends word_mistakes through
# Bible Memory Item.load_word_mistakes, which the scan cannot follow.
MEMORIZE_SOURCE = {
	"title": "Member Portal: Memorize",
	"route": "portal/memorize",
	"access": MEMBERS,
}

# The member app's endpoints (churchit/portal), each module by the app page it serves at /portal/<route>.
# A module not listed is badged at /portal itself.
PORTAL_MODULE_PAGES = {
	"household": "household",
	"account": "personal-details",
	"events": "function-sign-up",
	"serving": "ministry-team",
	"groups": "groups",
	"directory": "directory",
	"care": "community-prayer-requests",
	"faith": "memorize",
	"giving": "pledge",
}

# A page that sends every guest to the login screen is the portal, not the public site.
# A redirect gated on anything else (giving allows anonymous gifts) still serves guests.
GUEST_REDIRECT = re.compile(
	r"""if\s+frappe\.session\.user\s*==\s*["']Guest["']\s*:\s*\n[^\n]*redirect_location\s*=\s*["']/login"""
)

READ_CALL = (
	r"frappe\.(?:get_doc|get_cached_doc|get_list|get_all|get_cached_value"
	r"|db\.get_value|db\.get_list|db\.get_all|db\.get_single_value)\(\s*"
)
DOCTYPE_READ = re.compile(READ_CALL + r"""["'](?P<doctype>[^"']+)["']""")
QUOTED_NAME = re.compile(r"""['"](\w+)['"]""")

# A guest-callable function: from its decorator to the next top-level definition.
GUEST_FUNCTION = re.compile(
	r"@frappe\.whitelist\([^)]*allow_guest=True[^)]*\)[^\S\n]*\n(?:@[^\n]+\n)*"
	r"def (?P<name>\w+)(?P<body>.*?)(?=\n(?:@|def |class )|\Z)",
	re.S,
)
# Imports worth following: this app's own code, and the framework page a www/ page delegates to.
IMPORTED_NAMES = re.compile(r"^from\s+((?:churchit|frappe\.www)[\w.]*)\s+import\s+(\([^)]*\)|.+)$", re.M)
INCLUDED_TEMPLATE = re.compile(r"""\{%-?\s*include\s+["'](churchit/[^"']+)["']""")

# Attribute reads on these never name a field of a record.
NON_RECORD_BASES = ("context", "frappe", "self")
ATTRIBUTE_READ = re.compile("".join(rf"(?<!{base})" for base in NON_RECORD_BASES) + r"\.(\w+)")
LAYOUT_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "Heading", "HTML", "Button"}

# How far to follow a page into the helpers, templates and jinja methods it calls.
HELPER_DEPTH = 3

# The scan reads the app's source and every published page and form; it changes only on a deploy or an edit of one.
CACHE_KEY = "churchit_published_field_entries"


def published_field_map(use_cache=False):
	"""Every field the website shows, as ``{doctype: {fieldname: [source, …]}}``.

	Each source is a ``{"title", "route", "access"}`` dict naming the page, form
	or API that shows the field, so the desk badge can say where it appears and
	whether anyone sees it or only a signed-in member. With *use_cache* the scan
	is read from the cache, which `clear_published_field_cache` empties.
	"""
	published = defaultdict(lambda: defaultdict(list))
	for source, doctype, fieldname in published_entries(use_cache):
		published[doctype][fieldname].append(source)
	return {doctype: dict(fields) for doctype, fields in published.items()}


def get_reachable_field_map() -> dict:
	"""`published_field_map` as visitors reach it now, for the desk badge.

	A page that is off shows no field. While the public website is off, a page that sends guests to the
	login page shows its fields only to signed-in members.
	"""
	published = published_field_map(use_cache=True)
	routes = {
		source["route"] for fields in published.values() for sources in fields.values() for source in sources
	}
	off_pages = get_switched_off_pages()
	off_routes = {
		route for route in routes if any(is_page_off(page, off_pages) for page in page_routes(route))
	}
	closed_routes = set()
	if not is_public_website_on():
		closed_routes = {
			route for route in routes - off_routes if any(map(sends_guests_to_login, page_routes(route)))
		}

	reachable = {}
	for doctype, fields in published.items():
		for fieldname, sources in fields.items():
			shown = [
				{**source, "access": MEMBERS}
				if source["access"] == PUBLIC and source["route"] in closed_routes
				else source
				for source in sources
				if source["route"] not in off_routes
			]
			if shown:
				reachable.setdefault(doctype, {})[fieldname] = shown
	return reachable


def page_routes(route: str) -> set[str]:
	"""The routes a scanned source may be served at.

	The scan names a www/ page after its python file with dashes, so it calls /sermon_presentation
	sermon-presentation and /podcast.xml podcast.
	"""
	return {route, route.replace("-", "_"), f"{route}.xml"} - {"", ".xml"}


def published_entries(use_cache=False):
	"""Yield ``(source, doctype, fieldname)`` for everything the website shows."""
	entries = frappe.cache.get_value(CACHE_KEY) if use_cache else None
	if entries is None:
		entries = list(scanned_entries())
		if use_cache:
			frappe.cache.set_value(CACHE_KEY, entries)
	yield from entries
	# Schedule rows change with every Function, so they are read on each call.
	yield from schedule_item_entries(set(frappe.get_all("DocType", pluck="name")))


def clear_published_field_cache(doc=None, method=None):
	"""Forget the scan. Runs after a migrate and when a Web Page or Web Form changes or is deleted."""
	frappe.cache.delete_value(CACHE_KEY)


def scanned_entries():
	"""Yield the entries read from source code, Web Pages and Web Forms."""
	doctypes = set(frappe.get_all("DocType", pluck="name"))
	for source, code in code_sources():
		code = with_helper_code(code)
		attributes = attribute_reads(code)
		for doctype in {match["doctype"] for match in DOCTYPE_READ.finditer(code)} & doctypes:
			for fieldname in fields_used_in(doctype, code, attributes):
				yield source, doctype, fieldname
	yield from web_form_entries()
	for fieldname in (*PERSONAL_DETAILS_EDITABLE, *PERSONAL_DETAILS_READ_ONLY):
		yield PERSONAL_DETAILS_SOURCE, "Person", fieldname
	yield MEMORIZE_SOURCE, "Bible Memory Item", "word_mistakes"


def schedule_item_entries(doctypes):
	"""Yield the title field of each doctype that a Function's schedule links to, for the pages that show it.

	`function.get_schedule_rows` reads the title through a doctype held in a variable, which the scan cannot see.
	"""
	linked = frappe.get_all(
		"Function Schedule", filters={"item": ("is", "set")}, pluck="item_type", distinct=True
	)
	for doctype in set(linked) & doctypes:
		if title_field := frappe.get_meta(doctype).title_field:
			for source in SCHEDULE_SOURCES:
				yield source, doctype, title_field


def code_sources():
	"""Yield ``(source, code)`` for everything that renders on the public website."""
	yield from web_page_sources()
	yield from www_sources()
	yield from guest_api_sources()
	yield from portal_api_sources()
	website_dir = Path(frappe.get_app_path("churchit")) / "church_website"
	yield SITE_WIDE_SOURCE, "\n".join((website_dir / name).read_text() for name in SITE_WIDE_MODULES)


def web_page_sources():
	"""Each published Web Page whose content is a template reading records."""
	for page in frappe.get_all(
		"Web Page",
		filters={"published": 1, "dynamic_template": 1},
		fields=["name", "title", "route", "main_section_html", "members_only"],
	):
		access = MEMBERS if page.members_only else PUBLIC
		source = {"title": page.title or page.name, "route": page.route or page.name, "access": access}
		yield source, page.main_section_html or ""


def www_sources():
	"""Each ``www/`` page of this app: its python, its template, or both.

	Only this app's pages are scanned. The framework's own www/ pages (print
	view, password reset) are not the church website, and the churchit page
	that shadows one pulls the framework code in as a helper anyway.
	"""
	for route, paths in www_routes(Path(frappe.get_app_path("churchit")) / "www").items():
		code = "\n".join(path.read_text() for path in paths)
		access = MEMBERS if GUEST_REDIRECT.search(code) else PUBLIC
		yield {"title": route.replace("-", " ").title(), "route": route, "access": access}, code


def www_routes(www_dir):
	"""Route → the files that render it, for every page under *www_dir*.

	Frappe serves ``www/<folder>/<page>.py`` at /<folder>/<page>, a folder's
	``index`` at the folder itself, and reads underscores and dashes alike, so
	``find_a_group.py`` and ``find-a-group.html`` are one page, not two.
	"""
	routes = defaultdict(list)
	for entry in sorted(www_dir.rglob("*")):
		if entry.suffix not in (".py", ".html") or entry.name.startswith("__"):
			continue
		route = entry.relative_to(www_dir).with_suffix("").as_posix().replace("_", "-")
		routes[route.removesuffix("/index")].append(entry)
	return routes


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
			source = {
				"title": f"Public API: {frappe.unscrub(name)}",
				"route": f"api/method/{module}.{name}",
				"access": PUBLIC,
			}
			yield source, match.group("body")


def portal_api_sources():
	"""Each module of the member app's API (churchit/portal): what the app shows to signed-in members.

	The app reads records only through these endpoints, so they stand for its pages. They take no guest.
	"""
	portal_dir = Path(frappe.get_app_path("churchit")) / "portal"
	for entry in sorted(portal_dir.glob("*.py")):
		if entry.name.startswith(("test_", "__")):
			continue
		page = PORTAL_MODULE_PAGES.get(entry.stem)
		source = {
			"title": f"Member Portal: {frappe.unscrub(entry.stem)}",
			"route": f"portal/{page}" if page else "portal",
			"access": MEMBERS,
		}
		yield source, entry.read_text()


def web_form_entries():
	"""Yield ``(source, doctype, fieldname)`` for the fields each published Web Form shows."""
	forms = frappe.get_all(
		"Web Form",
		filters={"published": 1},
		fields=["name", "title", "route", "doc_type", "login_required", "key_required"],
	)
	shown = web_form_fieldnames([form.name for form in forms])
	for form in forms:
		source = {
			"title": (form.title or form.name).strip(),
			"route": form.route or form.name,
			"access": web_form_access(form),
		}
		for fieldname in shown[form.name] & field_names(form.doc_type):
			yield source, form.doc_type, fieldname


def web_form_access(form):
	"""Who reaches a Web Form: a signed-in member, the holder of a key from a Web Form Request, or anyone.

	A key-only form shows the one record its Web Form Request names, to whoever has the link.
	"""
	if form.login_required:
		return MEMBERS
	return LINK_HOLDERS if form.key_required else PUBLIC


def web_form_fieldnames(names):
	"""Form name to the fields that Web Form puts on the page, from its inputs and its list columns."""
	shown = defaultdict(set)
	for row in frappe.get_all(
		"Web Form Field", filters={"parent": ["in", names]}, fields=["parent", "fieldname", "fieldtype"]
	):
		if row.fieldtype not in LAYOUT_FIELDTYPES:
			shown[row.parent].add(row.fieldname)
	for row in frappe.get_all(
		"Web Form List Column", filters={"parent": ["in", names]}, fields=["parent", "fieldname"]
	):
		shown[row.parent].add(row.fieldname)
	return shown


def with_helper_code(code, depth=HELPER_DEPTH, seen=None):
	"""*code* with the churchit helpers it reaches folded in.

	A page rarely reads a field itself: it calls a helper, includes a template
	or uses a jinja method. Constants are substituted where they are used, so a
	field list held in one counts as read by the call it is passed to.
	"""
	if depth <= 0:
		return code
	seen = set() if seen is None else seen
	reached = []
	for target in helper_targets(code):
		if target in seen:
			continue
		seen.add(target)
		source = helper_source(target)
		if not source:
			continue
		name = target.rpartition(".")[2]
		constant = constant_value(name, source)
		if constant:
			code = code.replace(name, constant)
		else:
			reached.append(with_helper_code(source, depth - 1, seen))
	return "\n".join([code, *reached])


def helper_targets(code):
	"""Dotted paths and template paths of the churchit helpers *code* reaches."""
	for match in IMPORTED_NAMES.finditer(code):
		for imported in match.group(2).strip("()").split(","):
			name = imported.strip().split(" ")[0]
			if name:
				yield f"{match.group(1)}.{name}"
	for method in frappe.get_hooks("jinja").get("methods", []):
		if method.startswith("churchit.") and re.search(rf"\b{method.rpartition('.')[2]}\s*\(", code):
			yield method
	yield from INCLUDED_TEMPLATE.findall(code)


def helper_source(target):
	"""The source behind a dotted module path or an ``<app>/`` template path.

	The app name leads both spellings, so it resolves against that app's
	directory. Both come from source files this app ships, so no user input
	reaches the filesystem call.
	"""
	if "/" in target:
		app, _, relative = target.partition("/")
		template = Path(frappe.get_app_path(app)) / relative
		return template.read_text() if template.is_file() else None

	app, *parts = target.split(".")
	app_dir = Path(frappe.get_app_path(app))
	module = app_dir.joinpath(*parts).with_suffix(".py")
	if module.is_file():
		return module.read_text()
	module = app_dir.joinpath(*parts[:-1]).with_suffix(".py")
	return definition_source(module.read_text(), parts[-1]) if module.is_file() else None


def definition_source(source, name):
	"""The ``def``, ``class`` or assignment of *name* in *source*."""
	try:
		tree = ast.parse(source)
	except SyntaxError:
		return None
	for node in tree.body:
		assigned = any(isinstance(t, ast.Name) and t.id == name for t in getattr(node, "targets", []))
		if assigned or getattr(node, "name", None) == name:
			return ast.get_source_segment(source, node)
	return None


def constant_value(name, source):
	"""The literal a ``NAME = [...]`` definition holds, or None for anything else."""
	match = re.match(rf"{re.escape(name)}\s*=\s*(.+)", source, re.S)
	return match.group(1) if match else None


def fields_used_in(doctype, code, attributes=None):
	"""Fields of *doctype* that *code* reads, or none when it never fetches the doctype.

	A field counts when it is quoted inside the call that fetches the doctype,
	or read as ``record.fieldname`` anywhere in the code. Pass *attributes*,
	from ``attribute_reads``, to scan a long source once for many doctypes.
	"""
	calls = read_call_arguments(doctype, code)
	if not calls:
		return set()
	if attributes is None:
		attributes = attribute_reads(code)
	quoted = set(QUOTED_NAME.findall(" ".join(calls)))
	return field_names(doctype) & (quoted | attributes)


def attribute_reads(code):
	"""Every ``record.fieldname`` attribute *code* reads, by attribute name."""
	return set(ATTRIBUTE_READ.findall(code))


def field_names(doctype):
	"""Every fieldname of *doctype*."""
	return {field.fieldname for field in frappe.get_meta(doctype).fields if field.fieldname}


def read_call_arguments(doctype, code):
	"""The argument text of every call in *code* that fetches *doctype*."""
	pattern = READ_CALL + rf"""["']{re.escape(doctype)}["']"""
	return [call_arguments(code, match.end()) for match in re.finditer(pattern, code)]


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
