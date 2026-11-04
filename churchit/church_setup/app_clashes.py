# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Refuse to put Churchit and another app that ships a record of the same name on one site.

Frappe keeps one doctype, report, page or other standard record per name, so the app installed
last takes over the other app's record. Frappe Learning (the Function doctype) and Frappe Suite
(Email Address, Slide) clash today. The install hooks check; migrate does not, so an existing site
is left alone.
"""

import glob
import os

import frappe
from frappe import _

APP = "churchit"


def get_record_names(app: str) -> set[tuple[str, str]]:
	"""The (doctype, name) of each standard record *app* ships as `<module>/<type>/<name>/<name>.json`."""
	names = set()
	for module in frappe.get_module_list(app):
		folder = frappe.get_app_path(app, frappe.scrub(module))
		for path in glob.glob(os.path.join(glob.escape(folder), "*", "*", "*.json")):
			if os.path.basename(path) != f"{os.path.basename(os.path.dirname(path))}.json":
				continue
			record = frappe.get_file_json(path)
			if isinstance(record, dict) and record.get("doctype") and record.get("name"):
				names.add((record["doctype"], record["name"]))
	return names


def get_site_record_names(app: str) -> set[tuple[str, str]]:
	"""The (doctype, name) of each standard DocType and Report the site holds for *app*, as of its last migrate.

	Records a church made itself are left out: migrate never renames them.
	"""
	modules = ("in", frappe.get_module_list(app))
	standard = {
		"DocType": {"custom": 0, "module": modules},
		"Report": {"is_standard": "Yes", "module": modules},
	}
	return {
		(doctype, name)
		for doctype, filters in standard.items()
		for name in frappe.get_all(doctype, filters=filters, pluck="name")
	}


def refuse_clashing_app(app_name: str):
	"""before_app_install hook: refuse an app that ships a record with the name of a Churchit record.

	The site is checked as well as the code: until migrate renames a record, the site still holds
	it under its old name, which the other app's install would take over.
	"""
	if app_name == APP:
		return
	incoming = get_record_names(app_name)
	shared = sorted(incoming & get_record_names(APP))
	if shared:
		frappe.throw(
			_("{0} cannot be installed with Churchit, because both apps have these records: {1}").format(
				app_name, describe_records(shared)
			),
			frappe.ValidationError,
		)
	unmigrated = sorted(incoming & get_site_record_names(APP))
	if unmigrated:
		frappe.throw(
			_(
				"Migrate this site before you install {0}. The site still has these Churchit records: {1}"
			).format(app_name, describe_records(unmigrated)),
			frappe.ValidationError,
		)


def describe_records(records: list[tuple[str, str]]) -> str:
	return ", ".join(f"{_(doctype)} {name}" for doctype, name in records)


def refuse_clashing_installed_apps():
	"""before_install hook: refuse to install Churchit on a site that has a clashing app."""
	for app in frappe.get_installed_apps():
		refuse_clashing_app(app)
