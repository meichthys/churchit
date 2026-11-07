# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch over Flow: no chat, turn, trigger or new knowledge while AI is off, chats
that ask before changes, no knowledge from church records, and the Flow lines of the exposure panel.

The tests reach Flow by dotted path, through frappe.call and mock.patch, as the desk and a trigger's
job do, so no churchit module imports frappe.flow (ai/test_flow.py). A mock stands in for the flow
server, and no test calls a model.
"""

import unittest
from unittest.mock import patch
from urllib.parse import quote

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.ai.exposure import get_exposure
from churchit.ai.flow_switch import GUEST_DOCTYPES, PEOPLE_DOCTYPES, is_church_doctype
from churchit.ai.switch import SETTINGS, has_flow
from churchit.tests.helpers import RollbackEachTest, ensure_user

AI_OFF = "AI is turned off on this site."
CREATE_SESSION = "frappe.flow.api.create_session"
OPEN_SESSION = "frappe.flow.api.session"
RUN = "frappe.flow.api.run"
BOOT = "frappe.flow.api.boot"
NEW_SESSION = "frappe.flow.lib.session.new_session"
FIRE_TRIGGER = "frappe.flow.triggers.fire"
FLOW_SERVER = "frappe.flow.daemon.client.DaemonClient.for_site"
FLOW_USER = "_test_flow_switch_user@example.com"
FLOW_MANAGER = "_test_flow_switch_manager@example.com"
CHURCH_MANAGER = "_test_flow_switch_church_manager@example.com"


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value(SETTINGS, "enabled", enabled)


def get_messages() -> str:
	return " ".join(str(message.get("message")) for message in frappe.local.message_log)


def get_warnings() -> list[str]:
	return [
		str(message.message) for message in frappe.local.message_log if message.get("indicator") == "orange"
	]


def insert_without_controller(doctype: str, name: str, **values) -> str:
	"""Save a Flow record without its controller: a saved model sets up Flow's Assistant and asks
	its provider about itself, and a saved knowledge source starts reading at once."""
	frappe.get_doc({"doctype": doctype, "name": name, "title": name, **values}).db_insert()
	return name


class FlowTestCase(RollbackEachTest):
	"""A chat model, an agent, a Flow User and a System Manager, on a Frappe with Flow."""

	@classmethod
	def setUpClass(cls):
		if not has_flow():
			raise unittest.SkipTest("This Frappe has no Flow.")
		super().setUpClass()
		cls.flow_user = ensure_user(FLOW_USER, "Flow Chat", roles=("Flow User",))
		cls.manager = ensure_user(FLOW_MANAGER, "Flow Manager", roles=("System Manager",))
		cls.model = insert_without_controller(
			"Flow Model", "_Test Flow Switch Model", model_id="ollama/_test_flow_switch", enabled=1
		)
		cls.agent = insert_without_controller(
			"Flow Agent", "_Test Flow Switch Agent", model=cls.model, instructions="Be brief.", enabled=1
		)

	def setUp(self):
		super().setUp()
		self.flow_server = self.enterContext(patch(FLOW_SERVER)).return_value.__enter__.return_value
		frappe.clear_messages()

	def call_as(self, user: str, method: str, **kwargs):
		"""Call a Flow endpoint as *user*, as the desk does."""
		frappe.set_user(user)
		try:
			return frappe.call(method, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def start_chat(self, user: str, approval_mode: str | None = None) -> dict:
		set_ai(1)
		return self.call_as(user, CREATE_SESSION, agent=self.agent, approval_mode=approval_mode)

	def has_chats(self) -> bool:
		return bool(frappe.db.exists("Flow Session", {"agent": self.agent}))


class TestFlowChatsFollowTheSwitch(FlowTestCase):
	def test_ai_off_refuses_a_new_chat_and_says_why(self):
		set_ai(0)
		for user in (self.flow_user, self.manager, "Administrator"):
			frappe.clear_messages()
			self.assertRaises(frappe.PermissionError, self.call_as, user, CREATE_SESSION, agent=self.agent)
			self.assertIn(AI_OFF, get_messages(), user)
		self.assertFalse(self.has_chats())
		self.flow_server.create_session.assert_not_called()

	def test_ai_off_refuses_a_new_turn_of_an_old_chat_and_keeps_it_readable(self):
		"""Flow gives write on a chat only to its owner, so Frappe's second check, on the doctype,
		replaces the sentence with Frappe's own refusal."""
		for user in (self.flow_user, self.manager):
			chat = self.start_chat(user)["name"]
			set_ai(0)
			self.assertRaises(frappe.PermissionError, self.call_as, user, RUN, session=chat, message="Hello")
			self.assertTrue(self.call_as(user, OPEN_SESSION, session=chat)["read_only"], user)
		self.flow_server.run.assert_not_called()

	def test_ai_off_lets_administrator_continue_an_old_chat(self):
		"""Flow checks write on a chat for a new turn and for Stop. Frappe never asks a has_permission
		hook about Administrator, as the manual says."""
		chat = self.start_chat("Administrator")["name"]
		set_ai(0)
		self.assertTrue(frappe.has_permission("Flow Session", "write", chat, user="Administrator"))

	def test_ai_off_stops_a_trigger_that_runs_as_administrator(self):
		set_ai(1)
		trigger = make_trigger(
			self.agent, event="Scheduled", cron_expression="0 3 * * *", run_as="Administrator"
		)
		trigger.insert()

		set_ai(0)
		frappe.clear_messages()
		self.assertRaises(frappe.PermissionError, frappe.call, FIRE_TRIGGER, trigger=trigger.name)
		self.assertIn(AI_OFF, get_messages())
		self.assertFalse(self.has_chats())

	def test_ai_off_hides_every_agent(self):
		set_ai(0)
		self.assertEqual(self.call_as(self.flow_user, BOOT)["agents"], [])
		self.assertEqual(frappe.get_list("Flow Agent", pluck="name"), [])
		self.assertFalse(frappe.has_permission("Flow Agent", "read", self.agent, user=self.manager))

		set_ai(1)
		agents = [agent.name for agent in self.call_as(self.flow_user, BOOT)["agents"]]
		self.assertIn(self.agent, agents)
		self.assertTrue(frappe.has_permission("Flow Agent", "read", self.agent, user=self.manager))

	def test_ai_on_starts_a_persons_chat_in_ask(self):
		for user in (self.flow_user, self.manager):
			for asked, approval_mode in ((None, "Ask"), ("Auto", "Ask"), ("Auto-approve", "Auto-approve")):
				self.assertEqual(self.start_chat(user, asked)["approval_mode"], approval_mode, (user, asked))
		self.assertEqual(self.flow_server.create_session.call_args_list[0].args[0]["approval_mode"], "ask")

	def test_ai_on_leaves_a_trigger_chat_to_approve_its_own_changes(self):
		"""Flow gives a trigger's chat Auto-approve, since nobody is there to answer."""
		set_ai(1)
		chat = frappe.call(NEW_SESSION, agent=self.agent, source="Trigger")
		self.assertEqual(chat.approval_mode, "Auto-approve")


def make_trigger(agent: str, **values):
	return frappe.get_doc(
		{
			"doctype": "Flow Trigger",
			"title": "_Test Flow Switch Trigger",
			"agent": agent,
			"event": "DocType Event",
			"target_doctype": "Note",
			"doc_event": "after_insert",
			"prompt_template": "Say hello.",
			**values,
		}
	)


class TestFlowTriggersFollowTheSwitch(FlowTestCase):
	def save_as_manager(self, trigger):
		frappe.set_user(self.manager)
		try:
			return trigger.save()
		finally:
			frappe.set_user("Administrator")

	def test_ai_off_refuses_enabling_a_trigger(self):
		set_ai(0)
		trigger = make_trigger(self.agent, run_as="Administrator")
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, trigger)

		trigger = make_trigger(self.agent, run_as=self.flow_user)
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, trigger)

	def test_ai_off_saves_a_disabled_trigger(self):
		set_ai(0)
		trigger = self.save_as_manager(make_trigger(self.agent, run_as=self.flow_user, enabled=0))
		self.assertFalse(trigger.enabled)

	def test_flows_sync_saves_an_apps_trigger_while_ai_is_off(self):
		"""Flow writes the triggers that apps ship in an update, and outside one when the first model
		arrives, each with ignore_permissions. It gives Administrator to one that names no Run As."""
		set_ai(0)
		trigger = make_trigger(
			self.agent,
			title="churchit/_Test Flow Switch Trigger",
			app="churchit",
			is_system_generated=1,
			run_as=self.flow_user,
		)
		with patch.dict(frappe.flags, {"in_migrate": True}):
			trigger.insert(ignore_permissions=True)
		self.assertTrue(trigger.enabled)

		trigger.run_as = "Administrator"
		trigger.save(ignore_permissions=True)
		self.assertTrue(frappe.db.get_value("Flow Trigger", trigger.name, "enabled"))

		person_edit = frappe.get_doc("Flow Trigger", trigger.name)
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, person_edit)

	def test_ai_on_warns_about_a_trigger_on_text_that_guests_write(self):
		set_ai(1)
		self.save_as_manager(make_trigger(self.agent, target_doctype="Prayer Request", run_as=self.flow_user))
		warnings = get_warnings()
		self.assertEqual(len(warnings), 1)
		self.assertIn("Prayer Request", warnings[0])

	def test_ai_on_warns_about_a_trigger_that_runs_as_administrator(self):
		set_ai(1)
		self.save_as_manager(make_trigger(self.agent, run_as="Administrator"))
		self.assertIn("runs as Administrator", " ".join(get_warnings()))

		frappe.clear_messages()
		make_trigger(self.agent, title="_Test Flow Switch Trigger 2").insert()
		self.assertIn("runs as Administrator", " ".join(get_warnings()))

	def test_ai_on_saves_a_trigger_that_needs_no_warning(self):
		"""A disabled trigger starts no chat, so unticking a risky one shows nothing."""
		set_ai(1)
		trigger = self.save_as_manager(make_trigger(self.agent, run_as=self.flow_user))
		self.assertTrue(trigger.enabled)
		disabled = make_trigger(
			self.agent,
			title="_Test Flow Switch Trigger Off",
			target_doctype="Prayer Request",
			run_as="Administrator",
			enabled=0,
		)
		self.save_as_manager(disabled)
		self.assertEqual(get_warnings(), [])


class TestFlowKnowledgeFollowsTheSwitch(FlowTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		embedding = insert_without_controller(
			"Flow Model", "_Test Flow Switch Embedding", model_id="ollama/_test_embed", enabled=1, embedding=1
		)
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", embedding)
		cls.addClassCleanup(frappe.clear_document_cache, "Flow Knowledge Settings", "Flow Knowledge Settings")
		cls.knowledge = insert_without_controller(
			"Flow Knowledge Base", "_Test Flow Switch Knowledge", enabled=1
		)

	def make_source(self, **values):
		source = {
			"doctype": "Flow Knowledge Source",
			"title": "_Test Source",
			"knowledge_base": self.knowledge,
		}
		return frappe.get_doc({**source, "source_type": "Text", "content": "We meet on Sunday.", **values})

	def make_doctype_source(self, doctype: str, fields: str, **values):
		return self.make_source(
			source_type="DocType", reference_doctype=doctype, content_fields=fields, **values
		)

	def save_as_manager(self, source):
		frappe.set_user(self.manager)
		try:
			return source.save()
		finally:
			frappe.set_user("Administrator")

	def test_ai_off_refuses_a_new_knowledge_source(self):
		set_ai(0)
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, self.make_source())

	def test_ai_off_refuses_a_change_that_flow_reads_again(self):
		set_ai(1)
		text = self.save_as_manager(self.make_source())
		pages = self.save_as_manager(self.make_doctype_source("Web Page", "title", auto_sync=1))
		set_ai(0)

		text.content = "We meet on Saturday."
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, text)
		text.reload()
		text.title = "_Test Source Renamed"
		self.save_as_manager(text)

		pages.auto_sync = 0
		self.save_as_manager(pages)
		pages.auto_sync = 1
		self.assertRaisesRegex(frappe.ValidationError, AI_OFF, self.save_as_manager, pages)

	def test_ai_on_refuses_a_doctype_source_on_church_records(self):
		set_ai(1)
		for doctype, fields in (
			("Person", "first_name"),
			("Contact", "first_name"),
			("Prayer Request", "title"),
		):
			source = self.make_doctype_source(doctype, fields)
			self.assertRaisesRegex(
				frappe.ValidationError, "cannot read church records", self.save_as_manager, source
			)
		self.assertTrue(self.save_as_manager(self.make_doctype_source("Web Page", "title")).name)

	def test_an_older_source_on_church_records_can_stop_its_daily_copy(self):
		"""A source made before the rule may be renamed or lose Auto Sync; no save makes Flow read it."""
		set_ai(1)
		older = {"knowledge_base": self.knowledge, "source_type": "DocType", "auto_sync": 1}
		name = insert_without_controller(
			"Flow Knowledge Source",
			"_Test Older Person Source",
			reference_doctype="Person",
			content_fields="first_name",
			**older,
		)
		source = frappe.get_doc("Flow Knowledge Source", name)
		source.title = "_Test Older Person Source Renamed"
		source.auto_sync = 0
		self.save_as_manager(source)

		source.auto_sync = 1
		self.assertRaisesRegex(
			frappe.ValidationError, "cannot read church records", self.save_as_manager, source
		)

	def test_ai_on_accepts_a_text_source(self):
		set_ai(1)
		self.assertEqual(self.save_as_manager(self.make_source()).status, "Pending")

	def test_an_update_saves_an_apps_text_but_never_church_records(self):
		"""An app's update may add knowledge while AI is off, but never a copy of church records."""
		set_ai(0)
		with patch.dict(frappe.flags, {"in_migrate": True}):
			self.assertTrue(self.make_source().insert(ignore_permissions=True).name)
			source = self.make_doctype_source("Person", "first_name")
			self.assertRaisesRegex(
				frappe.ValidationError, "cannot read church records", source.insert, ignore_permissions=True
			)


class TestChurchRecords(FrappeTestCase):
	def test_church_doctypes_are_churchits_and_frappes_people_records(self):
		for doctype in ("Person", "Family Members", "Counseling Case", "Contact", "Deleted Document"):
			self.assertTrue(is_church_doctype(doctype), doctype)
		for doctype in ("Web Page", "Note", "_Test No Such Doctype", None):
			self.assertFalse(is_church_doctype(doctype), doctype)

	def test_the_named_doctypes_exist(self):
		for doctype in (*GUEST_DOCTYPES, *PEOPLE_DOCTYPES):
			self.assertTrue(frappe.db.exists("DocType", doctype), doctype)


class TestFlowExposure(RollbackEachTest):
	def lines(self, user: str = "Administrator") -> dict[str, dict]:
		frappe.set_user(user)
		try:
			return {line["surface"]: line for line in get_exposure()}
		finally:
			frappe.set_user("Administrator")

	def test_without_flow_the_panel_says_so(self):
		with patch("churchit.ai.exposure.has_flow", return_value=False):
			lines = self.lines()
		self.assertEqual(lines["Flow"]["state"], "Not available")
		self.assertNotIn("Flow triggers", lines)


class TestFlowExposureWithFlow(FlowTestCase):
	def lines(self, user: str) -> dict[str, dict]:
		frappe.set_user(user)
		try:
			return {line["surface"]: line for line in get_exposure()}
		finally:
			frappe.set_user("Administrator")

	def test_the_flow_line_follows_the_switch(self):
		for enabled in (0, 1):
			set_ai(enabled)
			line = self.lines(self.manager)["Flow"]
			self.assertEqual(line["open"], bool(enabled))
			self.assertIn("chat button", line["note"])

	def test_a_system_manager_sees_who_may_use_flow(self):
		before = self.lines(self.manager)["People who may use Flow"]["state"]
		ensure_user("_test_flow_switch_user_2@example.com", "Flow Chat", roles=("Flow User",))
		ensure_user("_test_flow_switch_staff@example.com", "Flow Staff", roles=("Church Staff",))

		line = self.lines(self.manager)["People who may use Flow"]
		self.assertEqual(int(line["state"].split()[0]), int(before.split()[0]) + 1)
		self.assertIn("Flow+User", line["link"])

	def test_a_system_manager_sees_older_knowledge_from_church_records(self):
		knowledge = insert_without_controller("Flow Knowledge Base", "_Test Flow Switch Old Knowledge")
		older = {"knowledge_base": knowledge, "source_type": "DocType", "content_fields": "first_name"}
		person = insert_without_controller(
			"Flow Knowledge Source", "_Test Older Person Source", reference_doctype="Person", **older
		)
		insert_without_controller(
			"Flow Knowledge Source", "_Test Older Page Source", reference_doctype="Web Page", **older
		)

		lines = self.lines(self.manager)
		line = lines["Flow knowledge from church records: _Test Older Person Source"]
		self.assertTrue(line["open"])
		self.assertEqual(line["link"], f"/app/flow-knowledge-source/{quote(person)}")
		self.assertNotIn("_Test Older Page Source", frappe.as_json(lines))

	def test_a_system_manager_sees_how_many_triggers_are_enabled(self):
		def state() -> str:
			return self.lines(self.manager)["Flow triggers"]["state"]

		before = state()
		trigger = make_trigger(self.agent, run_as="Administrator", enabled=1)
		trigger.name = trigger.title
		trigger.db_insert()
		count = 0 if before == "None" else int(before.split()[0])
		self.assertEqual(state(), f"{count + 1} enabled")

	def test_a_system_manager_sees_each_enabled_trigger_to_check(self):
		"""An update saves an app's trigger without the warning, and Flow gives it Administrator when
		the app names no Run As."""
		set_ai(0)
		app_trigger = make_trigger(
			self.agent,
			title="churchit/_Test Flow Switch App Trigger",
			app="churchit",
			is_system_generated=1,
			run_as="Administrator",
		)
		with patch.dict(frappe.flags, {"in_migrate": True}):
			app_trigger.insert(ignore_permissions=True)
		set_ai(1)
		guests = make_trigger(
			self.agent,
			title="_Test Flow Switch Guest Trigger",
			target_doctype="Prayer Request",
			run_as=self.flow_user,
		).insert()
		make_trigger(self.agent, title="_Test Flow Switch Plain Trigger", run_as=self.flow_user).insert()
		make_trigger(
			self.agent, title="_Test Flow Switch Off Trigger", run_as="Administrator", enabled=0
		).insert()

		lines = self.lines(self.manager)

		line = lines[f"Flow trigger to check: {app_trigger.name}"]
		self.assertTrue(line["open"])
		self.assertIn("runs as Administrator", line["note"])
		self.assertEqual(line["link"], f"/app/flow-trigger/{quote(app_trigger.name)}")
		self.assertIn("Prayer Request", lines[f"Flow trigger to check: {guests.name}"]["note"])
		for title in ("_Test Flow Switch Plain Trigger", "_Test Flow Switch Off Trigger"):
			self.assertNotIn(f"Flow trigger to check: {title}", lines)

	def test_a_church_manager_asks_a_system_manager(self):
		manager = ensure_user(CHURCH_MANAGER, "Flow Church Manager", roles=("Church Manager",))
		lines = self.lines(manager)
		self.assertIn("Flow", lines)
		self.assertEqual(lines["Flow chats ask before changes"]["state"], "Ask")
		for surface in ("People who may use Flow", "Flow knowledge from church records", "Flow triggers"):
			self.assertEqual(lines[surface]["state"], "Ask a System Manager")
