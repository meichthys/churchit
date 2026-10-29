# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import update_doc

from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

CASE = "Counseling Case"


class TestCounselingCaseChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.pastor_a = ensure_user(
			"_test_counseling_a@example.com", "Pastor", roles=("Church Pastoral Care",)
		)
		make_person("_Test Counseling", "Pastor", church=cls.branch_a, user=cls.pastor_a)
		cls.person_a = make_person("_Test Counseling", "Mine", church=cls.branch_a).name
		cls.person_b = make_person("_Test Counseling", "Theirs", church=cls.branch_b).name

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_only_the_persons_church_opens_a_case_or_moves_one(self):
		"""Frappe checks the church the caller sends, before the case takes the person's church."""
		theirs = frappe.new_doc(CASE, person=self.person_b).insert().name
		frappe.set_user(self.pastor_a)

		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc(CASE, person=self.person_b).insert()
		self.assertEqual(frappe.new_doc(CASE, person=self.person_a).insert().church, self.branch_a)

		frappe.local.form_dict = frappe._dict(
			data=json.dumps({"person": self.person_a, "church": self.branch_a})
		)
		with self.assertRaises(frappe.PermissionError):
			update_doc(CASE, theirs)
		self.assertEqual(frappe.db.get_value(CASE, theirs, "church"), self.branch_b)
