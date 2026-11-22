# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The household page and the check-in pass of the member app."""

import frappe
from frappe import _
from frappe.utils import cint, format_time, today

from churchit.church_ministries.doctype.function.function import TIME_FORMAT, get_time_window
from churchit.church_ministries.pre_check_in import get_functions, get_household_adults, get_pre_check_in_code
from churchit.church_people.household import ADULT, members, role_of
from churchit.contacts import mailing_address
from churchit.portal.access import require_page, require_person
from churchit.www.calendar import get_rooms
from churchit.www.household import get_address_line, get_members

PAGE = "household"


def get_member_rows(person: str) -> tuple[frappe.model.document.Document | None, list[frappe._dict]]:
	"""The member's own Family (None without one) and its living people, each with the reader's edit right."""
	family_name = frappe.db.get_value("Person", person, "family")
	if not family_name:
		return None, get_members([person], {})

	family = frappe.get_doc("Family", family_name)
	roles = {row.member: row.household_role for row in family.members}
	return family, get_members(members(family_name), roles)


@frappe.whitelist(methods=["GET"])
def get_household() -> dict:
	"""The member's household: photo, address, the people in it and what the member may do. Reads only."""
	person = require_person()
	require_page(PAGE)

	family, rows = get_member_rows(person)
	return {
		"person": person,
		"family": get_family_summary(family),
		"can_change_photo": bool(family and family.has_permission("write")),
		"members": [
			{
				"name": row.name,
				"display_name": row.display_name,
				"household_role": row.household_role,
				"age": row.age,
				"is_you": row.name == person,
				"can_edit": bool(row.can_edit),
			}
			for row in rows
		],
		"add_child": get_add_child(person) if role_of(person) == ADULT else None,
	}


def get_family_summary(family) -> dict | None:
	"""The household's title, photo and one-line mailing address, and nothing else of the Family."""
	if not family:
		return None
	return {
		"name": family.name,
		"title": _("The {0} Family").format(family.family_name.rpartition(" - ")[0] or family.family_name),
		"photo": family.photo,
		"address": get_address_line(mailing_address(family)),
	}


def get_add_child(person: str) -> dict:
	"""What the Add a Child form needs: the adult's last name, the adult age and today."""
	return {
		"last_name": frappe.db.get_value("Person", person, "last_name"),
		"adult_age": cint(frappe.db.get_single_value("People Settings", "adult_age")),
		"today": today(),
	}


@frappe.whitelist(methods=["GET"])
def get_pre_check_in() -> dict:
	"""The Functions open for self check-in now, who the member may check in, and who is in already. Reads only."""
	person = require_person()
	require_page(PAGE)

	_family, rows = get_member_rows(person)
	adults = get_household_adults()
	people = [row for row in rows if row.can_edit or row.name in adults]
	functions = get_functions()
	rooms = get_room_names([row.name for row in functions])
	checked_in = get_checked_in_times([row.name for row in functions], [row.name for row in people])
	return {
		"functions": [
			{
				"name": row.name,
				"function_name": row.function_name,
				"time": format_time(row.start_time, TIME_FORMAT) if row.start_time else None,
				"start_time": format_time(row.start_time, "HH:mm:ss") if row.start_time else None,
				"rooms": rooms.get(row.name, []),
			}
			for row in functions
		],
		"people": [
			{
				"name": row.name,
				"display_name": row.display_name,
				"age": row.age,
				"household_role": row.household_role,
				"checked_in": checked_in.get(row.name, {}),
			}
			for row in people
		],
		"opens_minutes": get_opens_minutes(functions),
		"has_pickup_codes": bool(frappe.db.get_single_value("Check-In Settings", "security_codes")),
	}


def get_opens_minutes(functions: list[dict]) -> int | None:
	"""How long before a service check-in opens, when no Function is open but a type allows self check-in."""
	if functions or not frappe.db.exists("Function Type", {"allow_self_check_in": 1}):
		return None
	return cint(frappe.db.get_single_value("Check-In Settings", "check_in_opens_minutes"))


def get_room_names(functions: list[str]) -> dict[str, list[str]]:
	"""{function: room names} of the Approved bookings of the *functions* offered to this member."""
	if not functions:
		return {}

	# church-scope: the Functions were offered to this member by get_functions; their church scopes the bookings
	rows = frappe.get_all("Function", filters={"name": ("in", functions)}, fields=["name", "church"])
	return get_rooms(rows)


def get_checked_in_times(functions: list[str], people: list[str]) -> dict[str, dict[str, str]]:
	"""{person: {function: "HH:mm:ss"}} for the *people* already checked in to the *functions*."""
	if not functions or not people:
		return {}

	# church-scope: the check-ins of this household's own people at the Functions offered to them
	rows = frappe.get_all(
		"Function Check-In",
		filters={"function": ("in", functions), "person": ("in", people)},
		fields=["function", "person", "creation"],
	)
	result: dict[str, dict[str, str]] = {}
	for row in rows:
		result.setdefault(row.person, {})[row.function] = row.creation.strftime("%H:%M:%S")
	return result


@frappe.whitelist(methods=["GET"])
def get_check_in_code(function: str, persons: str) -> dict:
	"""The QR code that checks *persons* in to *function* when scanned, and when it stops working. Reads only.

	*persons* is a JSON list. get_pre_check_in_code checks the right to check each one in.
	"""
	require_person()
	require_page(PAGE)
	offered = next((row.name for row in get_functions() if row.name == function), None)
	if not offered:
		frappe.throw(_("Check-in to this function is not open now."), frappe.PermissionError)

	result = get_pre_check_in_code(offered, persons)
	fields = ["start_date", "end_date", "start_time", "end_time", "all_day"]
	ends = get_time_window(frappe.db.get_value("Function", offered, fields, as_dict=True))[1]
	result["ends"] = ends.strftime("%Y-%m-%d %H:%M:%S")
	return result
