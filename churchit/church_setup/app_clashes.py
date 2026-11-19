# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Refuse to put Churchit and another app that ships a record of the same name on one site.

Frappe keeps one doctype, report, page or other standard record per name, so the app installed
last takes over the other app's record. `app_names` says which names an app ships. Frappe
Learning (the Function doctype), Frappe Education (Room, Room Booking), Lending (Pledge), Frappe
Mail and Frappe Suite (Email Address, Push Subscription, Slide) clash today. The install hooks
check; migrate does not, so an existing site is left alone. `scripts/check_app_clashes.py` checks
every app of the Frappe organization on GitHub, also the apps that are not on this bench.
"""

import frappe
from frappe import _

from churchit.church_setup.app_names import ROUTE, ShippedName, get_shared_names, get_shipped_names

APP = "churchit"


def get_record_names(app: str) -> dict[tuple[str, str], ShippedName]:
	"""Each name *app* ships, keyed by (doctype, name without case)."""
	return get_shipped_names(frappe.get_app_path(app), frappe.get_module_list(app))


def get_site_record_names(app: str) -> dict[tuple[str, str], ShippedName]:
	"""The (doctype, name) of each standard DocType and Report the site holds for *app*, as of its last migrate.

	Records a church made itself are left out: migrate never renames them.
	"""
	modules = ("in", frappe.get_module_list(app))
	standard = {
		"DocType": {"custom": 0, "module": modules},
		"Report": {"is_standard": "Yes", "module": modules},
	}
	return {
		(doctype, name.casefold()): ShippedName(doctype, name, "")
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
	if app_name == "frappe":
		# Churchit replaces some of Frappe's own pages, such as /contact, on purpose.
		incoming = {key: name for key, name in incoming.items() if name.doctype != ROUTE}
	shared = [name for name, _other in get_shared_names(get_record_names(APP), incoming)]
	if shared:
		frappe.throw(
			_("{0} cannot be installed with Churchit, because both apps have these records: {1}").format(
				app_name, describe_records(shared)
			),
			frappe.ValidationError,
		)
	unmigrated = [name for name, _other in get_shared_names(get_site_record_names(APP), incoming)]
	if unmigrated:
		frappe.throw(
			_(
				"Migrate this site before you install {0}. The site still has these Churchit records: {1}"
			).format(app_name, describe_records(unmigrated)),
			frappe.ValidationError,
		)


def describe_records(records: list[ShippedName]) -> str:
	"""*records* as a list a person reads, such as "DocType Function, Route about"."""
	return ", ".join(f"{_(record.doctype)} {record.name}" for record in records)


def refuse_clashing_installed_apps():
	"""before_install hook: refuse to install Churchit on a site that has a clashing app."""
	for app in frappe.get_installed_apps():
		refuse_clashing_app(app)
