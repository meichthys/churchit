# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Start each doctype's own naming counter after its highest existing name.

Doctypes used to share one global counter through ``format:`` autonames.
Without seeding, the new per-prefix counters would restart at 1 and collide.
"""

import re

import frappe
from frappe.model.naming import NamingSeries

SERIES_AUTONAME = re.compile(r"^(?P<prefix>[\w\- ]+)\.#+$")


def execute():
	for doctype, autoname in get_series_doctypes():
		seed_counter(doctype, autoname)


def get_series_doctypes():
	"""Yield (doctype, autoname) for churchit doctypes named by a prefixed counter."""
	modules = frappe.get_module_list("churchit")
	rows = frappe.get_all("DocType", filters={"module": ["in", modules]}, fields=["name", "autoname"])
	for row in rows:
		if row.autoname and SERIES_AUTONAME.match(row.autoname):
			yield row.name, row.autoname


def seed_counter(doctype, autoname):
	prefix = SERIES_AUTONAME.match(autoname)["prefix"]
	names = frappe.get_all(doctype, filters={"name": ["like", f"{prefix}%"]}, pluck="name")
	highest = max((int(n[len(prefix) :]) for n in names if n[len(prefix) :].isdigit()), default=0)
	series = NamingSeries(autoname)
	if highest > series.get_current_value():
		series.update_counter(highest)
