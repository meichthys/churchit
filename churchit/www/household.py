# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils import today

from churchit.church_foundations.doctype.church.church import address_line
from churchit.church_ministries.pre_check_in import get_functions
from churchit.church_people.household import ADULT, CHILD, get_ages, members, role_of
from churchit.church_scope import session_person
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
		context.check_in_functions = get_functions()


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


def get_members(people: list[str], roles: dict[str, str]) -> list[frappe._dict]:
	"""Each of *people* in order, with their household role, a Child's known age and whether the reader may edit them."""
	# church-scope: one household's own members, by name
	names = dict(
		frappe.get_all(
			"Person", filters={"name": ("in", people)}, fields=["name", "display_name"], as_list=True
		)
	)
	ages = get_ages([person for person in people if roles.get(person) == CHILD])
	return [
		frappe._dict(
			name=person,
			display_name=names[person],
			household_role=roles.get(person),
			age=ages.get(person),
			can_edit=frappe.has_permission("Person", "write", doc=person),
		)
		for person in people
	]


def get_address_line(address: str | None) -> str | None:
	"""The Address *address* on one line, or None without one."""
	if not address:
		return None
	return address_line(
		frappe.db.get_value(
			"Address", address, ["address_line1", "address_line2", "city", "state", "pincode"], as_dict=True
		)
	)
