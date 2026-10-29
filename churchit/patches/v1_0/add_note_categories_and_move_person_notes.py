# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Note Categories, and move each person's Notes field into a Person Note in General.

The note is dated the day the person was added, since the field kept no date of its own. Migrate keeps the
dropped `notes` column, so this reads it with the query builder and then empties it: the old copy must not
outlive the move or a later anonymization, and a second run finds nothing to move.
"""

import frappe
from frappe.utils import getdate, strip_html_tags

from churchit.church_people.doctype.note_category.note_category import GENERAL, create_note_categories


def execute():
	create_note_categories()
	if not frappe.db.has_column("Person", "notes"):
		return
	Person = frappe.qb.DocType("Person")
	people = (
		frappe.qb.from_(Person)
		.select(Person.name, Person.notes, Person.creation)
		.where(Person.notes.isnotnull() & (Person.notes != ""))
		.run(as_dict=True)
	)
	for person in people:
		if strip_html_tags(person.notes).strip() or "<img" in person.notes:
			add_general_note(person)
	frappe.qb.update(Person).set(Person.notes, None).where(Person.notes.isnotnull()).run()


def add_general_note(person: frappe._dict) -> None:
	"""A Person Note in General holding *person*'s old Notes field."""
	frappe.get_doc(
		{
			"doctype": "Person Note",
			"person": person.name,
			"category": GENERAL,
			"noted_on": getdate(person.creation),
			"note": person.notes,
		}
	).insert(ignore_permissions=True)
