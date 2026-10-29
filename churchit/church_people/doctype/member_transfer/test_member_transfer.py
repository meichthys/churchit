# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.doctype.inactive_reason.inactive_reason import TRANSFERRED
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestMemberTransfer(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Member Status", {"status": "Active"})
		ensure("Member Status", {"status": "Inactive"})
		ensure("Membership Type", {"type": "Member"})
		ensure("Membership Type", {"type": "Contact"})
		ensure("Inactive Reason", {"reason": TRANSFERRED})

	def transfer_out(self, person, status):
		return self.transfer(person, "Out", status)

	def transfer(self, person, direction, status):
		return frappe.get_doc(
			{
				"doctype": "Member Transfer",
				"person": person,
				"direction": direction,
				"other_church": "_Test Elsewhere Church",
				"status": status,
			}
		).insert()

	def test_confirming_a_transfer_in_makes_an_active_member(self):
		ensure("Life Event Type", {"type": "Membership"})
		person = make_person("_Test Arriving", "Member", membership="Contact", membership_status="Inactive")
		transfer = self.transfer(person.name, "In", "Letter Issued")

		transfer.status = "Confirmed"
		transfer.save()

		person.reload()
		self.assertEqual((person.membership, person.membership_status), ("Member", "Active"))
		(event,) = [row for row in person.life_events if row.event_type == "Membership"]
		self.assertEqual(event.notes, "Transferred from _Test Elsewhere Church")

	def test_confirming_a_transfer_in_again_adds_no_second_membership(self):
		ensure("Life Event Type", {"type": "Membership"})
		person = make_person("_Test Arrived", "Member", membership="Contact")
		for transfer in (self.transfer(person.name, "In", "Pending") for _ in range(2)):
			transfer.status = "Confirmed"
			transfer.save()

		person.reload()
		self.assertEqual(len([row for row in person.life_events if row.event_type == "Membership"]), 1)

	def test_confirming_a_transfer_out_ends_the_membership(self):
		person = make_person("_Test Leaving", "Member", membership="Member")
		transfer = self.transfer_out(person.name, "Requested")
		self.assertEqual(frappe.db.get_value("Person", person.name, "membership"), "Member")

		transfer.status = "Confirmed"
		transfer.save()

		person.reload()
		self.assertEqual(person.membership, "Contact")
		self.assertEqual(person.membership_status, "Inactive")
		self.assertEqual(person.inactive_reason, TRANSFERRED)
