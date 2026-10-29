# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Make Adults of the primary contacts and spouses whose household role was filled before their family had a primary contact.

Such a member got Other Adult from their age alone, and a filled role is kept. The household rule makes the
primary contact and their spouse Adults. Rows are written directly, so no family is saved or renamed.
"""

import frappe

from churchit.church_people.family_relations import ROLE_TYPES
from churchit.church_people.household import ADULT, OTHER_ADULT


def execute():
	Members = frappe.qb.DocType("Family Members")
	Family = frappe.qb.DocType("Family")
	families = (
		frappe.qb.from_(Members)
		.join(Family)
		.on(Family.name == Members.parent)
		.select(Members.parent)
		.distinct()
		.where((Members.parenttype == "Family") & (Members.household_role == OTHER_ADULT))
		.where(
			(Members.member == Family.primary_contact)
			| Members.relationship_to_primary_contact.isin(ROLE_TYPES["spouse"])
		)
		.run(pluck=True)
	)
	for name in families:
		family = frappe.get_doc("Family", name)
		repaired = [
			row
			for row in family.members
			if row.household_role == OTHER_ADULT
			and (
				row.member == family.primary_contact
				or row.relationship_to_primary_contact in ROLE_TYPES["spouse"]
			)
		]
		for row in repaired:
			row.household_role = ADULT
			frappe.db.set_value("Family Members", row.name, "household_role", ADULT, update_modified=False)
		family.set_life_stages(repaired)
