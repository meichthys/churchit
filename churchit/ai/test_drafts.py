# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""AI drafts: a link to a filled, unsaved form for the caller only, and the label after the first save."""

from unittest import mock
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.utils import get_url_to_form

from churchit.ai.drafts import get_draft, label_saved, make_draft, propose
from churchit.ai.switch import SETTINGS
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	create_communication_purposes,
)
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

MANAGER = "_test_drafts_manager@example.com"
EDITOR = "_test_drafts_editor@example.com"
OTHER_EDITOR = "_test_drafts_other_editor@example.com"
STAFF = "_test_drafts_staff@example.com"
WEBSITE_USER = "_test_drafts_website_user@example.com"
LABEL = "Drafted with AI help (an AI app)."


def get_token(url: str) -> str:
	return parse_qs(urlparse(url).query)["ai_draft"][0]


def get_labels(doctype: str, name: str) -> list[str]:
	return frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Info"},
		pluck="content",
	)


class DraftTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		create_communication_purposes()
		for user, roles in (
			(MANAGER, ("Church Manager",)),
			(EDITOR, ("Church People Editor",)),
			(OTHER_EDITOR, ("Church People Editor",)),
			(STAFF, ("Church Staff",)),
		):
			ensure_user(user, "Drafts", roles)
			set_user_church(user, cls.church)
		ensure_user(WEBSITE_USER, "Drafts Website User", ())
		cls.person = make_person("_Test Drafts", "Member", church=cls.church).name
		cls.group = (
			frappe.get_doc(
				{
					"doctype": "Group",
					"group_name": "_Test Drafts Group",
					"church": cls.church,
					"members": [{"person": cls.person}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, "enabled", 1)

	def as_user(self, user: str) -> None:
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")


class TestPropose(DraftTestCase):
	def test_propose_returns_a_link_and_saves_nothing(self):
		self.as_user(MANAGER)
		emails = frappe.db.count("Church Email")
		writes = frappe.db.transaction_writes

		result = propose("Church Email", {"subject": "Welcome", "message": "<p>Glad you came.</p>"})

		self.assertEqual(frappe.db.transaction_writes, writes)
		self.assertEqual(frappe.db.count("Church Email"), emails)
		self.assertTrue(result["url"].startswith(get_url_to_form("Church Email", "new") + "?ai_draft="))
		self.assertEqual(result["dropped"], [])
		draft = get_draft(get_token(result["url"]))
		self.assertEqual(
			draft,
			{
				"doctype": "Church Email",
				"name": None,
				"values": {"subject": "Welcome", "message": "<p>Glad you came.</p>"},
				"stale": False,
			},
		)

	def test_values_may_come_as_json(self):
		self.as_user(MANAGER)
		result = propose("Church Email", '{"subject": "Welcome"}')
		self.assertEqual(get_draft(get_token(result["url"]))["values"], {"subject": "Welcome"})

	def test_another_user_gets_draft_not_found(self):
		self.as_user(EDITOR)
		token = get_token(propose("Group", {"group_name": "_Test Drafts Mine"})["url"])

		frappe.set_user(OTHER_EDITOR)
		with self.assertRaisesRegex(frappe.DoesNotExistError, "Draft not found"):
			get_draft(token)
		frappe.set_user(EDITOR)
		self.assertEqual(get_draft(token)["values"], {"group_name": "_Test Drafts Mine"})
		for forged in ("0" * 32, f"../{token}", token.upper() + "x"):
			self.assertRaisesRegex(frappe.DoesNotExistError, "Draft not found", get_draft, forged)

	def test_a_sign_in_keeps_the_draft(self):
		"""The person often signs in to open the link, and Frappe's sign-in clears their "user:" keys."""
		self.as_user(EDITOR)
		token = get_token(propose("Group", {"group_name": "_Test Drafts Mine"})["url"])
		frappe.clear_cache(user=EDITOR)
		self.assertTrue(get_draft(token))

	def test_a_full_cache_clear_keeps_the_draft(self):
		"""hooks.py persistent_cache_keys keeps DRAFT_KEY, for example through a Church Features save."""
		self.as_user(EDITOR)
		token = get_token(propose("Group", {"group_name": "_Test Drafts Mine"})["url"])
		frappe.clear_cache()
		self.assertTrue(get_draft(token))

	def test_fields_the_caller_cannot_write_and_docstatus_are_dropped_and_listed(self):
		"""Church Staff create prayer requests, but only permlevel 1 roles set their status."""
		self.as_user(STAFF)
		result = propose(
			"Prayer Request",
			{
				"title": "_Test Drafts Prayer",
				"status": "Approved",
				"approved_for_list": 1,
				"prayer_count": 9,
				"docstatus": 1,
				"amended_from": "PREQ-0001",
				"owner": MANAGER,
				"no_such_field": "x",
			},
		)
		self.assertEqual(
			sorted(result["dropped"]),
			[
				"amended_from",
				"approved_for_list",
				"docstatus",
				"no_such_field",
				"owner",
				"prayer_count",
				"status",
			],
		)
		self.assertEqual(get_draft(get_token(result["url"]))["values"], {"title": "_Test Drafts Prayer"})

	def test_a_church_email_draft_cannot_send(self):
		"""ChurchEmail.send moves the status, and Send At moves a scheduled message."""
		self.as_user(MANAGER)
		result = propose(
			"Church Email",
			{"subject": "Welcome", "message": "<p>Hi</p>", "status": "Sending", "send_after": "2020-01-01"},
		)
		self.assertEqual(sorted(result["dropped"]), ["send_after", "status"])

		values = get_draft(get_token(result["url"]))["values"]
		module = "churchit.church_communications.doctype.church_email.church_email"
		with mock.patch(f"{module}.enqueue_delivery") as delivery, mock.patch("frappe.sendmail") as sendmail:
			email = frappe.get_doc({"doctype": "Church Email", **values}).insert()
		self.assertEqual((email.status, email.send_after), ("Draft", None))
		delivery.assert_not_called()
		sendmail.assert_not_called()

	def test_a_follow_up_workflow_draft_is_never_active(self):
		"""An active workflow opens cards and sends its messages by itself."""
		self.as_user(MANAGER)
		values = {"workflow_name": "_Test Drafts Workflow", "steps": [{"step": "Call"}], "is_active": 1}
		result = propose("Follow-up Workflow", values)
		self.assertEqual(result["dropped"], ["is_active"])
		self.assertNotIn("is_active", get_draft(get_token(result["url"]))["values"])

		# Active defaults to on, so a draft keeps Active off.
		result = propose("Follow-up Workflow", {**values, "is_active": 0})
		self.assertEqual(result["dropped"], [])
		self.assertEqual(get_draft(get_token(result["url"]))["values"]["is_active"], 0)

	def test_a_birth_date_is_drafted_as_a_birth_life_event(self):
		"""derived.sync_derived sets the read-only birth_date from the first Birth row (people.md)."""
		self.as_user(EDITOR)
		birth = {"event_type": "Birth", "date": "2015-04-02"}
		result = propose("Person", {"birth_date": "2015-04-02", "life_events": [birth]}, self.person)
		self.assertEqual(result["dropped"], ["birth_date"])
		self.assertEqual(get_draft(get_token(result["url"]))["values"], {"life_events": [birth]})

	def test_rows_are_added_or_change_the_row_they_name(self):
		self.as_user(EDITOR)
		newcomer = make_person("_Test Drafts", "Newcomer", church=self.church).name
		row = frappe.get_doc("Group", self.group).members[0].name
		result = propose(
			"Group",
			{
				"members": [
					{"person": newcomer, "no_such_field": 1},
					{"name": row, "group_role": "Leader"},
					{"name": "not-a-row-of-this-group", "person": newcomer},
					"not a row",
				]
			},
			self.group,
		)
		self.assertEqual(sorted(result["dropped"]), ["members", "members.name", "members.no_such_field"])
		self.assertEqual(
			get_draft(get_token(result["url"]))["values"]["members"],
			[{"person": newcomer}, {"group_role": "Leader", "name": row}, {"person": newcomer}],
		)

	def test_an_edit_draft_opens_the_record_and_needs_write(self):
		self.as_user(EDITOR)
		url = propose("Group", {"group_name": "_Test Drafts Renamed"}, self.group)["url"]
		self.assertTrue(url.startswith(get_url_to_form("Group", self.group) + "?ai_draft="))

		self.as_user(STAFF)
		self.assertRaises(frappe.PermissionError, propose, "Group", {"group_name": "x"}, self.group)
		self.assertRaises(frappe.PermissionError, propose, "Group", {"group_name": "x"})

	def test_a_single_draft_changes_its_one_record(self):
		"""The desk has no new form for a Single, so the draft opens the settings themselves."""
		self.as_user(MANAGER)
		result = propose("People Settings", {"adult_age": 19})
		form = get_url_to_form("People Settings", "People Settings")
		self.assertTrue(result["url"].startswith(f"{form}?ai_draft="))
		self.assertEqual(get_draft(get_token(result["url"]))["name"], "People Settings")

	def test_another_churchs_record_is_refused(self):
		other = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Drafts Other Group", "church": self.other_church}
		).insert(ignore_permissions=True)
		self.as_user(EDITOR)
		self.assertRaises(frappe.PermissionError, propose, "Group", {"group_name": "x"}, other.name)

	def test_a_draft_of_a_record_that_changed_is_stale(self):
		self.as_user(EDITOR)
		token = get_token(propose("Group", {"group_name": "_Test Drafts Renamed"}, self.group)["url"])
		self.assertFalse(get_draft(token)["stale"])

		group = frappe.get_doc("Group", self.group)
		group.description = "Changed after the draft"
		group.save()
		self.assertTrue(get_draft(token)["stale"])


class TestLabelSaved(DraftTestCase):
	def save_new_group(self, source: str | None = None) -> tuple[str, str]:
		"""As the editor: draft a new group, save it from the draft, and return its name and token."""
		self.as_user(EDITOR)
		values = {"group_name": "_Test Drafts Saved Group", "church": self.church}
		result = make_draft("Group", values, source=source) if source else propose("Group", values)
		token = get_token(result["url"])
		name = frappe.get_doc({"doctype": "Group", **get_draft(token)["values"]}).insert().name
		return name, token

	def test_the_first_save_adds_one_info_comment_and_a_second_call_none(self):
		name, token = self.save_new_group()
		self.assertTrue(label_saved("Group", name, token))
		self.assertFalse(label_saved("Group", name, token))
		self.assertEqual(get_labels("Group", name), [LABEL])

	def test_a_forged_token_adds_nothing(self):
		name, _token = self.save_new_group()
		self.assertFalse(label_saved("Group", name, "0" * 32))
		self.assertEqual(get_labels("Group", name), [])

	def test_another_users_token_adds_nothing(self):
		name, token = self.save_new_group()
		frappe.set_user(OTHER_EDITOR)
		self.assertFalse(label_saved("Group", name, token))
		self.assertEqual(get_labels("Group", name), [])

	def test_a_draft_names_its_own_record(self):
		_name, token = self.save_new_group()
		self.assertFalse(label_saved("Group", self.group, token))
		self.assertEqual(get_labels("Group", self.group), [])

	def test_an_edit_draft_is_labelled_only_after_a_save(self):
		self.as_user(EDITOR)
		token = get_token(propose("Group", {"group_name": "_Test Drafts Renamed"}, self.group)["url"])
		self.assertFalse(label_saved("Group", self.group, token))

		group = frappe.get_doc("Group", self.group)
		group.update(get_draft(token)["values"])
		group.save()
		self.assertTrue(label_saved("Group", self.group, token))
		self.assertEqual(get_labels("Group", self.group), [LABEL])

	def test_the_label_names_the_source_of_a_churchit_draft(self):
		name, token = self.save_new_group(source="<b>qwen2.5</b>")
		label_saved("Group", name, token)
		self.assertEqual(get_labels("Group", name), ["Drafted with AI help (&lt;b&gt;qwen2.5&lt;/b&gt;)."])

	def test_label_needs_write_on_the_record(self):
		name, token = self.save_new_group()
		frappe.set_user(STAFF)
		self.assertRaises(frappe.PermissionError, label_saved, "Group", name, token)


class TestDraftRefusals(DraftTestCase):
	def calls(self) -> list:
		return [
			lambda: propose("Group", {"group_name": "x"}),
			lambda: make_draft("Group", {"group_name": "x"}),
			lambda: get_draft("0" * 32),
			lambda: label_saved("Group", self.group, "0" * 32),
		]

	def test_every_method_refuses_while_ai_is_off(self):
		frappe.db.set_single_value(SETTINGS, "enabled", 0)
		self.as_user(EDITOR)
		for call in self.calls():
			self.assertRaisesRegex(frappe.PermissionError, "AI is turned off", call)

	def test_every_method_refuses_a_website_user_and_a_guest(self):
		for user in (WEBSITE_USER, "Guest"):
			self.as_user(user)
			for call in self.calls():
				self.assertRaises(frappe.PermissionError, call)

	def test_a_table_cannot_be_drafted_alone(self):
		self.as_user(EDITOR)
		self.assertRaises(frappe.ValidationError, make_draft, "Group Member", {"person": self.person})
