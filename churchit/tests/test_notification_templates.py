# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Shipped notifications rendered the way Frappe sends them.

A field name the document does not have renders as blank rather than failing,
so a wrong one goes unnoticed until someone reads the email.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.email.doctype.notification.notification import clear_notification_cache, get_context
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.alms_request import alms_request
from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.church_task import church_task
from churchit.church_prayers.doctype.prayer_request import prayer_request
from churchit.church_prayers.prayer_access import is_prayer_team_only
from churchit.patches.v1_0 import add_prayer_and_alms_notifications
from churchit.tests.helpers import ensure, ensure_user, make_person, make_two_churches


def shipped_templates(module, name):
	"""The notification's JSON, and its Markdown file, which a standard notification sends instead."""
	folder = Path(frappe.get_app_path("churchit", module, "notification", frappe.scrub(name)))
	notification = json.loads((folder / f"{frappe.scrub(name)}.json").read_text())
	markdown = folder / f"{frappe.scrub(name)}.md"
	return notification, markdown.read_text() if markdown.exists() else None


class TestNotificationTemplates(FrappeTestCase):
	def test_every_shipped_condition_is_marked_python(self):
		"""Migrate syncs a notification without field defaults, and Frappe skips a condition whose type is unset."""
		unmarked = [
			path.stem
			for path in Path(frappe.get_app_path("churchit")).glob("*/notification/*/*.json")
			if (notification := json.loads(path.read_text())).get("condition")
			and notification.get("condition_type") != "Python"
		]
		self.assertEqual(unmarked, [])

	def test_expense_pending_approval_names_the_fund_and_notes(self):
		fund = ensure("Fund", {"fund": "_Test Notice Fund"})
		expense = frappe.get_doc(
			{"doctype": "Expense", "amount": 25, "associated_fund": fund, "notes": "_Test hall repairs"}
		)
		notification, markdown = shipped_templates("church_finances", "Expense Pending Approval")

		for template in (notification["message"], markdown):
			rendered = frappe.render_template(template, get_context(expense))
			self.assertIn("_Test Notice Fund", rendered)
			self.assertIn("_Test hall repairs", rendered)

	def test_position_term_ending_names_the_person_and_position(self):
		position = ensure("Position Type", {"position": "_Test Notice Elder"})
		person = make_person("_Test Notice", "Holder")
		person.append(
			"positions", {"position": position, "start_date": "2030-01-01", "end_date": "2031-01-01"}
		)
		person.save(ignore_permissions=True)
		context = get_context(person.positions[0])
		notification, _markdown = shipped_templates("church_communications", "Position Term Ending")

		for template in (notification["subject"], notification["message"]):
			rendered = frappe.render_template(template, context)
			self.assertIn("_Test Notice Elder", rendered)
			self.assertIn("_Test Notice Holder", rendered)

	def test_visitation_follow_up_due_reaches_the_visitor(self):
		"""Visited By holds a Person, which Frappe would drop as a recipient for not being an email."""
		visitor = make_person("_Test Notice", "Visitor")
		visitor.append("emails", {"email_address": "_test_notice_visitor@example.com", "is_primary": 1})
		visitor.save(ignore_permissions=True)
		visit = frappe.get_doc(
			{
				"doctype": "Visitation Log",
				"person": make_person("_Test Notice", "Visited").name,
				"visited_by": visitor.name,
				"status": "Scheduled",
			}
		)
		notification, _markdown = shipped_templates("church_communications", "Visitation Follow-Up Due")

		_recipients, cc, _bcc = frappe.get_doc(notification).get_list_of_recipients(visit, get_context(visit))

		self.assertIn("_test_notice_visitor@example.com", cc)


class TestShippedEmailTemplates(FrappeTestCase):
	def test_every_shipped_email_template_sends_a_body(self):
		"""An HTML template sends its HTML body, so text left in the plain body goes out as nothing."""
		folder = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))
		for source in sorted(folder.glob("*/*.json")):
			template = frappe.get_doc(json.loads(source.read_text()))
			with self.subTest(template.name):
				message = template.get_formatted_email({"first_name": "_Test Reader", "assignments": []})[
					"message"
				]
				self.assertIn("<p>", message)


class TestChurchTaskDueNotification(FrappeTestCase):
	def test_the_seeded_message_names_the_task(self):
		frappe.delete_doc_if_exists("Notification", church_task.DUE_NOTIFICATION)
		church_task.create_due_notification()
		notification = frappe.get_doc("Notification", church_task.DUE_NOTIFICATION)
		task = frappe.get_doc(
			{
				"doctype": "Church Task",
				"title": "_Test Notice Gutters",
				"due_date": "2031-05-03 10:00:00",
				"status": "Assigned",
				"priority": "Urgent",
			}
		).insert(ignore_permissions=True)
		context = get_context(task)

		subject = frappe.render_template(notification.subject, context)
		message = frappe.render_template(notification.message, context)

		self.assertIn("_Test Notice Gutters", subject)
		for value in ("_Test Notice Gutters", "Assigned", "Urgent", f"/desk/church-task/{task.name}"):
			self.assertIn(value, message)
		self.assertIn(frappe.utils.format_datetime("2031-05-03 10:00:00"), message)


def church_user(email, roles, church):
	"""A user with *roles* whose Church permission is *church*."""
	ensure_user(email, "_Test Notice", roles)
	set_user_church(email, church)
	return email


def fields_read(*templates):
	return {field for template in templates for field in re.findall(r"doc\.(\w+)", template)}


class TestPrayerAndAlmsNotifications(FrappeTestCase):
	"""The Notifications seeded for new prayer and alms requests, and who they reach."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		prayer_request.create_new_prayer_request_notifications()
		alms_request.create_new_alms_request_notification()
		cls.addClassCleanup(clear_notification_cache)
		_root, cls.church_a, cls.church_b = make_two_churches()
		frappe.db.set_value("Church", cls.church_a, "publish", 1)
		team, care = ("Church User", "Church Prayer Team"), ("Church Staff", "Church Pastoral Care")
		cls.team_a = church_user("_test_notice_team_a@example.com", team, cls.church_a)
		cls.team_b = church_user("_test_notice_team_b@example.com", team, cls.church_b)
		cls.care_a = church_user("_test_notice_care_a@example.com", care, cls.church_a)
		cls.care_b = church_user("_test_notice_care_b@example.com", care, cls.church_b)
		cls.request_type = ensure("Prayer Request Type", {"type": "Health"})
		cls.asker = make_person("_Test Notice", "Asker", church=cls.church_a)

	def tearDown(self):
		frappe.set_user("Administrator")

	def emailed(self, doc, user="Administrator"):
		"""Everyone emailed when *user* adds *doc*."""
		frappe.set_user(user)
		with patch("frappe.sendmail") as sendmail:
			doc.insert(ignore_permissions=True)
		frappe.set_user("Administrator")
		return {recipient for call in sendmail.call_args_list for recipient in call.kwargs["recipients"]}

	def prayer_request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Notice Request",
				"type": self.request_type,
				"church": self.church_a,
				**values,
			}
		)

	def test_a_whole_church_request_reaches_the_prayer_team_of_its_church_only(self):
		emailed = self.emailed(self.prayer_request(visibility="Whole Church"))

		self.assertLessEqual({self.team_a, self.care_a}, emailed)
		self.assertFalse({self.team_b, self.care_b} & emailed)

	def test_a_private_request_reaches_the_care_team_but_not_the_prayer_team(self):
		self.assertTrue(is_prayer_team_only(self.team_a))

		emailed = self.emailed(self.prayer_request(visibility="Private"))

		self.assertIn(self.care_a, emailed)
		self.assertFalse({self.team_a, self.team_b, self.care_b} & emailed)

	def test_a_guests_request_waits_for_approval_before_it_reaches_the_prayer_team(self):
		request = self.prayer_request(visibility="Whole Church")

		emailed = self.emailed(request, user="Guest")

		self.assertEqual(request.approved_for_list, 0)
		self.assertIn(self.care_a, emailed)
		self.assertFalse({self.team_a, self.team_b, self.care_b} & emailed)

	def test_an_alms_request_reaches_the_care_team_of_its_church_only(self):
		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.asker.name,
				"requestor": self.asker.name,
				"description": "_Test Notice rent",
			}
		)

		emailed = self.emailed(alms)

		self.assertIn(self.care_a, emailed)
		self.assertFalse({self.team_a, self.care_b} & emailed)

	def test_the_patch_adds_each_notification_once_and_keeps_a_churchs_edit(self):
		names = (
			prayer_request.PRAYER_TEAM_NOTIFICATION,
			prayer_request.PRIVATE_NOTIFICATION,
			alms_request.ALMS_NOTIFICATION,
		)
		frappe.db.set_value("Notification", alms_request.ALMS_NOTIFICATION, "subject", "_Test edited")

		add_prayer_and_alms_notifications.execute()

		self.assertEqual(frappe.db.count("Notification", {"name": ("in", names)}), 3)
		self.assertEqual(
			frappe.db.get_value("Notification", alms_request.ALMS_NOTIFICATION, "subject"), "_Test edited"
		)

	def test_the_prayer_team_message_names_every_field(self):
		recipient = make_person("_Test Notice", "Sick", church=self.church_a)
		request = self.prayer_request(
			name="PREQ-NOTICE",
			urgent=1,
			requestor=self.asker.name,
			recipient_type="Person",
			recipient=recipient.name,
			recipient_name=recipient.full_name,
			visibility="Prayer Team",
			approved_for_list=1,
			request="_Test Notice <b>surgery</b>",
		)
		context = get_context(request)

		subject = frappe.render_template(prayer_request.PRAYER_TEAM_SUBJECT, context)
		message = frappe.render_template(prayer_request.PRAYER_TEAM_MESSAGE, context)

		self.assertEqual(subject, "Urgent prayer request: _Test Notice Request")
		church = frappe.db.get_value("Church", self.church_a, "church_name")
		for value in (
			"Urgent.",
			church,
			"_Test Notice Request",
			"_Test Notice Asker",
			"_Test Notice Sick",
			self.request_type,
			"Prayer Team",
			"_Test Notice &lt;b&gt;surgery&lt;/b&gt;",
			"/community-prayer-requests/PREQ-NOTICE",
			"/desk/prayer-request/PREQ-NOTICE",
		):
			self.assertIn(value, message)
		self.assert_reads_only_fields(
			"Prayer Request", prayer_request.PRAYER_TEAM_SUBJECT, prayer_request.PRAYER_TEAM_MESSAGE
		)

	def test_the_private_message_leaves_out_the_request(self):
		request = self.prayer_request(
			name="PREQ-NOTICE", visibility="Private", request="_Test Notice secret", requestor=self.asker.name
		)
		context = get_context(request)

		subject = frappe.render_template(prayer_request.PRIVATE_SUBJECT, context)
		message = frappe.render_template(prayer_request.PRIVATE_MESSAGE, context)

		self.assertEqual(subject, "New private prayer request")
		self.assertIn("/desk/prayer-request/PREQ-NOTICE", message)
		for private in ("_Test Notice secret", "_Test Notice Request", "_Test Notice Asker"):
			self.assertNotIn(private, message)
		self.assert_reads_only_fields(
			"Prayer Request", prayer_request.PRIVATE_SUBJECT, prayer_request.PRIVATE_MESSAGE
		)

	def test_the_alms_message_names_every_field(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Notice Household"}).insert(
			ignore_permissions=True
		)
		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"name": "ALMS-NOTICE",
				"title": "_Test Notice Household - 120 - Pending",
				"church": self.church_a,
				"recipient_type": "Family",
				"recipient": family.name,
				"requestor": self.asker.name,
				"amount": 120,
				"status": "Pending",
				"description": "_Test Notice <i>rent</i>",
			}
		)
		context = get_context(alms)

		subject = frappe.render_template(alms_request.ALMS_SUBJECT, context)
		message = frappe.render_template(alms_request.ALMS_MESSAGE, context)

		self.assertEqual(subject, "New alms request: _Test Notice Household - 120 - Pending")
		for value in (
			"_Test Notice Household",
			"_Test Notice Asker",
			frappe.utils.fmt_money(120),
			"Pending",
			"_Test Notice &lt;i&gt;rent&lt;/i&gt;",
			"/desk/alms-request/ALMS-NOTICE",
		):
			self.assertIn(value, message)
		self.assert_reads_only_fields("Alms Request", alms_request.ALMS_SUBJECT, alms_request.ALMS_MESSAGE)

	def assert_reads_only_fields(self, doctype, *templates):
		"""A field the doctype does not have renders blank, so every `doc.` name must be a real one."""
		self.assertLessEqual(
			fields_read(*templates), {"doctype", *frappe.get_meta(doctype).get_valid_columns()}
		)
