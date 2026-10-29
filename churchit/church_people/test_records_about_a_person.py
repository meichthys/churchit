# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A record about a person takes its church from them, so only the person's church records it.

Frappe checks the create right before the church is fetched, and a change on the record as sent, so
these tests make the calls `/api/resource` makes (`create_doc`, `update_doc`) as a user of one branch.
"""

import json

import frappe
from frappe.api.v1 import create_doc, update_doc
from frappe.utils import nowdate

from churchit.church_people.matching import Match, record_possible_duplicates
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

PAIR = "Possible Duplicate"


class TestRecordsAboutAnotherChurchesPerson(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.user = ensure_user("_test_about_manager_a@example.com", "Manager", roles=("Church Manager",))
		cls.manager = make_person("_Test About", "Manager", church=cls.branch_a, user=cls.user).name
		cls.mine = make_person("_Test About", "Mine", church=cls.branch_a).name
		cls.theirs = make_person("_Test About", "Theirs", church=cls.branch_b).name

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def rest(self, call, *args, **data):
		"""Call a REST handler of `frappe.api.v1` with *data* as the request body."""
		frappe.local.form_dict = frappe._dict(data=json.dumps(data))
		return call(*args)

	def assert_only_the_persons_church_records(self, doctype, **values):
		"""The user records about their own church's person only, and cannot take another church's record."""
		frappe.set_user(self.user)

		with self.assertRaises(frappe.PermissionError):
			self.rest(create_doc, doctype, person=self.theirs, **values)
		mine = self.rest(create_doc, doctype, person=self.mine, **values).name
		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, doctype, mine, person=self.theirs)
		# A job writes with ignore_permissions and still records it.
		theirs = (
			frappe.get_doc({"doctype": doctype, "person": self.theirs, **values})
			.insert(ignore_permissions=True)
			.name
		)
		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, doctype, theirs, person=self.mine, church=self.branch_a)

		self.assertEqual(frappe.db.get_value(doctype, mine, "person"), self.mine)
		self.assertEqual(
			frappe.db.get_value(doctype, theirs, ["person", "church"]), (self.theirs, self.branch_b)
		)

	def test_a_background_check(self):
		check_type = ensure("Background Check Type", {"type": "_Test About Check"})
		self.assert_only_the_persons_church_records("Background Check", check_type=check_type)

	def test_a_care_request(self):
		category = ensure("Care Request Type", {"type": "_Test About Need"})
		self.assert_only_the_persons_church_records("Care Request", category=category, description="Meals")

	def test_a_care_assignment(self):
		self.assert_only_the_persons_church_records(
			"Care Assignment", deacon=self.manager, start_date=nowdate()
		)

	def test_a_visitation_log(self):
		visit_type = ensure("Visit Type", {"type": "_Test About Visit"})
		self.assert_only_the_persons_church_records("Visitation Log", visit_type=visit_type)

	def test_a_possible_duplicate(self):
		"""Only matching opens pairs; a change of people may not move a pair to or from another church."""
		(mine,) = record_possible_duplicates(
			self.mine, [Match(make_person("_Test About", "Mine Too", church=self.branch_a).name, 90)]
		)
		(theirs,) = record_possible_duplicates(
			self.theirs, [Match(make_person("_Test About", "Theirs Too", church=self.branch_b).name, 90)]
		)
		frappe.set_user(self.user)

		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, PAIR, mine, person=self.theirs)
		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, PAIR, theirs, person=self.mine, church=self.branch_a)

		self.assertEqual(frappe.db.get_value(PAIR, mine, "church"), self.branch_a)
		self.assertEqual(frappe.db.get_value(PAIR, theirs, "church"), self.branch_b)
