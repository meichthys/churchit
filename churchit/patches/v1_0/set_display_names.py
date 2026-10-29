# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give every existing person a Display Name, which is otherwise set only when they are next saved."""

import frappe

from churchit.church_people.doctype.person.person import get_display_name


def execute():
	people = frappe.get_all(
		"Person", fields=["name", "first_name", "last_name", "nickname", "suffix", "display_name"]
	)
	for person in people:
		display_name = get_display_name(person.first_name, person.last_name, person.nickname, person.suffix)
		if person.display_name != display_name:
			frappe.db.set_value("Person", person.name, "display_name", display_name, update_modified=False)
