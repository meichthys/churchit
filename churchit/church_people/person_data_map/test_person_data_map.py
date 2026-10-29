# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.person_data_map import LinkedRecord, linked_records
from churchit.church_people.test_merge import email
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestPersonDataMap(RollbackEachTest):
	def test_records_child_rows_and_dynamic_links_that_name_a_person_are_found(self):
		person = make_person("_Test Mapped", "Person", emails=[email("_test.mapped@example.com")])
		wife = make_person(
			"_Test Wife",
			"Person",
			spouse=person.name,
			marital_status="Married",
			emails=[email("_test.mapped@example.com", shared_from_type="Person", shared_from=person.name)],
		)
		check = frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": person.name,
				"check_type": ensure("Background Check Type", {"type": "_Test Check"}),
				"status": "Requested",
				"requested_on": "2026-01-01",
			}
		).insert(ignore_permissions=True)
		group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Mapped Group", "members": [{"person": person.name}]}
		).insert(ignore_permissions=True)

		found = set(linked_records(person.name))

		self.assertLessEqual(
			{
				LinkedRecord("Background Check", check.name, "person"),
				LinkedRecord("Person", wife.name, "spouse"),
				LinkedRecord("Group Member", group.members[0].name, "person", "Group", group.name),
				LinkedRecord("Email Address", wife.emails[0].name, "shared_from", "Person", wife.name),
			},
			found,
		)
		self.assertNotIn(person.emails[0].name, {record.name for record in found})
