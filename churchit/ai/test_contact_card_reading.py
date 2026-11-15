# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Reading a returned contact verification card with AI: who may send a card, what the prompt holds and
what the check keeps of an answer. Tests never call a model: the check runs on a written answer, and
the run test patches Flow's new_session (test_runner.flow_session) and needs Flow."""

import base64

import frappe

from churchit.ai import contact_card_reading
from churchit.ai.contact_card_reading import check_card, get_card_lines, read_card
from churchit.ai.flow_switch import get_recommended_knowledge_doctypes
from churchit.ai.opt_outs import CHURCH_FIELD
from churchit.ai.switch import SETTINGS
from churchit.ai.test_runner import FlowRunnerTestCase, flow_session, set_ai
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.contact_cards import VERIFICATION, get_details
from churchit.patches.v1_0 import block_contact_verifications_from_knowledge
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches, pop_logs

EDITOR_A = "_test_reading_editor_a@example.com"
EDITOR_B = "_test_reading_editor_b@example.com"
WEBSITE_USER = "_test_reading_website@example.com"
# A 1x1 PNG.
PNG = base64.b64decode(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ReadingCase(RollbackEachTest):
	"""Two churches, a People Editor in each, and a person of the first church with a card on its list."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		for email, church in ((EDITOR_A, cls.church_a), (EDITOR_B, cls.church_b)):
			ensure_user(email, "Reading", ("Church Staff", "Church People Editor"))
			set_user_church(email, church)
		ensure_user(WEBSITE_USER, "Reading", roles=())

	def setUp(self):
		super().setUp()
		set_ai(1)
		self.person = make_person(
			"_Test Reading",
			"Ann",
			church=self.church_a,
			emails=[{"email_address": "_test.reading.ann@example.com", "is_primary": 1}],
			phones=[
				{"phone_number": f"+1 217 555 019{digit}", "phone_type": "Mobile", "is_primary": digit == 1}
				for digit in range(1, 6)
			],
		)
		self.verification = frappe.get_doc(
			{
				"doctype": VERIFICATION,
				"title": "_Test Reading",
				"church": self.church_a,
				"people": [{"person": self.person.name}],
			}
		).insert()
		self.photo = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "card.png",
				"content": PNG,
				"is_private": 1,
				"attached_to_doctype": VERIFICATION,
				"attached_to_name": self.verification.name,
			}
		).insert()

	def answer(self, **values):
		return {"verification": self.verification.name, "person": self.person.name, **values}

	def read(self, user: str = EDITOR_A):
		frappe.set_user(user)
		try:
			return read_card(self.verification.name, self.person.name, self.photo.file_url)
		finally:
			frappe.set_user("Administrator")


class TestContactCardReading(ReadingCase):
	def test_the_check_keeps_marks_on_printed_lines_and_valid_values_only(self):
		result = check_card(
			self.answer(
				lines=[
					{"line": 1, "mark": "wrong", "correction": "_test.reading.new@example.com"},
					{"line": 2, "mark": "wrong", "correction": "not a phone"},
					{"line": 3, "mark": "wrong"},
					{"line": 9, "mark": "wrong", "correction": "nobody@example.com"},
					{"line": [1], "mark": "wrong"},
					{"line": True, "mark": "right"},
					{"line": 1, "mark": "maybe"},
				],
				new_emails=[
					{"email": "not an email"},
					{"email": "_test.reading.more@example.com", "main": True},
				],
				new_phones=[{"phone": "+1 217 555 0182", "kind": "home"}],
				birthday={"month": 2, "day": 29},
				texting="YES",
				status="Updated",
			)
		)

		email, removed = result["lines"]
		self.assertEqual((email["item"], email["correction"]), ("emails", "_test.reading.new@example.com"))
		self.assertEqual((removed["line"], removed["item"], removed["correction"]), (3, "phones", None))
		self.assertEqual(
			result["new_emails"], [{"email_address": "_test.reading.more@example.com", "is_primary": True}]
		)
		self.assertEqual(result["new_phones"][0]["phone_type"], "Home")
		self.assertEqual(result["birthday"], {"birthday": "2000-02-29", "birthday_year_unknown": 1})
		self.assertEqual(result["texting"], "Yes")
		self.assertNotIn("status", result)

	def test_the_prompt_holds_only_the_printed_lines_and_never_the_emergency_contact(self):
		self.person.db_set("emergency_contact_name", "_Test Reading Contact")
		lines = get_card_lines(get_details(self.verification, frappe.get_doc("Person", self.person.name)))
		self.assertEqual([line["item"] for line in lines], ["emails", "phones", "phones", "phones"])
		self.assertNotIn("_Test Reading Contact", str(lines))

	def test_a_card_that_shows_the_emergency_contact_is_never_read(self):
		self.verification.db_set("show_emergency_contact", 1)
		with self.assertRaises(frappe.ValidationError):
			check_card(self.answer(lines=[]))
		with self.assertRaises(frappe.ValidationError):
			self.read()

	def test_an_answer_that_names_no_card_or_another_card_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			check_card({"lines": []})
		with self.assertRaises(frappe.ValidationError):
			check_card(self.answer(person=make_person("_Test Reading", "Other").name))

	def test_nothing_is_read_while_ai_is_off_or_for_a_website_user(self):
		set_ai(0)
		with self.assertRaises(frappe.PermissionError):
			self.read()
		set_ai(1)
		with self.assertRaises(frappe.PermissionError):
			self.read(WEBSITE_USER)

	def test_another_churchs_card_and_a_church_that_keeps_away_are_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.read(EDITOR_B)
		frappe.db.set_value("Church", self.church_a, CHURCH_FIELD, 1)
		with self.assertRaises(frappe.PermissionError):
			self.read()

	def test_the_knowledge_patch_blocks_the_verification_and_keeps_an_emptied_list(self):
		self.addCleanup(frappe.clear_document_cache, SETTINGS, SETTINGS)
		self.assertIn(VERIFICATION, get_recommended_knowledge_doctypes())
		settings = frappe.get_single(SETTINGS)
		settings.set("blocked_knowledge_doctypes", [{"document_type": "Connection Card"}])
		settings.save()
		block_contact_verifications_from_knowledge.execute()
		self.assertEqual(frappe.get_single(SETTINGS).blocked_doctypes, {"Connection Card", VERIFICATION})

		settings = frappe.get_single(SETTINGS)
		settings.set("blocked_knowledge_doctypes", [])
		settings.save()
		block_contact_verifications_from_knowledge.execute()
		self.assertEqual(frappe.get_single(SETTINGS).blocked_doctypes, set())


class TestReadCardRun(ReadingCase, FlowRunnerTestCase):
	def setUp(self):
		super().setUp()
		self.set_labels("No training", "Local")
		frappe.get_doc("User", EDITOR_A).add_roles("Flow User")

	def test_the_photo_goes_as_an_attachment_with_an_access_log_row_first(self):
		filters = {"reference_document": self.person.name, "method": f"AI: {contact_card_reading.FEATURE}"}
		pop_logs("Access Log", filters)
		with flow_session() as new_session:
			self.read()

		self.assertEqual(new_session.call_args.args[0].name, "churchit/Writer")
		[prompt] = new_session.return_value.chat.call_args.args
		self.assertIn(self.person.name, prompt)
		self.assertEqual(
			new_session.return_value.chat.call_args.kwargs,
			{
				"attachments": [self.photo.name],
				"reference_doctype": "Person",
				"reference_name": self.person.name,
				"on_complete": "churchit.ai.runner.complete",
			},
		)
		self.assertEqual(len(pop_logs("Access Log", filters)), 1)
