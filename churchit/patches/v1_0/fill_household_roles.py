# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill the new Household Role on every family's members, the way a Family save fills a blank one.

Rows are written directly, so no family is saved, renamed or announced. The members whose role cannot be
worked out go to a Church Manager in one ToDo, to be set by hand. People who have died need no role.
"""

import frappe
from frappe import _
from frappe.utils import escape_html, get_link_to_form

from churchit.church_people.membership import living_people_filter

CHURCH_MANAGER = "Church Manager"


def execute():
	if not frappe.db.get_single_value("People Settings", "adult_age"):
		raise frappe.ValidationError("Seed People Settings' adult age before filling household roles")
	left_over = []
	for name in frappe.get_all("Family", pluck="name"):
		family = frappe.get_doc("Family", name)
		filled = family.fill_household_roles()
		for row in filled:
			frappe.db.set_value(
				"Family Members", row.name, "household_role", row.household_role, update_modified=False
			)
		family.set_life_stages(filled)
		left_over += [(row.member, family) for row in family.members if row.member and not row.household_role]
	assign_left_over(left_over)


def assign_left_over(left_over):
	"""One ToDo for a Church Manager, linking each living (member, family) of *left_over*; none without any."""
	if not left_over:
		return
	living = dict(
		frappe.get_all(
			"Person",
			filters=[["name", "in", [member for member, _family in left_over]], living_people_filter()],
			fields=["name", "full_name"],
			as_list=True,
		)
	)
	items = "".join(
		"<li>{} ({})</li>".format(
			get_link_to_form("Person", member, escape_html(living[member])),
			get_link_to_form("Family", family.name, escape_html(family.family_name)),
		)
		for member, family in left_over
		if member in living
	)
	if not items:
		return
	description = _(
		"Set the Household Role of these family members by hand, on their family. The upgrade could not work it out from their relationship and age."
	)
	frappe.get_doc(
		{
			"doctype": "ToDo",
			"description": f"<p>{description}</p><ul>{items}</ul>",
			"role": CHURCH_MANAGER,
			"allocated_to": get_first_church_manager(),
		}
	).insert(ignore_permissions=True)


def get_first_church_manager() -> str:
	"""The longest-standing enabled Church Manager, or Administrator when there is none.

	A ToDo's role does not show it to anyone, so the ToDo is allocated to one person who holds it.
	"""
	managers = frappe.get_all(
		"User",
		filters=[
			["Has Role", "role", "=", CHURCH_MANAGER],
			["User", "enabled", "=", 1],
			["User", "name", "not in", ("Administrator", "Guest")],
		],
		order_by="creation asc",
		limit=1,
		pluck="name",
	)
	return managers[0] if managers else "Administrator"
