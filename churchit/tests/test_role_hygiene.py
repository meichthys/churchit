# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every staff role profile can use the forms it may fill in.

A role that can write a form but not read or select a doctype one of its Link
fields points at gets an empty picker, or "Insufficient Permission" on save.
Nothing else catches that, because each role is only ever tried with the others.
"""

import json

import frappe
from frappe.desk.desktop import Workspace as DeskWorkspace
from frappe.desk.desktop import get_desktop_page
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as get_chart
from frappe.desk.doctype.number_card.number_card import get_result
from frappe.desk.query_report import run as run_report
from frappe.tests.utils import FrappeTestCase

# Profiles made of the narrow desk roles. Church Manager holds everything and
# Church User is the portal, where forms carry their own link options.
STAFF_PROFILES = (
	"Church Staff",
	"Church Office",
	"Church Care Team",
	"Church Treasurer",
	"Church Check-In Volunteer",
)


def app_doctypes():
	return set(frappe.get_all("DocType", filters={"module": ("like", "Church%")}, pluck="name"))


def profile_roles(profile):
	return set(
		frappe.get_all("Has Role", filters={"parent": profile, "parenttype": "Role Profile"}, pluck="role")
	)


def permission_rows(doctype, roles):
	return [row for row in frappe.get_meta(doctype).permissions if row.role in roles and not row.permlevel]


def can_fill_in(doctype, roles):
	return any(row.write or row.create for row in permission_rows(doctype, roles))


def can_pick(doctype, roles):
	return any(row.read or row.select for row in permission_rows(doctype, roles))


def pickable_links(doctype):
	"""(fieldname, target) for every Link a user picks on the form, child tables included."""
	meta = frappe.get_meta(doctype)
	for field in meta.fields:
		if field.fieldtype in ("Table", "Table MultiSelect"):
			for child in frappe.get_meta(field.options).fields:
				if is_picked(child):
					yield f"{field.fieldname}.{child.fieldname}", child.options
		elif is_picked(field):
			yield field.fieldname, field.options


def is_picked(field):
	return field.fieldtype == "Link" and not (field.hidden or field.read_only or field.fetch_from)


class TestRoleHygiene(FrappeTestCase):
	def test_every_staff_profile_can_pick_what_its_forms_link_to(self):
		ours = app_doctypes()
		unpickable = []
		for profile in STAFF_PROFILES:
			roles = profile_roles(profile)
			self.assertTrue(roles, f"Role Profile {profile} is missing or empty")
			for doctype in sorted(ours):
				if frappe.get_meta(doctype).istable or not can_fill_in(doctype, roles):
					continue
				for fieldname, target in pickable_links(doctype):
					if target in ours and not can_pick(target, roles):
						unpickable.append(f"{profile}: {doctype}.{fieldname} -> {target}")
		self.assertEqual(unpickable, [], "Give the profile read or select on these targets")


class TestProfilesOpenTheirWorkspaces(FrappeTestCase):
	"""What a profile is shown, it can load: no card, chart or report errors on its workspaces."""

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_every_card_and_chart_a_profile_is_shown_loads(self):
		failures = []
		for profile in STAFF_PROFILES:
			frappe.set_user(make_profile_user(profile))
			for workspace in shown_workspaces():
				page = get_desktop_page(json.dumps({"name": workspace, "title": workspace, "public": 1}))
				for row in page["number_cards"]["items"]:
					failures += attempt(profile, "card", row.number_card_name, load_card)
				for row in page["charts"]["items"]:
					failures += attempt(profile, "chart", row.chart_name, load_chart)
			frappe.set_user("Administrator")
		self.assertEqual(failures, [])


def make_profile_user(profile):
	email = f"_test_{frappe.scrub(profile)}@example.com"
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.update({"email": email, "first_name": profile, "send_welcome_email": 0})
		user.append("role_profiles", {"role_profile": profile})
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)
	return email


def shown_workspaces():
	"""The churchit workspaces the current user is shown."""
	shown = []
	for name in frappe.get_all(
		"Workspace", filters={"module": ("like", "Church%"), "public": 1}, pluck="name"
	):
		try:
			if DeskWorkspace({"name": name, "title": name, "public": 1}, minimal=True).is_permitted():
				shown.append(name)
		except frappe.PermissionError:
			continue
	return shown


def attempt(profile, kind, name, load):
	try:
		load(name)
		return []
	except Exception as error:
		return [f"{profile}: {kind} {name}: {type(error).__name__} {error}"]


def load_card(name):
	card = frappe.get_doc("Number Card", name)
	if card.type == "Custom":
		frappe.call(card.method, filters=card.filters_json)
	elif card.type == "Report":
		run_report(card.report_name, card.filters_json)
	else:
		get_result(card.as_dict(), card.filters_json)


def load_chart(name):
	chart = frappe.get_doc("Dashboard Chart", name)
	if chart.chart_type == "Custom":
		source = frappe.get_doc("Dashboard Chart Source", chart.source)
		path = f"churchit.{frappe.scrub(source.module)}.dashboard_chart_source.{frappe.scrub(source.name)}"
		frappe.call(f"{path}.{frappe.scrub(source.name)}.get", chart_name=name, filters=chart.filters_json)
	elif chart.chart_type == "Report":
		run_report(chart.report_name, chart.filters_json)
	else:
		get_chart(chart_name=name)
