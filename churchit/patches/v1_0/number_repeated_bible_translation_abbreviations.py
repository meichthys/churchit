# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each Bible Translation its own abbreviation before migrate makes the field unique.

The abbreviation now names the translation, so two that shared one would stop the schema
sync. A repeat gets a number, such as "KJV 2", for the church to tidy afterwards.
"""

import frappe


def execute():
	rows = frappe.db.sql("select name, abbreviation from `tabBible Translation` order by creation")
	for name, abbreviation in get_renumbered(rows):
		frappe.db.set_value("Bible Translation", name, "abbreviation", abbreviation, update_modified=False)


def get_renumbered(rows):
	"""(name, new abbreviation) for each translation, oldest first, whose abbreviation is taken."""
	taken, renumbered = set(), []
	for name, abbreviation in rows:
		base = abbreviation or name
		unique, number = base, 1
		while unique.strip().lower() in taken:
			number += 1
			unique = f"{base} {number}"
		taken.add(unique.strip().lower())
		if unique != abbreviation:
			renumbered.append((name, unique))
	return renumbered
