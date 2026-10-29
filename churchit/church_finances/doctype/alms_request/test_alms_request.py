# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
import frappe.share
from frappe.exceptions import ValidationError
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.alms_request.alms_request import create_expense
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.doctype.note_category.note_category import BENEVOLENCE
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestAlmsRequest(FrappeTestCase):
	def setUp(self):
		# Expense Type is a tree doctype whose inserts commit, so keep it and its
		# Fund as persistent fixtures rather than per-test records.
		self.fund = _ensure("Fund", {"fund": "_Test Alms Fund"}, {"fund": "_Test Alms Fund"})
		self.expense_type = _ensure(
			"Expense Type",
			{"type": "_Test Alms Expense Type"},
			{"type": "_Test Alms Expense Type", "fund": self.fund},
		)
		self.person = _ensure(
			"Person", {"first_name": "_Test Alms Recipient"}, {"first_name": "_Test Alms Recipient"}
		)

	def _make_request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.person,
				"requestor": self.person,
				"description": "Needs assistance",
				"status": "Approved",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_title_combines_recipient_amount_and_status(self):
		alms = self._make_request(amount=250)
		self.assertIn("250", alms.title)
		self.assertIn("Approved", alms.title)

	def test_create_expense_requires_an_amount(self):
		alms = self._make_request(expense_type=self.expense_type)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_create_expense_requires_an_expense_type(self):
		alms = self._make_request(amount=100)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_create_expense_submits_expense_and_links_it_back(self):
		alms = self._make_request(amount=100, expense_type=self.expense_type)
		create_expense(alms.name)

		linked = frappe.db.get_value("Alms Request", alms.name, "associated_expense")
		self.assertTrue(linked)
		expense = frappe.get_doc("Expense", linked)
		self.assertEqual(expense.amount, 100)
		self.assertEqual(expense.type, self.expense_type)
		self.assertEqual(expense.docstatus, 1)

	def test_failed_create_expense_leaves_no_link(self):
		alms = self._make_request(amount=100)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)
		self.assertFalse(frappe.db.get_value("Alms Request", alms.name, "associated_expense"))

	def test_creating_an_expense_takes_a_post(self):
		"""Frappe checks the CSRF token only on a POST, and a GET from another site carries the session."""
		alms = self._make_request(amount=100, expense_type=self.expense_type)

		with (
			patch.object(frappe.local, "request", frappe._dict(method="GET"), create=True),
			patch.object(frappe.local, "form_dict", frappe._dict(alms_request_name=alms.name)),
			self.assertRaises(frappe.PermissionError),
		):
			execute_cmd("churchit.church_finances.doctype.alms_request.alms_request.create_expense")

		self.assertFalse(frappe.db.get_value("Alms Request", alms.name, "associated_expense"))


class TestAlmsRequestAcrossChurches(RollbackEachTest):
	"""Only the requestor's own church records their alms requests."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.care_b = ensure_user("_test_alms_care_b@example.com", "Care B", roles=("Church Pastoral Care",))
		set_user_church(cls.care_b, cls.branch_b)
		cls.member_b = ensure_user("_test_alms_member_b@example.com", "Member B")
		cls.person_b = make_person("_Test Alms", "Member B", church=cls.branch_b, user=cls.member_b).name
		set_user_church(cls.member_b, cls.branch_b)
		cls.person_a = make_person("_Test Alms", "Person A", church=cls.branch_a).name

	def request(self, requestor):
		return frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.person_b,
				"requestor": requestor,
				"description": "_Test across churches",
				"church": self.branch_b,
			}
		)

	def test_another_churchs_staff_cannot_record_a_request_for_a_person(self):
		"""Frappe checks the create right on the church the caller sends, before it fetches the person's."""
		frappe.set_user(self.care_b)
		with self.assertRaises(frappe.PermissionError):
			self.request(self.person_a).insert()

		self.assertEqual(self.request(self.person_b).insert().church, self.branch_b)

	def test_a_member_naming_another_churchs_person_is_refused(self):
		"""Not pinned to themselves while the request keeps the church fetched from the other person."""
		frappe.set_user(self.member_b)
		with self.assertRaises(frappe.PermissionError):
			self.request(self.person_a).insert()

	def request_with_expense_details(self):
		fund = _ensure(
			"Fund", {"fund": "_Test Alms Fund B"}, {"fund": "_Test Alms Fund B", "church": self.branch_b}
		)
		expense_type = _ensure(
			"Expense Type", {"type": "_Test Alms Type B"}, {"type": "_Test Alms Type B", "fund": fund}
		)
		alms = self.request(self.person_b)
		alms.update({"amount": 40, "expense_type": expense_type})
		return alms.insert(ignore_permissions=True)

	def test_create_expense_takes_the_requests_church(self):
		"""The Expense belongs to the request's church, not to the default church of who clicks."""
		alms = self.request_with_expense_details()
		finance = ensure_user(
			"_test_alms_root_finance@example.com", "Root Finance", roles=("Church Finance",)
		)
		set_user_church(finance, self.root)
		frappe.db.set_value("User Permission", {"user": finance, "allow": "Church"}, "hide_descendants", 0)
		frappe.clear_cache(user=finance)
		expenses = frappe.db.count("Expense")

		frappe.set_user(finance)
		create_expense(alms.name)
		expense = frappe.db.get_value("Alms Request", alms.name, "associated_expense")
		self.assertEqual(frappe.db.get_value("Expense", expense, "church"), self.branch_b)

		with self.assertRaises(ValidationError):
			create_expense(alms.name)
		self.assertEqual(frappe.db.count("Expense"), expenses + 1)

	def test_a_reader_cannot_create_an_expense(self):
		alms = self.request_with_expense_details()
		reader = ensure_user("_test_alms_reader_b@example.com", "Reader B", roles=("Church Staff",))
		set_user_church(reader, self.branch_b)
		frappe.share.add_docshare(
			"Alms Request", alms.name, reader, read=1, flags={"ignore_share_permission": True}
		)

		frappe.set_user(reader)
		self.assertTrue(frappe.has_permission("Alms Request", "read", doc=alms.name))
		frappe.local.message_log = []
		with self.assertRaises(frappe.PermissionError):
			create_expense(alms.name)
		# Every role that creates an Expense also writes Alms Requests, so the refusal must name the request.
		self.assertIn("Alms Request", frappe.local.message_log[-1]["message"])
		self.assertFalse(frappe.db.get_value("Alms Request", alms.name, "associated_expense"))


class TestCaseNoteButtons(RollbackEachTest):
	"""The form shows the Case Notes buttons to whoever may read or add a Benevolence note."""

	def case_note_rights(self, user):
		person = make_person("_Test Alms", "Case Notes").name
		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": person,
				"requestor": person,
				"description": "_Test case notes",
			}
		).insert(ignore_permissions=True)

		frappe.set_user(user)
		frappe.local.message_log = []
		alms.run_method("onload")
		onload = alms.get_onload()
		return onload.can_read_case_notes, onload.can_add_case_notes

	def test_finance_staff_get_no_case_note_buttons(self):
		"""Church Staff reads General notes, but not a Benevolence note, so it gets no button."""
		finance = ensure_user(
			"_test_alms_finance_staff@example.com", "Finance Staff", roles=("Church Finance", "Church Staff")
		)
		self.assertEqual(self.case_note_rights(finance), (False, False))
		# A refused check must not reach the form as a message dialog on every load and save.
		self.assertEqual(frappe.local.message_log, [])

	def test_managers_and_the_care_team_get_the_case_note_buttons(self):
		for role in ("Church Manager", "Church Pastoral Care"):
			user = ensure_user(f"_test_alms_{frappe.scrub(role)}@example.com", role, roles=(role,))
			with self.subTest(role=role):
				self.assertEqual(self.case_note_rights(user), (True, True))

	def test_the_buttons_follow_the_benevolence_category(self):
		"""A church that lets finance read case notes gives it View Case Notes, and still no Add Case Note."""
		category = frappe.get_doc("Note Category", BENEVOLENCE)
		category.append("view_roles", {"role": "Church Finance"})
		category.save(ignore_permissions=True)
		finance = ensure_user(
			"_test_alms_finance_staff@example.com", "Finance Staff", roles=("Church Finance", "Church Staff")
		)
		self.assertEqual(self.case_note_rights(finance), (True, False))
