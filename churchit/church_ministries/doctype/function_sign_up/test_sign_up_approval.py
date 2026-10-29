# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	PENDING,
	WAITLISTED,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

SIGN_UP = "Function Sign-Up"


class TestSignUpApproval(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.editor = ensure_user("_test_approver@example.com", "Approver", roles=("Church People Editor",))
		cls.member = ensure_user("_test_approval_member@example.com", "Member")
		cls.member_person = make_person("_Test Approval", "Member", user=cls.member).name
		cls.people = [make_person("_Test Approval", name).name for name in ("Ann", "Ben")]

	def make_function(self, **values):
		return make_function("_Test Approval", allow_sign_ups=1, sign_up_requires_approval=1, **values).name

	def as_user(self, user, method, sign_up):
		frappe.set_user(user)
		try:
			getattr(frappe.get_doc(SIGN_UP, sign_up.name), method)()
		finally:
			frappe.set_user("Administrator")
		sign_up.reload()

	def test_a_sign_up_waits_for_approval_and_keeps_its_seat(self):
		function = self.make_function(capacity=1)
		waiting = make_sign_up(function, self.people[0])

		self.assertEqual((waiting.status, waiting.hold_expires_on), (PENDING, None))
		self.assertEqual(make_sign_up(function, self.people[1]).status, WAITLISTED)

	def test_a_registrant_cannot_approve_their_own_sign_up(self):
		function = self.make_function()
		frappe.set_user(self.member)
		mine = frappe.get_doc({"doctype": SIGN_UP, "function": function}).insert()
		frappe.set_user("Administrator")

		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.member, "approve", mine)
		self.assertEqual(frappe.db.get_value(SIGN_UP, mine.name, "status"), PENDING)

	def test_a_people_editor_approves_a_sign_up_with_nothing_due(self):
		sign_up = make_sign_up(self.make_function(), self.people[0])
		self.as_user(self.editor, "approve", sign_up)

		self.assertEqual((sign_up.status, sign_up.approved_by), (CONFIRMED, self.editor))
		attendance = frappe.get_doc("Function", sign_up.function).attendance
		self.assertEqual([row.person for row in attendance], [self.people[0]])

	def test_approving_a_sign_up_with_an_amount_due_holds_it_for_payment(self):
		function = self.make_function(selections=[{"selection": "Adult", "price": 30}])
		sign_up = make_sign_up(
			function, self.people[0], attendees=[{"person": self.people[0], "selection": "Adult"}]
		)
		self.assertFalse(sign_up.hold_expires_on)

		self.as_user(self.editor, "approve", sign_up)
		self.assertEqual((sign_up.status, sign_up.approved_by), (PENDING, self.editor))
		self.assertTrue(sign_up.hold_expires_on)
		with self.assertRaises(frappe.ValidationError):
			self.as_user(self.editor, "approve", sign_up)

	def test_an_approved_sign_up_that_grows_waits_for_approval_again(self):
		sign_up = make_sign_up(self.make_function(), self.people[0])
		self.as_user(self.editor, "approve", sign_up)

		sign_up.append("attendees", {"person": self.people[1]})
		sign_up.save(ignore_permissions=True)
		self.assertEqual((sign_up.status, sign_up.approved_by), (PENDING, None))

	def test_a_declined_sign_up_gives_its_seats_to_the_oldest_waiting_party(self):
		function = self.make_function(capacity=1)
		declined = make_sign_up(function, self.people[0])
		waiting = make_sign_up(function, self.people[1])

		self.as_user(self.editor, "decline", declined)
		waiting.reload()
		self.assertEqual(declined.status, CANCELLED)
		self.assertEqual((waiting.status, waiting.hold_expires_on), (PENDING, None))

	def test_only_a_sign_up_waiting_for_approval_is_approved_or_declined(self):
		confirmed = make_sign_up(make_function("_Test No Approval", allow_sign_ups=1).name, self.people[0])
		for method in ("approve", "decline"):
			with self.assertRaises(frappe.ValidationError):
				self.as_user(self.editor, method, confirmed)
		self.assertEqual(confirmed.status, CONFIRMED)


class TestSignUpApprovalChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch_a, branch_b = make_two_churches()
		cls.editor_a = ensure_user(
			"_test_approver_a@example.com", "Approver", roles=("Church People Editor",)
		)
		make_person("_Test Approver", "A", church=branch_a, user=cls.editor_a)
		function_b = make_function(
			"_Test Approval B", church=branch_b, allow_sign_ups=1, sign_up_requires_approval=1
		)
		cls.theirs = make_sign_up(
			function_b.name, make_person("_Test Approval", "B", church=branch_b).name
		).name

	def test_an_editor_cannot_approve_or_decline_another_churches_sign_up(self):
		frappe.set_user(self.editor_a)
		for method in ("approve", "decline"):
			with self.assertRaises(frappe.PermissionError):
				getattr(frappe.get_doc(SIGN_UP, self.theirs), method)()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(SIGN_UP, self.theirs, "status"), PENDING)
