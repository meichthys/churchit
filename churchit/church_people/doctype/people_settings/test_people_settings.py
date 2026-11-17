# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.email.doctype.notification.notification import get_context, get_notification_templates
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.derived import refresh_daily
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.doctype.people_settings.people_settings import (
	DIRECTORY_ROUTE,
	REMINDERS,
	create_reminders,
	store_defaults,
	sync_directory_menu_item,
)
from churchit.church_people.followup import CARD, add_card
from churchit.patches.v1_0 import apply_directory_share_defaults, turn_standard_reminders_into_records
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_branch,
	make_person,
	set_multi_church,
)


def save_adult_age(age):
	settings = frappe.get_single("People Settings")
	settings.adult_age = age
	settings.save(ignore_permissions=True)


class TestPeopleSettings(FrappeTestCase):
	def test_a_site_that_never_saved_the_settings_gets_the_default_adult_age(self):
		"""A Single nobody saved stores nothing, so a reader got 0 and everyone with an age was an Adult."""
		frappe.db.delete("Singles", {"doctype": "People Settings"})

		store_defaults()

		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 18)

	def test_storing_the_defaults_keeps_a_saved_adult_age(self):
		save_adult_age(21)

		store_defaults()

		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 21)

	def test_changing_the_adult_age_rechecks_every_life_stage(self):
		save_adult_age(18)
		settings = frappe.get_single("People Settings")

		with patch("frappe.enqueue") as enqueue:
			settings.save(ignore_permissions=True)
			enqueue.assert_not_called()

			settings.adult_age = 16
			settings.save(ignore_permissions=True)

		enqueue.assert_called_once_with(refresh_daily, enqueue_after_commit=True)


def save_settings(**values):
	settings = frappe.get_single("People Settings")
	settings.update(values)
	settings.save(ignore_permissions=True)


def directory_menu_rows():
	return [row for row in frappe.get_single("Portal Settings").menu if row.route == DIRECTORY_ROUTE]


class TestMemberDirectorySettings(RollbackEachTest):
	def test_new_people_share_what_the_settings_say_and_people_on_file_keep_their_choice(self):
		save_settings(
			directory_share_email=0,
			directory_share_phone=0,
			directory_share_address=0,
			directory_share_birthday=0,
		)
		on_file = make_person("_Test Sharing", "On File").name

		save_settings(
			directory_share_email=1,
			directory_share_phone=0,
			directory_share_address=1,
			directory_share_birthday=1,
		)
		# Frappe keeps a new record's defaults until the request ends, and the next request starts afresh.
		frappe.local.new_doc_templates.pop("Person", None)
		newcomer = make_person("_Test Sharing", "Newcomer").name

		shares = ["share_email", "share_phone", "share_address", "share_birthday"]
		self.assertEqual(frappe.db.get_value("Person", newcomer, shares), (1, 0, 1, 1))
		self.assertEqual(frappe.db.get_value("Person", on_file, shares), (0, 0, 0, 0))

	def test_the_patch_follows_sharing_that_migrate_stored_without_a_save(self):
		frappe.db.set_single_value(
			"People Settings", {"directory_share_email": 1, "directory_share_address": 0}
		)

		apply_directory_share_defaults.execute()

		meta = frappe.get_meta("Person")
		self.assertEqual(meta.get_field("share_email").default, "1")
		self.assertEqual(meta.get_field("share_address").default, "0")

	def test_saving_unchanged_sharing_writes_no_property_setter(self):
		save_settings(directory_share_email=1)
		setters = frappe.get_all(
			"Property Setter", filters={"doc_type": "Person"}, fields=["name", "modified"]
		)

		save_settings(adult_age=frappe.db.get_single_value("People Settings", "adult_age"))

		self.assertEqual(
			frappe.get_all("Property Setter", filters={"doc_type": "Person"}, fields=["name", "modified"]),
			setters,
		)

	def test_the_member_directory_shows_in_the_portal_menu_only_while_it_is_on(self):
		frappe.db.delete("Portal Menu Item", {"parent": "Portal Settings", "route": DIRECTORY_ROUTE})
		frappe.get_doc(
			{
				"doctype": "Portal Menu Item",
				"parenttype": "Portal Settings",
				"parent": "Portal Settings",
				"parentfield": "menu",
				"idx": 99,
				"title": "Member Directory",
				"route": DIRECTORY_ROUTE,
				"reference_doctype": "Person",
				"role": "Church User",
				"enabled": 1,
			}
		).db_insert()
		frappe.db.set_single_value("People Settings", "member_directory", 0)

		sync_directory_menu_item()
		self.assertEqual([row.enabled for row in directory_menu_rows()], [0])

		save_settings(member_directory=1)
		self.assertEqual([row.enabled for row in directory_menu_rows()], [1])


def reminder_templates():
	"""Each shipped reminder by name, as create_reminders inserts it."""
	folder = Path(frappe.get_app_path("churchit", "church_people", "doctype", "people_settings", "reminders"))
	return {template["name"]: template for template in get_notification_templates(str(folder))}


class TestReminders(RollbackEachTest):
	"""A Church Manager turns the overdue and visit reminders on in People Settings, with no Notification rights."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_reminders()
		cls.manager = ensure_user(
			"_test_reminder_manager@example.com", "ReminderManager", ("Church Manager",)
		)

	def setUp(self):
		super().setUp()
		for name, (switch, days) in REMINDERS.items():
			frappe.db.set_value("Notification", name, {"enabled": 0, "days_in_advance": 1})
			frappe.db.set_single_value("People Settings", {switch: 0, days: 1})

	def save_as(self, user, **values):
		settings = frappe.get_single("People Settings")
		settings.update(values)
		frappe.set_user(user)
		try:
			settings.save()
		finally:
			frappe.set_user("Administrator")

	def test_the_reminders_are_records_a_production_site_can_turn_on(self):
		for name in REMINDERS:
			frappe.delete_doc("Notification", name, ignore_permissions=True)
		create_reminders()

		for name in REMINDERS:
			with self.subTest(name):
				self.assertEqual(
					frappe.db.get_value("Notification", name, ["is_standard", "enabled", "days_in_advance"]),
					(0, 0, 1),
				)

	def test_a_church_manager_turns_a_reminder_on_and_sets_its_days(self):
		self.assertFalse(frappe.has_permission("Notification", "write", user=self.manager))

		self.save_as(self.manager, remind_overdue_care_requests=1, care_request_reminder_days=3)

		self.assertEqual(
			frappe.db.get_value("Notification", "Care Request Overdue", ["enabled", "days_in_advance"]),
			(1, 3),
		)
		self.assertEqual(frappe.db.get_value("Notification", "Follow-up Card Overdue", "enabled"), 0)

	def test_a_branch_manager_cannot_turn_a_reminder_on_for_every_church(self):
		set_multi_church(True)
		branch = make_branch("_Test Reminder Branch", "TRB")
		branch_manager = ensure_user(
			"_test_reminder_branch@example.com", "ReminderBranch", ("Church Manager",)
		)
		set_user_church(branch_manager, branch)

		with self.assertRaisesRegex(frappe.PermissionError, "apply to every church"):
			self.save_as(branch_manager, remind_planned_visits=1)

		self.assertEqual(frappe.db.get_value("Notification", "Visitation Follow-Up Due", "enabled"), 0)

	def test_the_reminder_follows_the_settings_on_each_save(self):
		"""People Settings owns the switch, so the form never says off while the reminder is on."""
		frappe.db.set_value("Notification", "Follow-up Card Overdue", {"enabled": 1, "days_in_advance": 4})
		modified = frappe.db.get_value("Notification", "Care Request Overdue", "modified")

		self.save_as(self.manager, adult_age=frappe.db.get_single_value("People Settings", "adult_age") + 1)

		self.assertEqual(
			frappe.db.get_value("Notification", "Follow-up Card Overdue", ["enabled", "days_in_advance"]),
			(0, 1),
		)
		self.assertEqual(frappe.db.get_value("Notification", "Care Request Overdue", "modified"), modified)

	def test_a_standard_reminder_waiting_for_the_patch_stays_as_it_is(self):
		"""Saving a standard Notification in developer mode would write its folder back into the app."""
		frappe.db.set_value("Notification", "Care Request Overdue", "is_standard", 1)

		self.save_as(self.manager, remind_overdue_care_requests=1, care_request_reminder_days=3)

		self.assertEqual(
			frappe.db.get_value("Notification", "Care Request Overdue", ["enabled", "days_in_advance"]),
			(0, 1),
		)


class TestStandardRemindersPatch(RollbackEachTest):
	def test_the_standard_reminders_become_records_and_keep_their_state(self):
		frappe.delete_doc_if_exists("Notification", "Follow-up Card Overdue", force=True)
		template = reminder_templates()["Follow-up Card Overdue"]
		frappe.get_doc(
			{
				**template,
				"doctype": "Notification",
				"is_standard": 1,
				"module": "Church Communications",
				"enabled": 1,
				"days_in_advance": 2,
			}
		).db_insert()
		copy = frappe.get_doc(
			{**template, "doctype": "Notification", "name": "_Test Church Copy", "is_standard": 0}
		).insert(ignore_permissions=True)

		with patch.dict(frappe.flags, {"in_patch": True}):
			turn_standard_reminders_into_records.execute()
			turn_standard_reminders_into_records.execute()

		self.assertEqual(
			frappe.db.get_value(
				"Notification", "Follow-up Card Overdue", ["is_standard", "enabled", "days_in_advance"]
			),
			(0, 1, 2),
		)
		self.assertEqual(frappe.db.get_value("Notification", copy.name, "message"), template["message"])
		self.assertEqual(frappe.db.get_single_value("People Settings", "remind_overdue_follow_up_cards"), 1)
		self.assertEqual(frappe.db.get_single_value("People Settings", "follow_up_card_reminder_days"), 2)
		for name in REMINDERS:
			self.assertTrue(frappe.db.exists("Notification", name))

	def test_no_standard_reminder_ships_with_the_app(self):
		"""Migrate would put a standard copy back, which production cannot turn on."""
		folder = Path(frappe.get_app_path("churchit", "church_communications", "notification"))
		for name in REMINDERS:
			self.assertFalse((folder / frappe.scrub(name)).exists())


class TestReminderMessages(RollbackEachTest):
	"""What a volunteer reads: names instead of record IDs, the long date, a link, and the right people."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.templates = reminder_templates()

	def render(self, name, doc):
		template = self.templates[name]
		context = get_context(doc)
		return (
			frappe.render_template(template["subject"], context),
			frappe.render_template(template["message"], context),
		)

	def test_every_reminder_marks_its_condition_python(self):
		"""Frappe skips a condition whose type is unset."""
		for name, template in self.templates.items():
			self.assertEqual(template["condition_type"], "Python", name)

	def test_the_overdue_card_notice_names_the_card_and_reaches_its_assignee(self):
		caller = ensure_user("_test_reminder_caller@example.com", "ReminderCaller", ("Church Follow-up",))
		workflow = make_workflow("_Test Reminder Workflow", [("Call", caller, 1)]).name
		card = frappe.get_doc(CARD, add_card(make_person("_Test Reminder", "Newcomer").name, workflow))
		card.due_on = "2031-01-02"
		notification = frappe.get_doc({**self.templates["Follow-up Card Overdue"], "doctype": "Notification"})
		context = get_context(card)

		subject, message = self.render("Follow-up Card Overdue", card)

		for text in (subject, message):
			self.assertIn("_Test Reminder Newcomer", text)
		for text in ("Call", "Thursday, January 2, 2031", "/desk/follow-up-card/"):
			self.assertIn(text, message)
		self.assertTrue(frappe.safe_eval(notification.condition, None, context))
		self.assertIn(caller, notification.get_list_of_recipients(card, context)[0])

	def test_the_visit_notice_names_the_person_and_reaches_the_visitor(self):
		"""Visited By holds a Person, which Frappe would drop as a recipient for not being an email."""
		visitor = make_person("_Test Reminder", "Visitor")
		visitor.append("emails", {"email_address": "_test_reminder_visitor@example.com", "is_primary": 1})
		visitor.save(ignore_permissions=True)
		person = make_person("_Test Reminder", "Visited")
		visit = frappe.get_doc(
			{
				"doctype": "Visitation Log",
				"person": person.name,
				"person_name": person.full_name,
				"visited_by": visitor.name,
				"status": "Planned",
				"visit_date": "2031-01-02",
			}
		)
		visit.name = "_Test Reminder Visit"
		notification = frappe.get_doc(
			{**self.templates["Visitation Follow-Up Due"], "doctype": "Notification"}
		)

		subject, message = self.render("Visitation Follow-Up Due", visit)

		for text in (subject, message):
			self.assertIn("_Test Reminder Visited", text)
			self.assertNotIn(person.name, text)
		self.assertIn("Thursday, January 2, 2031", message)
		self.assertIn("/desk/visitation-log/", message)
		_recipients, cc, _bcc = notification.get_list_of_recipients(visit, get_context(visit))
		self.assertIn("_test_reminder_visitor@example.com", cc)
		for status, sent in (("Planned", True), ("Scheduled", True), ("Completed", False)):
			visit.status = status
			self.assertEqual(bool(frappe.safe_eval(notification.condition, None, get_context(visit))), sent)

	def test_a_turned_on_reminder_picks_the_records_its_days_say(self):
		create_reminders()
		frappe.db.set_value("Notification", "Visitation Follow-Up Due", {"enabled": 1, "days_in_advance": 3})
		visits = {}
		for days in (1, 3):
			visits[days] = frappe.get_doc(
				{
					"doctype": "Visitation Log",
					"person": make_person("_Test Reminder", f"In {days}").name,
					"status": "Planned",
					"visit_date": add_days(today(), days),
					"visit_type": frappe.get_all("Visit Type", pluck="name", limit=1)[0],
				}
			).insert(ignore_permissions=True)

		due = [
			doc.name
			for doc in frappe.get_doc("Notification", "Visitation Follow-Up Due").get_documents_for_today()
		]

		self.assertIn(visits[3].name, due)
		self.assertNotIn(visits[1].name, due)
