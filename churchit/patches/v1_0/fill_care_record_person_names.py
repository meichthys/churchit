# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each visit, care assignment, counseling case and member transfer with the person's name: fill Person Name."""

import frappe

DOCTYPES = ("Visitation Log", "Care Assignment", "Counseling Case", "Member Transfer")


def execute():
	for doctype in DOCTYPES:
		# church-scope: a patch fills every church's records
		records = frappe.get_all(
			doctype, filters={"person_name": ("is", "not set")}, fields=["name", "person"]
		)
		people = list({record.person for record in records if record.person})
		full_names = dict(
			frappe.get_all(
				"Person", filters={"name": ("in", people)}, fields=["name", "full_name"], as_list=True
			)
		)
		for record in records:
			if full_names.get(record.person):
				frappe.db.set_value(
					doctype, record.name, "person_name", full_names[record.person], update_modified=False
				)
