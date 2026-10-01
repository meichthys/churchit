# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Server side of the Rolodex page: the people directory as cards."""

import json

import frappe
from frappe.utils import getdate, sbool

from churchit.church_foundations.doctype.church.church import ADDRESS_FIELDS, address_line
from churchit.church_scope import is_multi_church
from churchit.church_website.footer import map_url
from churchit.contacts import ADDRESS_DOCTYPE, EMAIL_DOCTYPE, PHONE_DOCTYPE, get_primary_values

PERSON_FIELDS = [
	"name",
	"first_name",
	"last_name",
	"full_name",
	"photo",
	"family",
	"is_head_of_household",
	"membership_status",
	"age",
	"anniversary",
	"church",
]
# A user default rather than Frappe's user settings, which wait in the cache for an
# hourly sync and are lost to any cache clear before it.
SETTINGS_DEFAULT = "rolodex_settings"


@frappe.whitelist()
def get_directory():
	"""Every person and family the reader may see, what their cards show, and the filter choices.

	`frappe.get_list` applies the reader's churches and the directory privacy
	setting. Child tables carry no church, so they are read only for those people.
	"""
	people = frappe.get_list(
		"Person", fields=PERSON_FIELDS, order_by="last_name asc, first_name asc", limit_page_length=0
	)
	groups = frappe.get_list(
		"Group", fields=["name", "group_name"], order_by="group_name asc", limit_page_length=0
	)
	families = get_families({person.family for person in people if person.family})
	add_contacts(people, "Person")
	add_contacts(families, "Family")
	add_card_backs(people, groups)
	return {
		"people": people,
		"families": families,
		"choices": {
			"status": frappe.get_all("Member Status", pluck="name", order_by="name asc"),
			"group": [[group.name, group.group_name or group.name] for group in groups],
			"position": frappe.get_all("Position Type", pluck="name", order_by="name asc"),
			"church": get_churches(),
		},
		"settings": get_settings(),
	}


@frappe.whitelist()
def save_settings(saved: str | list[str], view: str, filters_open: bool | str):
	"""Keep the reader's saved cards and layout, on every device they sign in from."""
	settings = {"saved": list(frappe.parse_json(saved)), "view": view, "filters_open": sbool(filters_open)}
	frappe.defaults.set_user_default(SETTINGS_DEFAULT, json.dumps(settings))


def get_settings():
	"""Read from the row itself: the user-defaults cache is per worker and lags a write."""
	value = frappe.db.get_value(
		"DefaultValue", {"parent": frappe.session.user, "defkey": SETTINGS_DEFAULT}, "defvalue"
	)
	return json.loads(value) if value else {}


def get_families(names):
	if not names:
		return []
	return frappe.get_list(
		"Family",
		filters={"name": ("in", list(names))},
		fields=["name", "family_name", "photo"],
		limit_page_length=0,
	)


def get_churches():
	"""The churches a card can belong to, for the church filter; none on a single-church site."""
	if not is_multi_church():
		return []
	return [
		[church.name, church.church_name]
		for church in frappe.get_list("Church", fields=["name", "church_name"], order_by="lft asc")
	]


def add_contacts(records, parenttype):
	"""Primary phone, email and one-line address, with a map link, on each record."""
	names = [record.name for record in records]
	phones = get_primary_values(PHONE_DOCTYPE, "phone_number", parenttype, names)
	emails = get_primary_values(EMAIL_DOCTYPE, "email_address", parenttype, names)
	address_names = get_primary_values(ADDRESS_DOCTYPE, "address", parenttype, names)
	addresses = get_address_lines(set(address_names.values()))
	for record in records:
		record.phone = phones.get(record.name)
		record.email = emails.get(record.name)
		record.address = addresses.get(address_names.get(record.name))
		record.map_url = map_url(record.address)


def get_address_lines(names):
	if not names:
		return {}
	rows = frappe.get_all("Address", filters={"name": ("in", list(names))}, fields=["name", *ADDRESS_FIELDS])
	return {row.name: address_line(row) for row in rows}


def add_card_backs(people, groups):
	"""Birthday, current positions and group memberships for the back of each card."""
	names = [person.name for person in people]
	birthdays = get_birthdays(names)
	positions = get_current_positions(names)
	memberships = get_memberships(names, [group.name for group in groups])
	for person in people:
		person.birthday = birthdays.get(person.name)
		person.positions = positions.get(person.name, [])
		person.groups = memberships.get(person.name, [])


def get_birthdays(names):
	if not names:
		return {}
	rows = frappe.get_all(
		"Life Event",
		filters={
			"parenttype": "Person",
			"parent": ("in", names),
			"event_type": "Birth",
			"date": ("is", "set"),
		},
		fields=["parent", "date"],
	)
	return {row.parent: row.date for row in rows}


def get_current_positions(names):
	"""Position types held today, per person, in the order the Person form lists them."""
	if not names:
		return {}
	today = getdate()
	rows = frappe.get_all(
		"Position",
		filters={"parenttype": "Person", "parent": ("in", names)},
		fields=["parent", "position", "start_date", "end_date"],
		order_by="idx asc",
	)
	held = {}
	for row in rows:
		if (row.start_date or today) <= today <= (row.end_date or today):
			held.setdefault(row.parent, []).append(row.position)
	return held


def get_memberships(names, groups):
	"""The readable groups each person belongs to; another church's group stays out of view."""
	if not names or not groups:
		return {}
	rows = frappe.get_all(
		"Group Member",
		filters={"parenttype": "Group", "parent": ("in", groups), "person": ("in", names)},
		fields=["parent", "person"],
	)
	memberships = {}
	for row in rows:
		memberships.setdefault(row.person, []).append(row.parent)
	return memberships
