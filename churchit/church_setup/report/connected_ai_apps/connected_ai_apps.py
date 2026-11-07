# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who connected which AI app. OAuth Bearer Token names each row by its access token, so this report
groups the tokens by person and app and never selects a token."""

import frappe
from frappe import _

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"fieldname": "user", "fieldtype": "Link", "label": _("Person"), "options": "User", "width": 220},
		{
			"fieldname": "client",
			"fieldtype": "Link",
			"label": _("App"),
			"options": "OAuth Client",
			"width": 120,
		},
		{
			"fieldname": "app_name",
			"fieldtype": "Data",
			"label": _("App Name, As the App Gave It"),
			"width": 220,
		},
		{"fieldname": "connected_on", "fieldtype": "Datetime", "label": _("Connected On"), "width": 170},
		{"fieldname": "refreshed_on", "fieldtype": "Datetime", "label": _("Last Refreshed On"), "width": 170},
		{"fieldname": "tokens", "fieldtype": "Int", "label": _("Active Tokens"), "width": 120},
	]


def get_data() -> list[dict]:
	"""One row per person and app with an active token."""
	rows = frappe.get_list(
		"OAuth Bearer Token",
		filters={"status": "Active"},
		fields=[
			"user",
			"client",
			{"MIN": "creation", "as": "connected_on"},
			{"MAX": "creation", "as": "refreshed_on"},
			{"COUNT": "*", "as": "tokens"},
		],
		group_by="user, client",
		order_by="user asc",
	)
	app_names = dict(
		frappe.get_list(
			"OAuth Client",
			filters={"name": ("in", [row.client for row in rows])},
			fields=["name", "app_name"],
			as_list=True,
		)
	)
	for row in rows:
		row["app_name"] = app_names.get(row.client)
	return rows
