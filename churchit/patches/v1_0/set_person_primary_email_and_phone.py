# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give every existing person the stored primary email and phone, which are otherwise set only when they are next saved."""

import frappe

from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, get_primary_values


def execute():
	people = frappe.get_all("Person", fields=["name", "primary_email", "primary_phone"])
	names = [person.name for person in people]
	emails = get_primary_values(EMAIL_DOCTYPE, "email_address", "Person", names)
	phones = get_primary_values(PHONE_DOCTYPE, "phone_number", "Person", names)
	for person in people:
		values = {"primary_email": emails.get(person.name), "primary_phone": phones.get(person.name)}
		if values != {"primary_email": person.primary_email, "primary_phone": person.primary_phone}:
			frappe.db.set_value("Person", person.name, values, update_modified=False)
