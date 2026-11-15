# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Anonymizing a person also erases the AI copies about them: the AI suggestions and suggestion comments on
their records, and the Flow chats whose runs reference them or a record about them. The chat tests need
Flow."""

from unittest.mock import patch

import frappe

from churchit.ai.test_runner import PRIVATE_WORK, WRITER, WRITER_MODEL, FlowRunnerTestCase
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.followup import CARD
from churchit.church_people.privacy import anonymize_person
from churchit.church_setup.doctype.church_ai_suggestion.church_ai_suggestion import set_suggestion
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

MANAGER = "_test_privacy_ai_manager@example.com"
# Flow's call to its server, which drops the server's copy of a chat.
DELETE_SERVER_SESSION = "frappe.flow.doctype.flow_session.flow_session._delete_server_session"


def record(doctype: str, **values) -> str:
	"""A bare record of *doctype*, without its hooks: only the person it names matters here."""
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.db_insert()
	return doc.name


def make_manager() -> tuple[str, str]:
	"""A Church Manager of branch A, and branch A."""
	_root, church_a, _church_b = make_two_churches()
	ensure_user(MANAGER, "Privacy AI", ["Church Manager"])
	set_user_church(MANAGER, church_a)
	return MANAGER, church_a


def anonymize_as(user: str, person: str) -> None:
	frappe.set_user(user)
	try:
		anonymize_person(person)
	finally:
		frappe.set_user("Administrator")


class TestSuggestionComments(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.manager, cls.church = make_manager()

	def test_the_ai_suggestion_on_the_persons_card_goes_and_anothers_stays(self):
		people = [make_person(name, "_Test Privacy AI", church=self.church).name for name in ("Gone", "Kept")]
		comments = [
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"reference_doctype": CARD,
					"reference_name": record(CARD, person=person, church=self.church, status="Closed"),
					"content": "AI suggestion: the Welcome workflow.",
				}
			)
			.insert(ignore_permissions=True)
			.name
			for person in people
		]

		anonymize_as(self.manager, people[0])

		self.assertEqual([frappe.db.exists("Comment", name) for name in comments], [None, comments[1]])

	def test_the_ai_suggestion_on_the_persons_request_goes_and_anothers_stays(self):
		people = [make_person(name, "_Test Privacy AI", church=self.church).name for name in ("Gone", "Kept")]
		requests = [record("Care Request", person=person, church=self.church) for person in people]
		for request in requests:
			set_suggestion("Care Request", request, {"suggested_urgency": "High"})

		anonymize_as(self.manager, people[0])

		suggestions = [
			frappe.db.exists("Church AI Suggestion", {"reference_name": request}) for request in requests
		]
		self.assertEqual([bool(name) for name in suggestions], [False, True])

	def test_the_ai_suggestion_on_a_prayer_request_for_the_person_goes(self):
		people = [make_person(name, "_Test Privacy AI", church=self.church).name for name in ("Gone", "Kept")]
		requests = [
			record(
				"Prayer Request", recipient_type="Person", recipient=person, church=self.church, title="Pray"
			)
			for person in people
		]
		for request in requests:
			set_suggestion("Prayer Request", request, {"suggested_flags": "Health details"})

		anonymize_as(self.manager, people[0])

		suggestions = [
			frappe.db.exists("Church AI Suggestion", {"reference_name": request}) for request in requests
		]
		self.assertEqual([bool(name) for name in suggestions], [False, True])


class TestAIChats(FlowRunnerTestCase):
	"""The chats of churchit's AI runs, made as Brief Me, Draft Note and a suggestion make them. Needs Flow."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.manager, cls.church = make_manager()

	def make_chat(self, agent: str, reference_doctype: str, reference_name: str) -> str:
		session = {"doctype": "Flow Session", "agent": agent, "model": WRITER_MODEL, "title": "Brief me"}
		session = frappe.get_doc(session).insert(ignore_permissions=True).name
		run = {"session": session, "status": "Completed", "input": "Prompt", "output": "{}"}
		frappe.get_doc(
			{
				"doctype": "Flow Run",
				**run,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
			}
		).insert(ignore_permissions=True)
		return session

	def test_the_chats_about_the_person_go_and_anothers_stay(self):
		person, other = (
			make_person(name, "_Test Privacy AI", church=self.church).name for name in ("Gone", "Kept")
		)
		note = record("Person Note", person=person, church=self.church, note="<p>Visited.</p>")
		prayer = record("Prayer Request", requestor=person, church=self.church, title="Pray")
		prayer_for = record(
			"Prayer Request", recipient_type="Person", recipient=person, church=self.church, title="Pray"
		)
		gone = [
			self.make_chat(WRITER, "Person", person),
			self.make_chat(PRIVATE_WORK, "Person Note", note),
			self.make_chat(PRIVATE_WORK, "Prayer Request", prayer),
			self.make_chat(PRIVATE_WORK, "Prayer Request", prayer_for),
		]
		kept = self.make_chat(WRITER, "Person", other)

		with patch(DELETE_SERVER_SESSION) as delete_server_session:
			anonymize_as(self.manager, person)

		self.assertEqual(sorted(call.args[0] for call in delete_server_session.call_args_list), sorted(gone))
		self.assertFalse([name for name in gone if frappe.db.exists("Flow Session", name)])
		self.assertFalse(frappe.db.exists("Flow Run", {"session": ("in", gone)}))
		self.assertFalse(
			frappe.db.exists(
				"Deleted Document", {"deleted_doctype": "Flow Session", "deleted_name": ("in", gone)}
			)
		)
		self.assertTrue(frappe.db.exists("Flow Session", kept))
		self.assertTrue(frappe.db.exists("Flow Run", {"session": kept}))
