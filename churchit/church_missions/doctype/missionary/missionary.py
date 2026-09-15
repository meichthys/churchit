# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, add_years, getdate, today

from churchit.contacts import validate_contact_tables

# Maps each Missionary Support Frequency to the function that advances a date by
# one period. Keyed off the frequency record names seeded in
# churchit.patches.after_install._create_missionary_support_frequencies.
FREQUENCY_STEP = {
	"Weekly": lambda d: add_days(d, 7),
	"Bi-Weekly": lambda d: add_days(d, 14),
	"Monthly": lambda d: add_months(d, 1),
	"Bi-Monthly": lambda d: add_months(d, 2),
	"Quarterly": lambda d: add_months(d, 3),
	"Yearly": lambda d: add_years(d, 1),
}

# Safety cap so a misconfigured start date can never spin forever.
MAX_EXPENSES_PER_RUN = 1000


class Missionary(Document):
	def validate(self):
		validate_contact_tables(self)

		if self.auto_create_expenses:
			if not self.support_amount or self.support_amount <= 0:
				frappe.throw("A positive Support Amount is required to auto-create expenses.")
			if self.support_frequency not in FREQUENCY_STEP:
				frappe.throw(
					f"Support Frequency '{self.support_frequency}' is not supported for "
					"auto-creating expenses."
				)


@frappe.whitelist(methods=["GET"])
def get_map_markers() -> list[dict]:
	"""Missionaries with a Location set, for the Missionary Map workspace block."""
	missionaries = frappe.get_list(
		"Missionary",
		filters={"geolocation": ["is", "set"]},
		fields=["name", "title", "photo", "country", "geolocation"],
	)
	return _build_markers(missionaries, include_name=True)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_public_map_markers() -> dict:
	"""Published, non-sensitive missionaries with a Location set, for the public Missions map.

	Also reports how many otherwise-mappable missionaries were hidden for being sensitive,
	so the page can note that some locations are intentionally not shown.
	"""
	missionaries = frappe.get_list(
		"Missionary",
		filters={"geolocation": ["is", "set"], "publish": 1, "sensitive": 0},
		fields=["title", "photo", "country", "geolocation"],
		ignore_permissions=True,
	)
	hidden_count = frappe.db.count("Missionary", {"geolocation": ["is", "set"], "publish": 1, "sensitive": 1})
	return {"markers": _build_markers(missionaries), "hidden_count": hidden_count}


def _build_markers(missionaries, include_name=False) -> list[dict]:
	"""Marker dicts (title, photo, country, latitude, longitude) for missionaries with a Point geolocation."""
	markers = []
	for missionary in missionaries:
		coordinates = _get_point_coordinates(missionary.geolocation)
		if not coordinates:
			continue
		longitude, latitude = coordinates
		marker = {
			"title": missionary.title,
			"photo": missionary.photo,
			"country": missionary.country,
			"latitude": latitude,
			"longitude": longitude,
		}
		if include_name:
			marker["name"] = missionary.name
		markers.append(marker)
	return markers


def _get_point_coordinates(geolocation):
	"""[longitude, latitude] of the first Point feature in a Geolocation field's GeoJSON, or None."""
	for feature in json.loads(geolocation).get("features", []):
		geometry = feature.get("geometry") or {}
		if geometry.get("type") == "Point":
			return geometry.get("coordinates")
	return None


def create_missionary_expenses():
	"""Daily scheduler: for every Missionary with auto_create_expenses enabled,
	create a draft Expense for each support period that has come due."""
	missionaries = frappe.get_all(
		"Missionary",
		filters={"auto_create_expenses": 1},
		fields=["name"],
	)
	for missionary in missionaries:
		try:
			_create_due_expenses(missionary.name)
		except Exception:
			frappe.log_error(
				title=f"Auto-create Missionary Expense failed for {missionary.name}",
				message=frappe.get_traceback(),
			)


def _create_due_expenses(missionary_name):
	missionary = frappe.get_doc("Missionary", missionary_name)

	step = FREQUENCY_STEP.get(missionary.support_frequency)
	if not step or not missionary.support_amount or not missionary.expense_type:
		return
	if not missionary.support_start_date:
		return

	today_date = getdate(today())
	end_date = getdate(missionary.support_end_date) if missionary.support_end_date else None

	# Anchor the next due date to the most recent expense already generated for
	# this missionary; fall back to the support start date for the first run.
	last_date = frappe.db.get_value(
		"Expense",
		filters={"missionary": missionary_name},
		fieldname="date",
		order_by="date desc",
	)
	if last_date:
		next_date = step(getdate(last_date))
	else:
		next_date = getdate(missionary.support_start_date)

	created = 0
	while next_date <= today_date and created < MAX_EXPENSES_PER_RUN:
		if end_date and next_date > end_date:
			break
		_create_expense(missionary, next_date)
		created += 1
		next_date = step(next_date)


def _create_expense(missionary, expense_date):
	expense = frappe.get_doc(
		{
			"doctype": "Expense",
			"title": f"Missionary Support: {missionary.title}",
			"amount": missionary.support_amount,
			"type": missionary.expense_type,
			"date": expense_date,
			"missionary": missionary.name,
			"notes": (f"Auto-generated {missionary.support_frequency} support for " f"{missionary.title}."),
		}
	)
	expense.insert(ignore_permissions=True)
