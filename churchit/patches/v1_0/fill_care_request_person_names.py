# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each care request with the person's name, not the Person ID: fill the new Person Name field."""

import frappe


def execute():
	requests = frappe.get_all(
		"Care Request", filters={"person_name": ("is", "not set")}, fields=["name", "person"]
	)
	people = list({request.person for request in requests if request.person})
	full_names = dict(
		frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", "full_name"], as_list=True)
	)
	for request in requests:
		if full_names.get(request.person):
			frappe.db.set_value(
				"Care Request", request.name, "person_name", full_names[request.person], update_modified=False
			)
