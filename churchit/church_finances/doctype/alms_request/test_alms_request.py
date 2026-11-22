# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import patch

import frappe
import frappe.share
from frappe.exceptions import ValidationError
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.alms_request.alms_request import create_expense
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.doctype.note_category.note_category import BENEVOLENCE
from churchit.church_people.privacy import ANONYMIZED, anonymize
from churchit.church_people.test_merge import make_family
from churchit.patches.v1_0 import distribute_paid_approved_alms_requests, retitle_alms_requests
from churchit.portal.care import save_alms_request
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

	def test_create_expense_requires_an_amount(self):
		alms = self._make_request(expense_type=self.expense_type)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_a_negative_amount_is_refused_and_no_expense_is_made_for_zero(self):
		with self.assertRaises(ValidationError):
			self._make_request(amount=-250, expense_type=self.expense_type)

		alms = self._make_request(amount=0, expense_type=self.expense_type)
		with self.assertRaises(ValidationError):
			create_expense(alms.name)

	def test_a_cancelled_expense_does_not_block_a_new_one(self):
		alms = self._make_request(amount=100, expense_type=self.expense_type)
		first = create_expense(alms.name)
		frappe.get_doc("Expense", first).cancel()

		second = create_expense(alms.name)

		self.assertNotEqual(first, second)
		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "associated_expense"), second)

	def test_a_submitted_expense_blocks_a_second_one(self):
		alms = self._make_request(amount=100, expense_type=self.expense_type)
		create_expense(alms.name)

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
		# No Expense links to the recipient, so Remove Personal Data could not reach a name there.
		self.assertEqual(expense.title, f"Alms Request {alms.name}")

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


class TestAlmsRequestTitle(RollbackEachTest):
	"""The title is the recipient's name: the amount and status have their own columns."""

	def make_request(self, recipient, requestor):
		return frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": recipient,
				"requestor": requestor,
				"description": "_Test alms title",
				"amount": 200,
				"status": "Approved",
			}
		).insert(ignore_permissions=True)

	def test_the_title_is_the_recipients_name(self):
		recipient = make_person("_Test Alms", "Recipient")
		alms = self.make_request(recipient.name, make_person("_Test Alms", "Deacon").name)

		self.assertEqual(alms.title, "_Test Alms Recipient")

	def test_the_patch_retitles_an_old_request_and_its_expense_and_can_run_again(self):
		recipient = make_person("_Test Alms", "Retitled")
		alms = self.make_request(recipient.name, recipient.name)
		frappe.db.set_value("Alms Request", alms.name, "title", "_Test Alms Retitled - 200 - Approved")
		expense = frappe.get_doc(
			{"doctype": "Expense", "title": "Alms: _Test Alms Retitled - 200 - Approved", "amount": 200}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.db.set_value("Alms Request", alms.name, "associated_expense", expense.name)

		retitle_alms_requests.execute()
		retitle_alms_requests.execute()

		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "title"), "_Test Alms Retitled")
		self.assertEqual(frappe.db.get_value("Expense", expense.name, "title"), f"Alms Request {alms.name}")

	def test_removing_the_recipients_personal_data_leaves_no_name_in_the_title(self):
		recipient = make_person("_Test Alms", "Forgotten")
		alms = self.make_request(recipient.name, make_person("_Test Alms", "Deacon").name)

		anonymize(recipient.name)

		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "title"), ANONYMIZED)

	def make_family_request(self, *members):
		"""A request first for someone else, then changed to the family of *members*, so its history names it."""
		family = make_family("_Test Kin - _Test Alms Anne", *members)
		alms = self.make_request(
			make_person("_Test Alms", "Other").name, make_person("_Test Alms", "Deacon").name
		)
		alms.update({"recipient_type": "Family", "recipient": family.name})
		# Frappe skips Version rows in tests unless a save asks for them.
		alms.save(ignore_permissions=True, ignore_version=False)
		self.assertEqual(alms.title, "_Test Kin - _Test Alms Anne")
		return alms

	def get_history(self, alms) -> str:
		return "".join(
			frappe.get_all("Version", {"ref_doctype": "Alms Request", "docname": alms.name}, pluck="data")
		)

	def test_a_family_that_keeps_members_loses_the_first_name_from_its_requests(self):
		person = make_person("_Test Alms Anne", "_Test Kin")
		alms = self.make_family_request(person, make_person("_Test Alms Wife", "_Test Kin"))

		anonymize(person.name)

		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "title"), "_Test Kin")
		self.assertNotIn("_Test Alms Anne", self.get_history(alms))

	def test_a_family_with_no_one_left_is_anonymized_on_its_requests(self):
		person = make_person("_Test Alms Anne", "_Test Kin")
		alms = self.make_family_request(person)

		anonymize(person.name)

		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "title"), ANONYMIZED)
		self.assertNotIn("_Test Alms Anne", self.get_history(alms))

	def test_removing_the_recipients_personal_data_leaves_no_name_in_the_history(self):
		recipient = make_person("_Test Alms", "Moved")
		alms = self.make_request(recipient.name, make_person("_Test Alms", "Deacon").name)
		alms.description = "Rent for _Test Alms Moved"
		# Frappe skips Version rows in tests unless a save asks for them.
		alms.save(ignore_permissions=True, ignore_version=False)
		history = {"ref_doctype": "Alms Request", "docname": alms.name}
		self.assertIn("_Test Alms Moved", "".join(frappe.get_all("Version", history, pluck="data")))

		anonymize(recipient.name)

		self.assertNotIn("_Test Alms Moved", "".join(frappe.get_all("Version", history, pluck="data")))


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


class TestReviewedAlmsRequests(RollbackEachTest):
	"""A member changes or deletes their request only until the care team reviews it, and never sets its status."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.member = ensure_user("_test_alms_reviewed_member@example.com", "Reviewed Member")
		cls.person = make_person("_Test Alms", "Reviewed Member", user=cls.member).name
		cls.care = ensure_user(
			"_test_alms_reviewed_care@example.com", "Reviewed Care", roles=("Church Pastoral Care",)
		)
		fund = _ensure("Fund", {"fund": "_Test Alms Fund"}, {"fund": "_Test Alms Fund"})
		cls.expense_type = _ensure(
			"Expense Type",
			{"type": "_Test Alms Expense Type"},
			{"type": "_Test Alms Expense Type", "fund": fund},
		)

	def send(self, **values):
		"""A request the member sends with their own right, as REST saves it."""
		frappe.set_user(self.member)
		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.person,
				"description": "_Test reviewed request",
				"amount": 150,
				**values,
			}
		).insert()
		frappe.set_user("Administrator")
		return alms

	def review(self, alms, status="Approved"):
		frappe.set_user(self.care)
		alms = frappe.get_doc("Alms Request", alms.name)
		alms.update({"status": status, "expense_type": self.expense_type})
		alms.save()
		frappe.set_user("Administrator")
		return alms

	def test_a_member_cannot_set_the_status(self):
		alms = self.send(status="Approved")
		self.assertEqual(alms.status, "Pending")

		frappe.set_user(self.member)
		alms.status = "Distributed"
		alms.save()
		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "status"), "Pending")

	def test_a_member_changes_a_pending_request(self):
		alms = self.send()

		frappe.set_user(self.member)
		alms.amount = 200
		alms.save()
		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "amount"), 200)

	def test_a_member_cannot_change_or_delete_a_reviewed_request(self):
		for status in ("Approved", "Declined"):
			with self.subTest(status=status):
				alms = self.review(self.send(), status)

				frappe.set_user(self.member)
				alms.amount = 1500
				with self.assertRaises(frappe.PermissionError):
					alms.save()
				# on_trash refuses it even for a delete that skips the permission check.
				with self.assertRaises(frappe.PermissionError):
					frappe.delete_doc("Alms Request", alms.name, ignore_permissions=True)

				frappe.set_user("Administrator")
				self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "amount"), 150)

	def test_the_care_team_changes_a_reviewed_request(self):
		alms = self.review(self.send())

		frappe.set_user(self.care)
		alms.amount = 120
		alms.save()
		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "amount"), 120)

	def test_paying_an_approved_request_distributes_it(self):
		alms = self.review(self.send())

		expense = create_expense(alms.name)

		self.assertEqual(
			frappe.db.get_value("Alms Request", alms.name, ["associated_expense", "status"]),
			(expense, "Distributed"),
		)

	def test_a_paid_request_stays_until_its_expense_is_cancelled(self):
		alms = self.review(self.send())
		expense = create_expense(alms.name)

		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Alms Request", alms.name)

		frappe.get_doc("Expense", expense).cancel()
		frappe.delete_doc("Alms Request", alms.name)
		self.assertFalse(frappe.db.exists("Alms Request", alms.name))

	def test_the_waiting_list_holds_the_requests_that_wait_for_someone(self):
		pending, approved = self.send(), self.review(self.send())
		declined = self.review(self.send(), "Declined")
		paid = self.review(self.send())
		create_expense(paid.name)
		unpaid = self.review(self.send())
		frappe.get_doc("Expense", create_expense(unpaid.name)).cancel()
		names = [pending.name, approved.name, declined.name, paid.name, unpaid.name]

		report = json.loads(frappe.db.get_value("Report", "Pending Alms Requests", "json"))["filters"]
		card = json.loads(frappe.db.get_value("Number Card", "Pending Alms Requests", "filters_json"))
		for filters in (report, [row[:4] for row in card]):
			waiting = frappe.get_all(
				"Alms Request", filters=[*filters, ["Alms Request", "name", "in", names]], pluck="name"
			)
			self.assertCountEqual(waiting, [pending.name, approved.name, unpaid.name])

	def test_the_form_offers_create_expense_again_once_the_expense_is_cancelled(self):
		alms = self.review(self.send())
		expense = frappe.get_doc("Expense", create_expense(alms.name))

		for action, is_paid in ((None, True), (expense.cancel, False)):
			if action:
				action()
			request = frappe.get_doc("Alms Request", alms.name)
			request.run_method("onload")
			self.assertEqual(request.get_onload().is_paid, is_paid)

	def test_the_patch_distributes_an_old_approved_request_that_an_expense_pays(self):
		paid = self.review(self.send())
		create_expense(paid.name)
		frappe.db.set_value("Alms Request", paid.name, "status", "Approved")
		unpaid = self.review(self.send())
		frappe.get_doc("Expense", create_expense(unpaid.name)).cancel()

		distribute_paid_approved_alms_requests.execute()
		distribute_paid_approved_alms_requests.execute()

		self.assertEqual(frappe.db.get_value("Alms Request", paid.name, "status"), "Distributed")
		self.assertEqual(frappe.db.get_value("Alms Request", unpaid.name, "status"), "Approved")


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


class TestRequestorFromTheLogin(RollbackEachTest):
	"""The member app does not send Requester, so the server fills it from the signed-in person."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.member = ensure_user("_test_alms_web_member@example.com", "Web Member")
		cls.member_person = make_person("_Test Alms", "Web Member", user=cls.member).name
		cls.staff = ensure_user("_test_alms_web_staff@example.com", "Web Staff", roles=("Church Manager",))
		cls.staff_person = make_person("_Test Alms", "Web Staff", user=cls.staff).name
		cls.unlinked = ensure_user("_test_alms_web_unlinked@example.com", "Web Unlinked")
		cls.unlinked_staff = ensure_user(
			"_test_alms_web_unlinked_staff@example.com", "Web Unlinked Staff", roles=("Church Manager",)
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def send_through_the_app(self, user):
		frappe.set_user(user)
		saved = save_alms_request("Person", self.member_person, "_Test app request", 40)
		return frappe.get_doc("Alms Request", saved["name"])

	def test_a_member_is_named_as_the_requester(self):
		request = self.send_through_the_app(self.member)
		self.assertEqual(request.requestor, self.member_person)

	def test_staff_with_a_person_are_named_as_the_requester(self):
		request = self.send_through_the_app(self.staff)
		self.assertEqual(request.requestor, self.staff_person)

	def test_a_member_with_no_person_is_told_so(self):
		"""The app refuses a login with no Person first; REST reaches the rule here."""
		frappe.set_user(self.unlinked)
		values = {"recipient_type": "Person", "recipient": self.member_person, "description": "_Test REST"}
		with self.assertRaisesRegex(ValidationError, "not linked to a person"):
			frappe.get_doc({"doctype": "Alms Request", **values}).insert()
		for user in (self.unlinked, self.unlinked_staff):
			with self.subTest(user=user), self.assertRaises(frappe.PermissionError):
				self.send_through_the_app(user)

	def test_staff_in_the_desk_still_choose_the_requester(self):
		frappe.set_user(self.unlinked_staff)
		request = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.member_person,
				"requestor": self.staff_person,
				"description": "_Test desk request",
			}
		).insert()
		self.assertEqual(request.requestor, self.staff_person)
