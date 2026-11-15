# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import today

from churchit.church_people.doctype.position_type.position_type import assign_position_to_person
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

STAFF = "_test_position_staff@example.com"
SINGLE_ROLE = {"position": "_Test Single Role", "is_single_person_role": 1}


class TestPositionType(RollbackEachTest):
	def test_assigning_a_position_keeps_a_blank_start_date(self):
		position_type = ensure("Position Type", {"position": "_Test Assigned Role"})
		person = make_person("_Test Assigned", "Role")

		assign_position_to_person(position_type, person.name)

		self.assertIsNone(frappe.db.get_value("Position", {"parent": person.name}, "start_date"))

	def test_only_a_user_who_may_change_the_person_assigns_a_position(self):
		position_type = ensure("Position Type", {"position": "_Test Assigned Role"})
		person = make_person("_Test Refused", "Role")
		ensure_user(STAFF, "Position Staff", ("Church Staff",))
		frappe.set_user(STAFF)

		with self.assertRaises(frappe.PermissionError):
			assign_position_to_person(position_type, person.name)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Position", {"parent": person.name}))

	def test_each_church_has_its_own_holder_of_a_single_person_role(self):
		_root, church_a, church_b = make_two_churches()
		position_type = ensure("Position Type", SINGLE_ROLE)
		assign_position_to_person(position_type, make_person("_Test Holder", "Role", church=church_a).name)

		branch_holder = make_person("_Test Branch", "Role", church=church_b).name
		assign_position_to_person(position_type, branch_holder)
		self.assertTrue(frappe.db.exists("Position", {"parent": branch_holder, "position": position_type}))

		with self.assertRaisesRegex(frappe.ValidationError, "held by _Test Holder Role"):
			assign_position_to_person(
				position_type, make_person("_Test Hopeful", "Role", church=church_a).name
			)

	def test_a_site_with_one_church_has_one_holder_of_a_single_person_role(self):
		force_single_church()
		position_type = ensure("Position Type", SINGLE_ROLE)
		assign_position_to_person(position_type, make_person("_Test Holder", "Role").name)

		with self.assertRaisesRegex(frappe.ValidationError, "held by _Test Holder Role"):
			assign_position_to_person(position_type, make_person("_Test Hopeful", "Role").name)

	def test_the_person_form_refuses_a_second_holder_and_still_saves_an_older_one(self):
		force_single_church()
		position_type = ensure("Position Type", SINGLE_ROLE)
		assign_position_to_person(position_type, make_person("_Test Holder", "Role").name)

		hopeful = make_person("_Test Hopeful", "Role")
		hopeful.append("positions", {"position": position_type})
		with self.assertRaisesRegex(frappe.ValidationError, "held by _Test Holder Role"):
			hopeful.save()

		hopeful.reload()
		hopeful.append("positions", {"position": position_type, "end_date": today()})
		hopeful.save()
		hopeful.positions[0].end_date = None
		with self.assertRaisesRegex(frappe.ValidationError, "held by _Test Holder Role"):
			hopeful.save()

		older = make_person("_Test Older", "Role")
		row = {"parenttype": "Person", "parentfield": "positions", "parent": older.name, "idx": 1}
		frappe.get_doc({"doctype": "Position", "position": position_type, **row}).db_insert()
		older.reload()
		older.nickname = "_Test Old"
		older.save()

	def test_moving_a_holder_to_a_church_that_has_one_is_refused(self):
		_root, church_a, church_b = make_two_churches()
		position_type = ensure("Position Type", SINGLE_ROLE)
		assign_position_to_person(position_type, make_person("_Test Holder", "Role", church=church_a).name)
		mover = make_person("_Test Mover", "Role", church=church_b)
		assign_position_to_person(position_type, mover.name)

		mover.reload()
		mover.church = church_a
		with self.assertRaisesRegex(frappe.ValidationError, "held by _Test Holder Role"):
			mover.save()
