# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Refuse to put Churchit and another app with a doctype of the same name on one site.

Frappe keeps one doctype per name, so the app installed last takes over the other app's table and
forms. ERPNext (Budget, Location), Frappe Learning (Function) and Frappe Suite (Email Address,
Slide) clash today. The install hooks check; migrate does not, so an existing site is left alone.
"""

import os

import frappe
from frappe import _

APP = "churchit"


def get_doctype_names(app: str) -> set[str]:
	"""The names of the doctypes that *app* ships, read from its `<module>/doctype/<name>/<name>.json` files."""
	names = set()
	for module in frappe.get_module_list(app):
		folder = frappe.get_app_path(app, frappe.scrub(module), "doctype")
		if not os.path.isdir(folder):
			continue
		for doctype in os.listdir(folder):
			path = os.path.join(folder, doctype, f"{doctype}.json")
			if os.path.isfile(path):
				names.add(frappe.get_file_json(path)["name"])
	return names


def refuse_clashing_app(app_name: str):
	"""before_app_install hook: refuse an app that has a doctype with a Churchit doctype's name."""
	if app_name == APP:
		return
	shared = sorted(get_doctype_names(app_name) & get_doctype_names(APP))
	if shared:
		frappe.throw(
			_("{0} cannot be installed with Churchit, because both apps have these doctypes: {1}").format(
				app_name, ", ".join(shared)
			),
			frappe.ValidationError,
		)


def refuse_clashing_installed_apps():
	"""before_install hook: refuse to install Churchit on a site that has a clashing app."""
	for app in frappe.get_installed_apps():
		refuse_clashing_app(app)
