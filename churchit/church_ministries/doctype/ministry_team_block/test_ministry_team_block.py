# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import update_doc

from churchit.church_ministries.availability import get_blocks_covering
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

BLOCK = "Ministry Team Block"


def block(person, from_date, to_date, **values):
	return frappe.get_doc(
		{
			"doctype": "Ministry Team Block",
			"person": person,
			"from_date": from_date,
			"to_date": to_date,
			**values,
		}
	).insert(ignore_permissions=True)


class TestMinistryTeamBlock(RollbackEachTest):
	def setUp(self):
		super().setUp()
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Block Family"}).insert(
			ignore_permissions=True
		)
		self.parent = make_person("_Test Block", "Parent", family=family.name)
		self.child = make_person("_Test Block", "Child", family=family.name)

	def test_to_date_cannot_come_before_from_date(self):
		with self.assertRaises(frappe.ValidationError):
			block(self.parent.name, "2031-05-10", "2031-05-09")

	def test_a_block_covers_its_person_on_any_overlapping_day(self):
		own = block(self.parent.name, "2031-05-10", "2031-05-12").name

		self.assertEqual(
			[b.name for b in get_blocks_covering(self.parent.name, "2031-05-12", "2031-05-14")], [own]
		)
		self.assertEqual(get_blocks_covering(self.parent.name, "2031-05-13", "2031-05-14"), [])
		self.assertEqual(get_blocks_covering(self.child.name, "2031-05-10", "2031-05-10"), [])

	def test_a_whole_household_block_covers_the_family(self):
		household = block(self.parent.name, "2031-05-10", "2031-05-12", whole_household=1).name
		self.assertEqual(
			[b.name for b in get_blocks_covering(self.child.name, "2031-05-11", "2031-05-11")], [household]
		)


class TestMinistryTeamBlockChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_block_a@example.com", "Coordinator", roles=("Church Manager",))
		make_person("_Test Block", "Coordinator", church=cls.branch_a, user=cls.manager_a)
		cls.person_a = make_person("_Test Block", "Mine", church=cls.branch_a).name
		cls.person_b = make_person("_Test Block", "Theirs", church=cls.branch_b).name

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_only_the_persons_church_blocks_them_or_moves_a_block(self):
		"""Frappe checks the church the caller sends, before the block takes the person's church."""
		theirs = block(self.person_b, "2031-05-10", "2031-05-12").name
		frappe.set_user(self.manager_a)
		dates = {"from_date": "2031-05-10", "to_date": "2031-05-12"}

		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc(BLOCK, person=self.person_b, **dates).insert()
		self.assertEqual(frappe.new_doc(BLOCK, person=self.person_a, **dates).insert().church, self.branch_a)

		frappe.local.form_dict = frappe._dict(
			data=json.dumps({"person": self.person_a, "church": self.branch_a})
		)
		with self.assertRaises(frappe.PermissionError):
			update_doc(BLOCK, theirs)
		self.assertEqual(frappe.db.get_value(BLOCK, theirs, "person"), self.person_b)
