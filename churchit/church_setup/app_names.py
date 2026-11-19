# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The names an app ships, which two apps on one site cannot share.

Frappe keeps one record of each (doctype, name), and MariaDB compares names without case, so an app
installed later takes over a record of the same name however it is spelt. The names are:

- each standard record in the app's module folders, at any depth (doctypes, reports, pages,
  workspaces, web forms, kanban boards, notifications and the rest),
- each fixture record, and each custom field and property setter in a module's `custom` folder,
- each route of its `www` folder, web forms and web pages, because one app's page hides the other's.

Uses only the standard library, so `scripts/check_app_clashes.py` reads apps that are not on a bench.
"""

import json
import os
from typing import NamedTuple

ROUTE = "Route"
PAGE_EXTENSIONS = (".html", ".md")
SKIPPED_EXTENSIONS = (".py", ".pyc", ".css", ".scss")


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
	"""Each name the app in folder *package* ships, keyed by (doctype, name without case)."""
	names = {}

	def add(doctype: str, name: str, path: str):
		names[(doctype, str(name).casefold())] = ShippedName(
			doctype, str(name), os.path.relpath(path, package)
		)

	for module in modules if modules is not None else get_modules(package):
		for path, record in read_json_files(os.path.join(package, scrub(module))):
			if not isinstance(record, dict):
				continue
			if record.get("doctype") and record.get("name"):
				add(record["doctype"], record["name"], path)
				if record["doctype"] in ("Web Form", "Web Page") and record.get("route"):
					add(ROUTE, record["route"].strip("/"), path)
			for field in record.get("custom_fields") or []:
				add("Custom Field", f"{field['dt']}-{field['fieldname']}", path)
			for setter in record.get("property_setters") or []:
				add("Property Setter", get_property_setter_name(setter), path)
	for path, records in read_json_files(os.path.join(package, "fixtures"), recursive=False):
		for record in records if isinstance(records, list) else []:
			if isinstance(record, dict) and record.get("doctype") and record.get("name"):
				add(record["doctype"], record["name"], path)
	for route, path in get_www_routes(os.path.join(package, "www")):
		add(ROUTE, route, path)
	return names


def read_json_files(folder: str, recursive: bool = True):
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


def get_www_routes(folder: str):
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


def get_property_setter_name(setter: dict) -> str:
	"""The name Frappe gives *setter*: doctype, field (or main) and property."""
	field = setter.get("field_name") or setter.get("row_name") or "main"
	return setter.get("name") or f"{setter['doc_type']}-{field}-{setter['property']}"


def get_shared_names(
	names: dict[tuple[str, str], ShippedName], others: dict[tuple[str, str], ShippedName]
) -> list[tuple[ShippedName, ShippedName]]:
	"""The (name, other name) pairs that *names* and *others* both ship, in order."""
	return [(names[key], others[key]) for key in sorted(names.keys() & others.keys())]


def scrub(text: str) -> str:
	"""*text* as Frappe names its folder."""
	return text.replace(" ", "_").replace("-", "_").lower()
