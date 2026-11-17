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
from frappe.client import set_value
from frappe.email.doctype.notification.notification import clear_notification_cache, get_context
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_url

from churchit.church_finances.doctype.alms_request import alms_request
from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.church_task import church_task
from churchit.church_operations.doctype.room_booking import room_booking
from churchit.church_people.doctype.care_request import care_request
from churchit.church_prayers.doctype.prayer_request import prayer_request
from churchit.church_prayers.prayer_access import is_prayer_team_only
from churchit.patches.v1_0 import (
	add_care_request_and_alms_approved_notifications,
	add_prayer_and_alms_notifications,
	add_prayer_request_approved_notification,
	format_dates_and_money_in_inserted_notifications,
	remove_duplicate_standard_notifications,
	sign_greeting_templates_and_greet_active_people,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
)


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


class TestNotificationContent(FrappeTestCase):
	"""What a church volunteer reads: names instead of record IDs, links, and no shared recipient list."""

	def render(self, module, name, doc):
		"""Subject and message of the shipped notification *name*, as sent for *doc*."""
		notification, _markdown = shipped_templates(module, name)
		context = get_context(doc)
		return tuple(frappe.render_template(notification[field], context) for field in ("subject", "message"))

	def test_each_markdown_file_is_the_json_message(self):
		"""A standard notification sends its .md, and a church's duplicate sends the JSON message."""
		for path in Path(frappe.get_app_path("churchit")).glob("*/notification/*/*.md"):
			with self.subTest(path.stem):
				self.assertEqual(
					path.read_text(), json.loads(path.with_suffix(".json").read_text())["message"]
				)

	def test_expense_pending_approval_shows_the_currency(self):
		get_default = frappe.db.get_default
		expense = frappe.get_doc({"doctype": "Expense", "amount": 245.5})

		with patch.object(
			frappe.db,
			"get_default",
			lambda key, *args: "EUR" if key == "currency" else get_default(key, *args),
		):
			subject, message = self.render("church_finances", "Expense Pending Approval", expense)

		for text in (subject, message):
			self.assertIn("€", text)

	def test_new_member_welcome_goes_to_the_member_only(self):
		notification, _markdown = shipped_templates("church_communications", "New Member Welcome")

		self.assertEqual(
			[row.get("receiver_by_document_field") for row in notification["recipients"]],
			["notification_address,emails"],
		)

	def test_function_reminder_prints_a_readable_time_and_address(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Notice Hall",
				"address_line1": "12 Chapel Lane",
				"city": "Testville",
				"country": "United States",
			}
		).insert(ignore_permissions=True)
		function = frappe.get_doc(
			{
				"doctype": "Function",
				"function_name": "_Test Notice Supper",
				"start_date": "2031-01-02",
				"start_time": "10:00:00",
				"address": address.name,
			}
		)

		_subject, message = self.render("church_communications", "Function Reminder 24h", function)

		self.assertIn("10:00 AM", message)
		self.assertIn("12 Chapel Lane", message)
		self.assertNotIn(address.name, message)

	def test_member_notifications_link_to_the_portal_and_the_calendar(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Notice", "last_name": "Welcome"})
		function = frappe.get_doc(
			{"doctype": "Function", "function_name": "_Test Notice Supper", "start_date": "2031-01-02"}
		)

		for name, doc, path in (
			("New Member Welcome", person, "/portal"),
			("Function Reminder 24h", function, "/calendar"),
		):
			with self.subTest(name):
				_subject, message = self.render("church_communications", name, doc)
				self.assertIn(f'href="{get_url(path)}"', message)

	def test_staff_notifications_link_to_their_record(self):
		for module, name in (
			("church_finances", "Expense Pending Approval"),
			("church_communications", "Background Check Expiring"),
			("church_communications", "Visitor Follow-Up"),
			("church_communications", "Meeting Minutes Published"),
		):
			with self.subTest(name):
				notification, _markdown = shipped_templates(module, name)
				self.assertIn("get_url_to_form(doc.doctype, doc.name)", notification["message"])

	def test_shipped_duplicates_are_gone(self):
		for module, name in (
			("church_communications", "Prayer Request New"),
			("church_finances", "Alms Request Review"),
		):
			path = Path(frappe.get_app_path("churchit", module, "notification", frappe.scrub(name)))
			self.assertFalse((path / f"{path.name}.json").exists())


class TestRemoveDuplicateNotificationsPatch(FrappeTestCase):
	def test_the_shipped_duplicates_go(self):
		for name in remove_duplicate_standard_notifications.DUPLICATES:
			frappe.delete_doc_if_exists("Notification", name, force=True)
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": name,
					"subject": "_Test shipped",
					"document_type": "Alms Request",
					"event": "New",
					"channel": "Email",
					"recipients": [{"receiver_by_role": "Church Manager"}],
					"message": "_Test shipped",
				}
			).insert(ignore_permissions=True)
			frappe.db.set_value("Notification", name, "is_standard", 1)

		with patch.dict(frappe.flags, {"in_patch": True}):
			remove_duplicate_standard_notifications.execute()
			remove_duplicate_standard_notifications.execute()

		for name in remove_duplicate_standard_notifications.DUPLICATES:
			self.assertFalse(frappe.db.exists("Notification", name))

	def test_a_church_s_own_notification_of_the_same_name_stays(self):
		frappe.delete_doc_if_exists("Notification", "Alms Request Review", force=True)
		frappe.get_doc(
			{
				"doctype": "Notification",
				"name": "Alms Request Review",
				"subject": "_Test own",
				"document_type": "Alms Request",
				"event": "New",
				"channel": "Email",
				"is_standard": 0,
				"recipients": [{"receiver_by_role": "Church Manager"}],
				"message": "_Test own",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc_if_exists, "Notification", "Alms Request Review", force=True)

		remove_duplicate_standard_notifications.execute()

		self.assertTrue(frappe.db.exists("Notification", "Alms Request Review"))


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
		self.assertIn("Saturday, May 3, 2031 10:00 AM", message)


class TestFormatDatesAndMoneyPatch(FrappeTestCase):
	def test_the_inserted_messages_get_the_new_formats_and_keep_a_church_s_own_text(self):
		messages = {
			room_booking.DECIDED_NOTIFICATION: room_booking.DECIDED_MESSAGE,
			church_task.DUE_NOTIFICATION: church_task.DUE_MESSAGE,
			alms_request.ALMS_NOTIFICATION: alms_request.ALMS_MESSAGE,
		}
		room_booking.create_decided_notification()
		church_task.create_due_notification()
		alms_request.create_new_alms_request_notification()
		own_line = "<p>_Test our own line</p>"
		for name, message in messages.items():
			shipped = message
			for old, new in format_dates_and_money_in_inserted_notifications.FIXES[name]:
				shipped = shipped.replace(new, old)
			self.assertNotEqual(shipped, message)
			frappe.db.set_value("Notification", name, "message", shipped + own_line)

		for _run in range(2):
			format_dates_and_money_in_inserted_notifications.execute()

		for name, message in messages.items():
			self.assertEqual(frappe.db.get_value("Notification", name, "message"), message + own_line)


def church_user(email, roles, church):
	"""A user with *roles* whose Church permission is *church*."""
	ensure_user(email, "_Test Notice", roles)
	set_user_church(email, church)
	return email


def fields_read(*templates):
	return {field for template in templates for field in re.findall(r"doc\.(\w+)", template)}


class TestPrayerAndAlmsNotifications(FrappeTestCase):
	"""The Notifications seeded for prayer, alms and care requests, and who they reach."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		prayer_request.create_new_prayer_request_notifications()
		alms_request.create_new_alms_request_notification()
		alms_request.create_alms_request_approved_notification()
		care_request.create_new_care_request_notification()
		cls.addClassCleanup(clear_notification_cache)
		# A Notification sends email only while an Email Account can send it.
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Notice Outgoing",
				"email_id": "_test_notice_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		_root, cls.church_a, cls.church_b = make_two_churches()
		frappe.db.set_value("Church", cls.church_a, "publish", 1)
		team, care = ("Church User", "Church Prayer Team"), ("Church Staff", "Church Pastoral Care")
		cls.team_a = church_user("_test_notice_team_a@example.com", team, cls.church_a)
		cls.team_b = church_user("_test_notice_team_b@example.com", team, cls.church_b)
		cls.care_a = church_user("_test_notice_care_a@example.com", care, cls.church_a)
		cls.care_b = church_user("_test_notice_care_b@example.com", care, cls.church_b)
		finance = ("Church Staff", "Church Finance")
		cls.finance_a = church_user("_test_notice_finance_a@example.com", finance, cls.church_a)
		cls.finance_b = church_user("_test_notice_finance_b@example.com", finance, cls.church_b)
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

	def approval_emails(self, name, user="Administrator"):
		"""Every recipient, once per email, when *user* approves the request *name* for the list."""
		frappe.set_user(user)
		request = frappe.get_doc("Prayer Request", name)
		with patch("frappe.sendmail") as sendmail:
			request.approved_for_list = 1
			request.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		return [recipient for call in sendmail.call_args_list for recipient in call.kwargs["recipients"]]

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

	def test_a_guests_request_reaches_the_prayer_team_when_it_is_approved(self):
		request = self.prayer_request(visibility="Whole Church")
		self.emailed(request, user="Guest")

		emailed = self.approval_emails(request.name, user=self.care_a)

		self.assertEqual(emailed.count(self.team_a), 1)
		self.assertFalse({self.team_b, self.care_a, self.care_b} & set(emailed))

	def test_a_request_approved_at_creation_reaches_the_prayer_team_once(self):
		request = self.prayer_request(visibility="Whole Church", request="_Test Notice first")
		self.assertIn(self.team_a, self.emailed(request))

		with patch("frappe.sendmail") as sendmail:
			edited = frappe.get_doc("Prayer Request", request.name)
			edited.request = "_Test Notice second"
			edited.save(ignore_permissions=True)
			set_value("Prayer Request", request.name, "approved_for_list", 1)

		sendmail.assert_not_called()

	def test_approving_a_private_request_reaches_no_prayer_team(self):
		request = self.prayer_request(visibility="Private")
		self.emailed(request, user="Guest")

		emailed = self.approval_emails(request.name, user=self.care_a)

		self.assertFalse({self.team_a, self.team_b} & set(emailed))

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

	def alms_request(self):
		return frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": self.asker.name,
				"requestor": self.asker.name,
				"description": "_Test Notice rent",
				"amount": 80,
			}
		)

	def status_emails(self, name, status):
		"""Every recipient, once per email, when the care team sets the alms request *name* to *status*."""
		frappe.set_user(self.care_a)
		alms = frappe.get_doc("Alms Request", name)
		with patch("frappe.sendmail") as sendmail:
			alms.status = status
			alms.save(ignore_permissions=True)
		frappe.set_user("Administrator")
		return [recipient for call in sendmail.call_args_list for recipient in call.kwargs["recipients"]]

	def test_an_approved_alms_request_reaches_finance_of_its_church_only(self):
		alms = self.alms_request()
		self.assertFalse({self.finance_a, self.finance_b} & self.emailed(alms))

		emailed = self.status_emails(alms.name, "Approved")

		self.assertEqual(emailed.count(self.finance_a), 1)
		self.assertFalse({self.finance_b, self.care_a, self.care_b} & set(emailed))

	def test_a_declined_alms_request_reaches_no_one_in_finance(self):
		alms = self.alms_request()
		self.emailed(alms)

		self.assertFalse({self.finance_a, self.finance_b} & set(self.status_emails(alms.name, "Declined")))

	def test_a_care_request_reaches_the_care_team_of_its_church_only(self):
		request = frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": self.asker.name,
				"category": ensure("Care Request Type", {"type": "_Test Notice Need"}),
				"description": "_Test Notice visit",
			}
		)

		emailed = self.emailed(request)

		self.assertIn(self.care_a, emailed)
		self.assertFalse({self.care_b, self.team_a, self.finance_a} & emailed)

	def test_the_care_request_message_names_every_field(self):
		caregiver = make_person("_Test Notice", "Caregiver", church=self.church_a)
		request = frappe.get_doc(
			{
				"doctype": "Care Request",
				"name": "CR-NOTICE",
				"church": self.church_a,
				"person": self.asker.name,
				"person_name": self.asker.full_name,
				"category": ensure("Care Request Type", {"type": "_Test Notice Need"}),
				"urgency": "High",
				"due_on": "2031-01-02",
				"preferred_contact": "Phone",
				"caregiver": caregiver.name,
				"description": "_Test Notice <b>hospital</b>",
			}
		)
		context = get_context(request)

		subject = frappe.render_template(care_request.CARE_SUBJECT, context)
		message = frappe.render_template(care_request.CARE_MESSAGE, context)

		self.assertEqual(subject, "New care request: _Test Notice Need for _Test Notice Asker")
		for value in (
			frappe.db.get_value("Church", self.church_a, "church_name"),
			"_Test Notice Asker",
			"_Test Notice Need",
			"High",
			"Thursday, January 2, 2031",
			"Phone",
			"_Test Notice Caregiver",
			"_Test Notice &lt;b&gt;hospital&lt;/b&gt;",
			"/desk/care-request/CR-NOTICE",
		):
			self.assertIn(value, message)
		self.assert_reads_only_fields("Care Request", care_request.CARE_SUBJECT, care_request.CARE_MESSAGE)

	def test_the_approved_alms_message_names_every_field(self):
		alms = self.alms_request()
		alms.update(
			{
				"name": "ALMS-NOTICE",
				"title": "_Test Notice Asker",
				"church": self.church_a,
				"expense_type": "_Test Type",
			}
		)
		context = get_context(alms)

		subject = frappe.render_template(alms_request.APPROVED_SUBJECT, context)
		message = frappe.render_template(alms_request.APPROVED_MESSAGE, context)

		self.assertEqual(subject, "Alms request approved: _Test Notice Asker")
		for value in (
			"_Test Notice Asker",
			frappe.utils.fmt_money(80, currency=frappe.db.get_default("currency")),
			"_Test Type",
			"Create Expense",
			"/desk/alms-request/ALMS-NOTICE",
		):
			self.assertIn(value, message)
		self.assert_reads_only_fields(
			"Alms Request", alms_request.APPROVED_SUBJECT, alms_request.APPROVED_MESSAGE
		)

	def test_the_care_and_approved_patch_adds_each_once_and_keeps_a_churchs_edit(self):
		frappe.delete_doc("Notification", alms_request.APPROVED_NOTIFICATION, ignore_permissions=True)
		frappe.db.set_value("Notification", care_request.CARE_NOTIFICATION, "subject", "_Test edited")

		add_care_request_and_alms_approved_notifications.execute()
		add_care_request_and_alms_approved_notifications.execute()

		self.assertEqual(
			frappe.get_all(
				"Notification",
				{"name": alms_request.APPROVED_NOTIFICATION},
				["event", "value_changed"],
				as_list=True,
			),
			(("Value Change", "status"),),
		)
		self.assertEqual(
			frappe.db.get_value("Notification", care_request.CARE_NOTIFICATION, "subject"), "_Test edited"
		)

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

	def test_the_approved_patch_adds_the_missing_notification_once_and_keeps_a_churchs_edit(self):
		approved = prayer_request.APPROVED_NOTIFICATION
		frappe.delete_doc("Notification", approved, ignore_permissions=True)
		frappe.db.set_value(
			"Notification", prayer_request.PRAYER_TEAM_NOTIFICATION, "subject", "_Test edited"
		)

		add_prayer_request_approved_notification.execute()
		add_prayer_request_approved_notification.execute()

		self.assertEqual(
			frappe.get_all("Notification", {"name": approved}, ["event", "value_changed"], as_list=True),
			(("Value Change", "approved_for_list"),),
		)
		self.assertEqual(
			frappe.db.get_value("Notification", prayer_request.PRAYER_TEAM_NOTIFICATION, "subject"),
			"_Test edited",
		)

	def test_the_approved_patch_leaves_a_deleted_notification_deleted(self):
		deleted = (prayer_request.PRAYER_TEAM_NOTIFICATION, prayer_request.PRIVATE_NOTIFICATION)
		self.addCleanup(prayer_request.create_new_prayer_request_notifications)
		for name in deleted:
			frappe.delete_doc("Notification", name, ignore_permissions=True)

		add_prayer_request_approved_notification.execute()

		self.assertFalse(frappe.db.count("Notification", {"name": ("in", deleted)}))
		self.assertTrue(frappe.db.exists("Notification", prayer_request.APPROVED_NOTIFICATION))

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
			frappe.utils.fmt_money(120, currency=frappe.db.get_default("currency")),
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


class TestGreetings(RollbackEachTest):
	def shipped_condition(self, name):
		return shipped_templates("church_communications", name)[0]["condition"]

	def test_the_greetings_go_only_to_active_people(self):
		for name in ("Birthday Greeting", "Anniversary Greeting"):
			with self.subTest(name):
				self.assertIn('doc.membership_status == "Active"', self.shipped_condition(name))

	def test_the_three_templates_sign_with_the_church_name(self):
		for name in ("Birthday Greeting", "New Member Welcome", "Visitor Follow-Up"):
			with self.subTest(name):
				self.assertIn(
					"{{ church_name }}", frappe.db.get_value("Email Template", name, "response_html")
				)

	def test_the_patch_signs_a_shipped_template_and_keeps_a_church_s_own_words(self):
		old = "<p>Dear {{ first_name }},</p>\n\n<p>Our own words.</p>\n\n<p>With love,<br>The Church</p>"
		frappe.db.set_value("Email Template", "Birthday Greeting", "response_html", old)
		frappe.db.set_value(
			"Email Template", "Visitor Follow-Up", "response_html", "<p>Our own words, with no sign-off.</p>"
		)

		sign_greeting_templates_and_greet_active_people.execute()
		sign_greeting_templates_and_greet_active_people.execute()

		self.assertEqual(
			frappe.db.get_value("Email Template", "Birthday Greeting", "response_html"),
			old.removesuffix("The Church</p>") + "{{ church_name }}</p>",
		)
		self.assertEqual(
			frappe.db.get_value("Email Template", "Visitor Follow-Up", "response_html"),
			"<p>Our own words, with no sign-off.</p>",
		)

	def test_the_patch_adds_the_active_rule_to_a_shipped_condition_once_and_keeps_enabled(self):
		birthday = frappe.get_doc(
			{
				**shipped_templates("church_communications", "Birthday Greeting")[0],
				"name": "_Test Birthday Copy",
				"is_standard": 0,
				"enabled": 1,
				"condition": "doc.primary_email",
			}
		).insert(ignore_permissions=True)
		own = frappe.copy_doc(birthday)
		own.update({"name": "_Test Birthday Own", "condition": "doc.primary_email and doc.is_deceased == 0"})
		own.insert(ignore_permissions=True)
		disabled = frappe.copy_doc(birthday)
		disabled.update({"name": "_Test Birthday Off", "enabled": 0})
		disabled.insert(ignore_permissions=True)

		sign_greeting_templates_and_greet_active_people.execute()
		sign_greeting_templates_and_greet_active_people.execute()

		values = {
			row.name: row
			for row in frappe.get_all(
				"Notification",
				filters={"name": ("in", [birthday.name, own.name, disabled.name])},
				fields=["name", "condition", "enabled"],
			)
		}
		active = 'doc.primary_email and doc.membership_status == "Active"'
		self.assertEqual((values[birthday.name].condition, values[birthday.name].enabled), (active, 1))
		self.assertEqual((values[disabled.name].condition, values[disabled.name].enabled), (active, 0))
		self.assertEqual(values[own.name].condition, "doc.primary_email and doc.is_deceased == 0")
