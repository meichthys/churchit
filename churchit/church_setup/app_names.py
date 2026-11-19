# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The names an app ships, which two apps on one site cannot share.

Frappe keeps one record of each (doctype, name), and MariaDB compares names without case or accents,
so an app installed later takes over a record of the same name however it is spelt. The names are:

- each standard record in the app's module folders, at any depth (doctypes, reports, pages,
  workspaces, web forms, kanban boards, notifications and the rest),
- each fixture record, and each custom field and property setter in a module's `custom` folder,
- each route of its `www` folder, web forms, web pages and `website_route_rules`, and the routes in
  INSTALL_ROUTES, because one app's page hides the other's.

A record that an app makes in code, such as a Notification or an Email Template from `after_install`,
is not seen, except the routes in INSTALL_ROUTES.

Uses only the standard library, so `scripts/check_app_clashes.py` reads apps that are not on a bench.
"""

import ast
import json
import os
import unicodedata
from collections.abc import Iterator
from typing import NamedTuple

ROUTE = "Route"
PAGE_EXTENSIONS = (".html", ".md")
SKIPPED_EXTENSIONS = (".py", ".pyc", ".css", ".scss")

# The routes of the Web Pages that an app makes when it installs, by app package. Churchit's come from
# `patches/after_install.WEB_PAGES` and `ai/policy.PAGE_NAME`, which test_app_clashes compares.
INSTALL_ROUTES = {
	"churchit": ("home", "beliefs", "missions", "sermons", "ministries", "how-we-use-ai"),
}


class ShippedName(NamedTuple):
	"""One record an app ships, and the file it comes from."""

	doctype: str
	name: str
	path: str


def get_modules(package: str) -> list[str]:
	"""The module names in *package*'s modules.txt."""
	with open(os.path.join(package, "modules.txt")) as file:
		return [line.strip() for line in file if line.strip() and not line.startswith("#")]


def get_shipped_names(package: str, modules: list[str] | None = None) -> dict[tuple[str, str], ShippedName]:
	"""Each name the app in folder *package* ships, keyed by (doctype, name as MariaDB compares it)."""
	names = {}

	def add(doctype: str, name: str, path: str):
		names[(doctype, get_key(name))] = ShippedName(doctype, str(name), os.path.relpath(path, package))

	for module in modules if modules is not None else get_modules(package):
		for path, record in read_json_files(os.path.join(package, scrub(module))):
			for doctype, name in get_record_names(record):
				add(doctype, name, path)
	for path, records in read_json_files(os.path.join(package, "fixtures"), recursive=False):
		for record in records if isinstance(records, list) else []:
			for doctype, name in get_record_names(record):
				add(doctype, name, path)
	for route, path in get_www_routes(os.path.join(package, "www")):
		add(ROUTE, route, path)
	for route in get_route_rules(os.path.join(package, "hooks.py")):
		add(ROUTE, route, os.path.join(package, "hooks.py"))
	for route in INSTALL_ROUTES.get(os.path.basename(os.path.normpath(package)), ()):
		add(ROUTE, route, os.path.join(package, "patches"))
	return names


def get_record_names(record) -> Iterator[tuple[str, str]]:
	"""Yield (doctype, name) of *record*, its route, and the custom fields and property setters it holds."""
	if not isinstance(record, dict):
		return
	if record.get("doctype") and record.get("name"):
		yield record["doctype"], record["name"]
		if record["doctype"] in ("Web Form", "Web Page") and record.get("route"):
			yield ROUTE, record["route"].strip("/")
	for field in record.get("custom_fields") or []:
		if isinstance(field, dict) and field.get("dt") and field.get("fieldname"):
			yield "Custom Field", f"{field['dt']}-{field['fieldname']}"
	for setter in record.get("property_setters") or []:
		if isinstance(setter, dict) and (setter.get("name") or setter.get("doc_type")):
			yield "Property Setter", get_property_setter_name(setter)


def read_json_files(folder: str, recursive: bool = True) -> Iterator[tuple[str, object]]:
	"""Yield (path, content) of each JSON file under *folder* that parses."""
	for folder_path, folders, files in os.walk(folder):
		if not recursive:
			folders.clear()
		folders[:] = sorted(name for name in folders if name not in ("node_modules", "__pycache__"))
		for filename in sorted(files):
			if not filename.endswith(".json"):
				continue
			path = os.path.join(folder_path, filename)
			try:
				with open(path) as file:
					yield path, json.load(file)
			except (OSError, ValueError):
				continue


def get_www_routes(folder: str) -> Iterator[tuple[str, str]]:
	"""Yield (route, path) of each page and file the `www` *folder* serves."""
	for folder_path, folders, files in os.walk(folder):
		folders[:] = sorted(name for name in folders if name != "__pycache__")
		for filename in sorted(files):
			base, extension = os.path.splitext(filename)
			if extension in SKIPPED_EXTENSIONS or filename.startswith(("_", ".")):
				continue
			route = os.path.relpath(os.path.join(folder_path, filename), folder)
			if extension in PAGE_EXTENSIONS:
				route = os.path.join(os.path.dirname(route), base)
				if base == "index":
					route = os.path.dirname(route)
			if route:
				yield route.replace(os.sep, "/"), os.path.join(folder_path, filename)


def get_route_rules(hooks: str) -> Iterator[str]:
	"""Yield the fixed start of each `website_route_rules` route in the *hooks* file, such as "sermon"."""
	try:
		with open(hooks) as file:
			tree = ast.parse(file.read())
	except (OSError, SyntaxError, ValueError):
		return
	for node in tree.body:
		if isinstance(node, ast.Assign) and any(
			isinstance(target, ast.Name) and target.id == "website_route_rules" for target in node.targets
		):
			for element in node.value.elts if isinstance(node.value, ast.List) else []:
				try:
					rule = ast.literal_eval(element)
				except ValueError:
					continue  # a route built in code, such as Frappe Learning's
				route = rule.get("from_route", "") if isinstance(rule, dict) else ""
				if route := route.split("<")[0].strip("/"):
					yield route


def get_property_setter_name(setter: dict) -> str:
	"""The name Frappe gives *setter*: doctype, field (or main) and property."""
	field = setter.get("field_name") or setter.get("row_name") or "main"
	return setter.get("name") or f"{setter.get('doc_type')}-{field}-{setter.get('property')}"


def get_shared_names(
	names: dict[tuple[str, str], ShippedName], others: dict[tuple[str, str], ShippedName]
) -> list[tuple[ShippedName, ShippedName]]:
	"""The (name, other name) pairs that *names* and *others* both ship, in order."""
	return [(names[key], others[key]) for key in sorted(names.keys() & others.keys())]


def get_key(name: str) -> str:
	"""*name* without case or accents, as MariaDB's utf8mb4_unicode_ci compares it."""
	decomposed = unicodedata.normalize("NFKD", str(name))
	return "".join(letter for letter in decomposed if not unicodedata.combining(letter)).casefold()


def scrub(text: str) -> str:
	"""*text* as Frappe names its folder."""
	return text.replace(" ", "_").replace("-", "_").lower()
