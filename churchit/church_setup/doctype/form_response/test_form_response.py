# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import set_request
from frappe.website.doctype.web_form.web_form import accept
from frappe.website.serve import get_response

from churchit.church_finances.doctype.giving_settings.test_giving_settings import make_gateway
from churchit.church_finances.doctype.online_donation.test_online_donation import ensure_online_payment_type
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_payment import (
	alerts,
	bind_finance,
	collections_of,
	log_charge,
)
from churchit.church_people.followup import FORM_SUBMITTED
from churchit.church_people.membership import VISITOR
from churchit.church_people.privacy import anonymize
from churchit.church_setup.doctype.form_response.form_response import FORM, NEW, PROCESSED, get_form, pay
from churchit.questions import get_fields
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
)
from churchit.tests.test_questions import make_question_set

WEB_FORM = "form"
EMAIL = "_test_form_guest@example.com"
ANSWERS = [{"question": "your_name", "answer": "Ann"}, {"question": "agrees_to_the_rules", "answer": 1}]


class FormResponseTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.question_set = make_question_set("_Test Form Camp", church=cls.branch_a, publish_as_form=1).name
		cls.other_set = make_question_set("_Test Form Choir", church=cls.branch_a, publish_as_form=1).name
		cls.member = ensure_user("_test_form_member@example.com", "FormMember")
		cls.member_person = make_person("_Test Form", "Member", church=cls.branch_b, user=cls.member).name

	def setUp(self):
		super().setUp()
		# A response queues its processing after the commit a test never makes; tests call process() themselves.
		enqueue = patch("frappe.enqueue_doc")
		self.enqueue_doc = enqueue.start()
		self.addCleanup(enqueue.stop)
		frappe.db.set_single_value("People Settings", "match_threshold", 80)

	def send(self, user="Guest", **values):
		"""Send the form web form as *user* and return the response it made."""
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)
		frappe.local.form_dict = frappe._dict()
		frappe.set_user(user)
		try:
			data = {
				"question_set": self.question_set,
				"first_name": "_Test Form",
				"last_name": "Guest",
				"email": EMAIL,
				"answers": ANSWERS,
				**values,
			}
			return frappe.get_doc("Form Response", accept(WEB_FORM, json.dumps(data)).name)
		finally:
			frappe.set_user("Administrator")

	def get_form_as(self, user, question_set):
		frappe.set_user(user)
		try:
			return get_form(question_set)
		finally:
			frappe.set_user("Administrator")


class TestFormResponseWebForm(FormResponseTestCase):
	def test_a_guest_answers_a_published_set(self):
		response = self.send()

		self.assertEqual((response.status, response.owner, response.person), (NEW, "Guest", None))
		self.assertEqual(response.church, self.branch_a)
		self.assertEqual(
			[(row.question, row.label, row.answer) for row in response.answers],
			[
				("your_name", "Your name", "Ann"),
				("needs_a_ride", "Needs a ride", "No"),
				("agrees_to_the_rules", "Agrees to the rules", "Yes"),
			],
		)
		self.assertEqual(frappe.db.count("Form Response", {"question_set": self.question_set}), 1)
		self.assertEqual(self.enqueue_doc.call_args.args, ("Form Response", response.name, "process"))
		self.assertTrue(self.enqueue_doc.call_args.kwargs["enqueue_after_commit"])

	def test_the_answers_are_rebuilt_from_the_set(self):
		forged = [{**ANSWERS[0], "label": "Forged"}, ANSWERS[1]]
		self.assertEqual(self.send(answers=forged).answers[0].label, "Your name")

		with self.assertRaises(frappe.ValidationError):
			self.send(answers=[*ANSWERS, {"question": "not_asked", "answer": "x"}])
		with self.assertRaises(frappe.MandatoryError):
			self.send(answers=ANSWERS[:1])

	def test_an_unpublished_set_is_refused_by_the_endpoint_and_on_save(self):
		frappe.db.set_value("Question Set", self.question_set, "publish_as_form", 0)

		with self.assertRaises(frappe.PermissionError):
			self.get_form_as("Guest", self.question_set)
		with self.assertRaises(frappe.PermissionError):
			self.get_form_as("Guest", "QSET-NOT-THERE")
		with self.assertRaises(frappe.PermissionError):
			self.send()
		self.assertFalse(frappe.db.exists("Form Response", {"question_set": self.question_set}))

	def test_a_members_only_set_is_refused_for_a_guest(self):
		frappe.db.set_value("Question Set", self.question_set, "members_only", 1)

		with self.assertRaises(frappe.PermissionError):
			self.get_form_as("Guest", self.question_set)
		with self.assertRaises(frappe.PermissionError):
			self.send()
		self.assertTrue(self.get_form_as(self.member, self.question_set)["fields"])

	def test_a_members_only_set_is_refused_for_a_login_with_no_person(self):
		frappe.db.set_value("Question Set", self.question_set, "members_only", 1)
		website_user = ensure_user("_test_form_website@example.com", "FormWebsite")

		with self.assertRaises(frappe.PermissionError):
			self.get_form_as(website_user, self.question_set)
		with self.assertRaises(frappe.PermissionError):
			self.send(website_user)
		self.assertFalse(frappe.db.exists("Form Response", {"question_set": self.question_set}))

	def test_a_member_answers_as_their_own_person(self):
		response = self.send(self.member)

		self.assertEqual((response.owner, response.person), (self.member, self.member_person))

	def test_the_endpoint_gives_a_guest_the_title_and_fields_of_a_published_set(self):
		form = self.get_form_as("Guest", self.question_set)

		self.assertEqual(
			form, {"title": "_Test Form Camp", "price": 0, "fields": get_fields(self.question_set)}
		)

	def test_the_form_names_no_other_question_set(self):
		frappe.set_user("Guest")
		query = f"question_set={self.question_set}"
		set_request(method="GET", path="form/new", query_string=query)
		frappe.local.form_dict = frappe._dict(question_set=self.question_set)

		response = get_response("form/new")
		html = response.get_data(as_text=True)

		self.assertEqual(response.status_code, 200)
		self.assertIn("form_response.get_form", html, "the page draws the questions from the endpoint")
		self.assertNotIn(self.other_set, html)
		self.assertNotIn("_Test Form Choir", html)

	def test_anonymizing_the_person_deletes_their_responses(self):
		response = self.send(self.member)

		anonymize(self.member_person)

		self.assertFalse(frappe.db.exists("Form Response", response.name))

	def test_responses_are_scoped_to_their_church(self):
		manager_a = ensure_user("_test_form_manager_a@example.com", "FormA", roles=("Church Manager",))
		make_person("_Test Form Manager", "A", church=self.branch_a, user=manager_a)
		theirs_set = make_question_set("_Test Form Theirs", church=self.branch_b, publish_as_form=1).name

		mine = self.send().name
		theirs = self.send(question_set=theirs_set).name

		self.assertEqual(frappe.db.get_value("Form Response", theirs, "church"), self.branch_b)
		assert_scoped(self, "Form Response", manager_a, mine, theirs)


class TestFormResponseFollowUp(FormResponseTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.camp_workflow = cls.make_workflow("_Test Form Camp Welcome", cls.question_set, cls.branch_a)
		cls.choir_workflow = cls.make_workflow("_Test Form Choir Welcome", cls.other_set, cls.branch_a)

	@staticmethod
	def make_workflow(name, question_set, church):
		return (
			frappe.get_doc(
				{
					"doctype": "Follow-up Workflow",
					"workflow_name": name,
					"church": church,
					"steps": [{"step": "Call"}],
					"triggers": [{"trigger": FORM_SUBMITTED, "value": question_set}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def processed(self, response):
		"""Run the job as Guest, as the web form queues it, and return the stored response."""
		frappe.set_user("Guest")
		try:
			response.process()
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc("Form Response", response.name)

	def started(self, response):
		return frappe.get_all(
			"Follow-up Card",
			filters={"source_type": "Form Response", "source_name": response.name},
			pluck="workflow",
		)

	def test_a_guests_response_adds_a_visitor(self):
		response = self.processed(self.send())

		self.assertEqual(response.status, PROCESSED)
		person = frappe.get_doc("Person", response.person)
		self.assertEqual((person.first_name, person.last_name), ("_Test Form", "Guest"))
		self.assertEqual((person.membership, person.source, person.church), (VISITOR, FORM, self.branch_a))

	def test_a_guest_of_a_shared_set_is_added_at_the_church_that_shared_it(self):
		shared = make_question_set(
			"_Test Form Shared Guest", church=self.branch_a, is_shared=1, publish_as_form=1
		).name

		response = self.processed(self.send(question_set=shared))

		self.assertEqual(response.church, "")
		self.assertEqual(frappe.db.get_value("Person", response.person, "church"), self.branch_a)

	def test_a_strong_match_is_linked_and_left_unchanged(self):
		known = make_person(
			"_Test Form", "Guest", church=self.branch_a, emails=[{"email_address": EMAIL}]
		).name

		response = self.processed(self.send())

		self.assertEqual(response.person, known)

	def test_a_response_opens_a_card_only_on_the_workflow_of_its_set(self):
		response = self.processed(self.send())

		self.assertEqual(self.started(response), [self.camp_workflow])

	def test_a_second_run_opens_no_second_card(self):
		response = self.processed(self.send())
		response.process()

		self.assertEqual(self.started(response), [self.camp_workflow])

	def test_anonymizing_a_person_whose_response_opened_a_card(self):
		response = self.processed(self.send())
		self.assertEqual(self.started(response), [self.camp_workflow])

		anonymize(response.person)

		self.assertFalse(frappe.db.exists("Form Response", response.name))
		self.assertTrue(frappe.db.exists("Follow-up Card", {"person": response.person}))

	def test_a_members_response_keeps_the_member(self):
		response = self.processed(self.send(self.member))

		self.assertEqual(response.person, self.member_person)

	def test_a_shared_set_follows_up_at_the_persons_church(self):
		shared = make_question_set("_Test Form Shared", is_shared=1, publish_as_form=1).name
		workflow = self.make_workflow("_Test Form Shared Welcome", shared, self.branch_b)

		response = self.processed(self.send(self.member, question_set=shared))

		self.assertEqual(response.church, "")
		self.assertEqual(self.started(response), [workflow])


class TestFormResponsePayment(FormResponseTestCase):
	"""A priced form takes its price once, through the same payment functions as a sign-up."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_online_payment_type()
		cls.fund_a = ensure(
			"Fund", {"fund": "_Test Form Fees A"}, {"fund": "_Test Form Fees A", "church": cls.branch_a}
		)
		cls.fund_b = ensure(
			"Fund", {"fund": "_Test Form Fees B"}, {"fund": "_Test Form Fees B", "church": cls.branch_b}
		)
		cls.finance_a = bind_finance("_test_form_finance_a@example.com", "FormFinanceA", cls.branch_a)
		cls.finance_b = bind_finance("_test_form_finance_b@example.com", "FormFinanceB", cls.branch_b)
		frappe.db.set_value("Question Set", cls.question_set, {"price": 15, "fund": cls.fund_a})
		settings = frappe.get_doc("Giving Settings")
		settings.currency = "USD"
		settings.gateways = []
		settings.append("gateways", {"payment_gateway": make_gateway("_Test Form Gateway")})
		settings.save(ignore_permissions=True)

	def pay_as_guest(self, response):
		controller = MagicMock()
		controller.get_payment_url.return_value = "https://pay.example.com/form"
		frappe.set_user("Guest")
		try:
			with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
				return pay(response.name), controller
		finally:
			frappe.set_user("Administrator")

	def call_as(self, user, method, response):
		frappe.set_user(user)
		try:
			getattr(frappe.get_doc("Form Response", response.name), method)()
		finally:
			frappe.set_user("Administrator")
		response.reload()

	def test_pay_opens_the_checkout_of_the_sets_price(self):
		url, controller = self.pay_as_guest(self.send())

		self.assertEqual(url, "https://pay.example.com/form")
		checkout = controller.get_payment_url.call_args.kwargs
		self.assertEqual(
			(checkout["amount"], checkout["currency"], checkout["title"]), (15, "USD", "_Test Form Camp")
		)

	def test_a_set_with_no_price_opens_no_payment_page(self):
		response = self.send(question_set=self.other_set)

		with self.assertRaises(frappe.ValidationError):
			self.pay_as_guest(response)
		self.assertEqual(self.get_form_as("Guest", self.other_set)["price"], 0)
		self.assertEqual(self.get_form_as("Guest", self.question_set)["price"], 15)

	def test_a_paid_response_records_one_collection_at_the_sets_church(self):
		response = self.send()
		log_charge(response, 15)

		# The gateway calls back in the payer's session, a guest's here.
		frappe.set_user("Guest")
		response.on_payment_authorized("Completed")
		frappe.set_user("Administrator")
		response.reload()

		self.assertEqual((response.payment_status, response.amount_paid), ("Paid", 15))
		rows = collections_of(response)
		self.assertEqual([(row.amount, row.fund, row.person) for row in rows], [(15, self.fund_a, None)])
		self.assertEqual(frappe.db.get_value("Collection", rows[0].parent, "church"), self.branch_a)

		self.assertEqual(alerts(self.finance_a, response), [])
		with self.assertRaises(frappe.ValidationError):
			self.pay_as_guest(response)

	def test_a_second_charge_on_a_paid_response_records_nothing_and_alerts_finance(self):
		# A checkout page opened before the first payment still takes a card.
		response = self.send()
		log_charge(response, 15)
		response.on_payment_authorized("Completed")

		log_charge(response, 15)
		frappe.get_doc("Form Response", response.name).on_payment_authorized("Completed")

		self.assertEqual(len(collections_of(response)), 1)
		self.assertEqual(len(alerts(self.finance_a, response)), 1)
		self.assertIn("charged again", alerts(self.finance_a, response)[0])
		self.assertEqual(alerts(self.finance_b, response), [])

	def test_a_shared_set_records_at_the_church_that_shared_it(self):
		shared = make_question_set(
			"_Test Form Shared Fee",
			church=self.branch_a,
			is_shared=1,
			publish_as_form=1,
			price=15,
			fund=self.fund_a,
		).name
		response = self.send(question_set=shared)
		self.assertEqual(response.church, "")
		log_charge(response, 15)

		response.on_payment_authorized("Completed")

		self.assertEqual(
			frappe.db.get_value("Collection", collections_of(response)[0].parent, "church"), self.branch_a
		)

	def test_a_charge_that_differs_from_the_price_records_nothing_and_alerts_finance(self):
		response = self.send()
		log_charge(response, 10)

		response.on_payment_authorized("Completed")
		response.reload()

		self.assertEqual((response.payment_status, collections_of(response)), ("Unpaid", []))
		self.assertEqual(len(alerts(self.finance_a, response)), 1)
		self.assertEqual(alerts(self.finance_b, response), [])

	def test_finance_records_a_refund_and_a_guest_cannot(self):
		response = self.send()
		with self.assertRaises(frappe.ValidationError):
			self.call_as(self.finance_a, "record_refund", response)
		log_charge(response, 15)
		response.on_payment_authorized("Completed")

		with self.assertRaises(frappe.PermissionError):
			self.call_as("Guest", "record_refund", response)
		self.call_as(self.finance_a, "record_refund", response)

		self.assertEqual(response.payment_status, "Refunded")

	def test_the_payment_fields_keep_what_code_stored(self):
		response = self.send()
		response.update({"payment_status": "Paid", "amount_paid": 15})
		response.save(ignore_permissions=True)

		self.assertEqual(
			frappe.db.get_value("Form Response", response.name, ["payment_status", "amount_paid"]),
			("Unpaid", 0),
		)

	def test_a_price_needs_a_fund_of_the_sets_church(self):
		with self.assertRaises(frappe.ValidationError):
			make_question_set("_Test Form No Fund", church=self.branch_a, price=5)
		with self.assertRaises(frappe.PermissionError):
			make_question_set("_Test Form Their Fund", church=self.branch_a, price=5, fund=self.fund_b)
