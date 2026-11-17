# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils import cint, format_time, today

from churchit.church_foundations.doctype.church.church import address_line
from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_ministries.pre_check_in import get_functions, get_household_adults
from churchit.church_people.household import ADULT, CHILD, get_ages, get_editable_children, members, role_of
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import is_multi_church, session_person
from churchit.contacts import mailing_address

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/household"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = _("My Household")
	context.person = session_person()
	if context.person:
		context.update(get_household(context.person))
		context.update(get_pre_check_in(context.members))


def get_household(person: str) -> dict:
	"""The member's Family with its mailing address and living members, or the member alone without a Family."""
	family_name = frappe.db.get_value("Person", person, "family")
	if not family_name:
		return {"family": None, "members": get_members([person], {})}

	family = frappe.get_doc("Family", family_name)
	return {
		"family": family,
		"family_title": _("The {0} Family").format(
			family.family_name.rpartition(" - ")[0] or family.family_name
		),
		"address": get_address_line(mailing_address(family)),
		"can_change_photo": family.has_permission("write"),
		# What the Add a Child form needs, for an Adult only.
		"add_child": frappe._dict(
			last_name=frappe.db.get_value("Person", person, "last_name"),
			adult_age=frappe.db.get_single_value("People Settings", "adult_age"),
			today=today(),
		)
		if role_of(person) == ADULT
		else None,
		"members": get_members(
			members(family_name), {row.member: row.household_role for row in family.members}
		),
	}


def get_pre_check_in(household_members: list[frappe._dict]) -> dict:
	"""The Functions open for pre check-in now, each with the start time to show, and who the member may check in.

	`check_in_people` are the *household_members* the member may edit, and the other adults of the household
	when Check-In Settings allows it. With no Function open, `check_in_opens_minutes` says how long before a
	service check-in opens. It is None when no Function Type allows self check-in.
	"""
	functions = get_functions()
	for function in functions:
		function.time = format_time(function.start_time, TIME_FORMAT) if function.start_time else None
	opens_minutes = None
	if not functions and frappe.db.exists("Function Type", {"allow_self_check_in": 1}):
		opens_minutes = cint(frappe.db.get_single_value("Check-In Settings", "check_in_opens_minutes"))
	adults = get_household_adults()
	return {
		"check_in_functions": functions,
		"check_in_opens_minutes": opens_minutes,
		"check_in_people": [
			member for member in household_members if member.can_edit or member.name in adults
		],
	}


def get_members(people: list[str], roles: dict[str, str]) -> list[frappe._dict]:
	"""Each of *people* in order, with their household role, a Child's known age and whether the reader may edit them."""
	# church-scope: one household's own members, by name
	names = dict(
		frappe.get_all(
			"Person", filters={"name": ("in", people)}, fields=["name", "display_name"], as_list=True
		)
	)
	ages = get_ages([person for person in people if roles.get(person) == CHILD])
	editable = get_editable_people()
	return [
		frappe._dict(
			name=person,
			display_name=names[person],
			household_role=roles.get(person),
			age=ages.get(person),
			can_edit=(
				person in editable
				if editable is not None
				else frappe.has_permission("Person", "write", doc=person)
			),
		)
		for person in people
	]


def get_editable_people() -> set[str] | None:
	"""The people a member may edit, worked out once, or None when only Frappe knows.

	It is the answer of `member_access.refuse_other_people_to_members` for every member of the house. Frappe
	decides for staff, for a member without write, and on a site with several churches, where
	`church_scope.refuse_changing_another_churches_people` also refuses a Child of another church.
	"""
	if (
		not is_portal_member()
		or is_multi_church()
		or not frappe.has_permission("Person", "write", ignore_share_permissions=True)
	):
		return None
	return {session_person(), *get_editable_children(frappe.session.user)}


def get_address_line(address: str | None) -> str | None:
	"""The Address *address* on one line, or None without one."""
	if not address:
		return None
	return address_line(
		frappe.db.get_value(
			"Address", address, ["address_line1", "address_line2", "city", "state", "pincode"], as_dict=True
		)
	)
