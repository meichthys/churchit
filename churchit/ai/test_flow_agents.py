# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's agents in Flow: when Flow writes them, which tools Church Office has, and what each
tool does for the person who chats.

Runs only on a Frappe with Flow, and never calls a model. The tests reach Flow by dotted path
(frappe.call, frappe.get_attr, mock.patch) and through churchit.ai.flow, never by an import of
frappe.flow.
"""

import json
import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.ai import drafts
from churchit.ai.exposure import get_churchit_agent_lines
from churchit.ai.flow_models import is_flow_ready
from churchit.ai.manual_knowledge import KNOWLEDGE_BASE
from churchit.ai.switch import SETTINGS, has_flow
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

OFFICE = "churchit/Church Office"
AGENTS = (OFFICE, "churchit/Writer", "churchit/Private Work")
# Flow's own steps: its sync after migrate, its model check on save and its call of a tool.
FLOW_SYNC_AGENTS = "frappe.flow.lib.agent.sync_agents"
DETECT_CONTEXT_WINDOW = "frappe.flow.doctype.flow_model.flow_model._detect_context_window"
TOOL_CALLBACK = "frappe.flow.daemon.callback.tool_callback"
OFFICE_TOOLS = {
	"churchit__get_agent_guide",
	"churchit__propose",
	"churchit__get_smart_list_url",
	"churchit__get_smart_list_people",
	"churchit__first_time_guests_without_follow_up",
	"churchit__people_not_seen",
	"churchit__birthdays_and_anniversaries",
	"churchit__groups_needing_attention",
	"churchit__get_open_needs",
	"churchit__get_week_overview",
	"churchit__get_person_briefing",
	"churchit__get_group_briefing",
	"find_doctypes",
	"describe",
	"read_records",
	"run_report",
	"read_screen",
	"load_skill",
}
MODEL = "_Test Church Office Model"
STAFF_A = "_test_office_staff_a@example.com"
STAFF_B = "_test_office_staff_b@example.com"
MANAGER_A = "_test_office_manager_a@example.com"
NO_RIGHTS = "_test_office_flow_only@example.com"
WEBSITE_USER = "_test_office_website_user@example.com"
GROUP_NAME = "_Test Office Draft Group"
AGENTS_LINE = "Churchit agents in Flow"
MANUAL_LINE = "Churchit Manual in Flow knowledge"


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value(SETTINGS, "enabled", enabled)


def insert_model(name: str, **values) -> str:
	"""A Flow Model saved without its controller, so no hook runs."""
	model = {"doctype": "Flow Model", "name": name, "title": name, "model_id": "ollama/_test", "enabled": 1}
	frappe.get_doc({**model, **values}).db_insert()
	return name


class FlowAgentsTestCase(RollbackEachTest):
	"""No churchit agent and no enabled model at the start of each test."""

	@classmethod
	def setUpClass(cls):
		if not has_flow():
			raise unittest.SkipTest("This Frappe has no Flow.")
		super().setUpClass()

	def setUp(self):
		super().setUp()
		from churchit.ai import flow

		self.flow = flow
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		for agent in AGENTS:
			if frappe.db.exists("Flow Agent", agent):
				frappe.delete_doc("Flow Agent", agent, ignore_permissions=True, force=True)

	def get_agents(self) -> list[str]:
		return [agent for agent in AGENTS if frappe.db.exists("Flow Agent", agent)]


class TestAgents(FlowAgentsTestCase):
	def test_there_is_no_agent_without_an_enabled_chat_model(self):
		self.assertEqual(self.flow.agents(), [])

		insert_model("_Test Office Embedding Model", embedding=1)
		self.assertEqual(self.flow.agents(), [])

	def test_saving_a_chat_model_writes_the_agents(self):
		with patch(DETECT_CONTEXT_WINDOW, return_value=8192):
			frappe.get_doc(
				{
					"doctype": "Flow Model",
					"title": MODEL,
					"model_id": "ollama_chat/test-office",
					"enabled": 1,
				}
			).insert()

		self.assertEqual(self.get_agents(), list(AGENTS))
		for agent in AGENTS:
			self.assertEqual(
				frappe.db.get_value("Flow Agent", agent, ["model", "is_system_generated"]), (MODEL, 1)
			)

	def test_saving_an_embedding_model_writes_no_agent(self):
		with patch(DETECT_CONTEXT_WINDOW, return_value=8192):
			frappe.get_doc(
				{
					"doctype": "Flow Model",
					"title": MODEL,
					"model_id": "ollama/test-office",
					"enabled": 1,
					"embedding": 1,
				}
			).insert()

		self.assertEqual(self.get_agents(), [])

	def test_flows_sync_after_migrate_writes_the_agents(self):
		self.assertIn(FLOW_SYNC_AGENTS, frappe.get_hooks("after_migrate"))
		insert_model(MODEL)

		frappe.get_attr(FLOW_SYNC_AGENTS)()

		self.assertEqual(self.get_agents(), list(AGENTS))

	def test_church_office_reads_and_drafts_and_the_others_have_no_tools(self):
		insert_model(MODEL)
		self.flow.sync_agents()

		office = frappe.get_doc("Flow Agent", OFFICE)
		tools = office.client_tools()
		self.assertEqual({tool.name for tool in tools}, OFFICE_TOOLS)
		self.assertEqual(office.client_tool_config()["confirm_tools"], [], "Nothing in it writes")
		self.assertEqual(office.server_tools(), [], "No web search, web fetch or sub-agents")
		self.assertEqual([row.skill for row in office.skills], ["churchit/churchit"])
		for agent in AGENTS[1:]:
			self.assertEqual(frappe.get_doc("Flow Agent", agent).client_tools(), [])

	def test_flow_is_ready_once_the_agents_are_synced(self):
		insert_model(MODEL)
		self.assertFalse(is_flow_ready())

		self.flow.sync_agents()
		self.assertTrue(is_flow_ready())

	def test_the_ai_access_panel_says_whether_the_agents_and_the_manual_are_ready(self):
		insert_model(MODEL)
		frappe.db.set_single_value("Flow Knowledge Settings", "embedding_model", None)
		self.assertEqual(
			get_panel_states(),
			{AGENTS_LINE: "Not ready", MANUAL_LINE: "Needs an embedding model"},
		)

		self.flow.sync_agents()
		frappe.get_doc(
			{"doctype": "Flow Knowledge Base", "name": KNOWLEDGE_BASE, "title": KNOWLEDGE_BASE}
		).db_insert()
		self.assertEqual(get_panel_states(), {AGENTS_LINE: "Ready", MANUAL_LINE: "Added"})


class TestPanelWithoutFlow(FrappeTestCase):
	def test_the_panel_has_no_line_for_churchits_agents_without_flow(self):
		with patch("churchit.ai.exposure.has_flow", return_value=False):
			self.assertEqual(get_churchit_agent_lines(), [])


class TestOfficeTools(FlowAgentsTestCase):
	"""Each tool runs its churchit function as the person who chats, with that person's rights."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.staff_a = church_user(STAFF_A, ("Church Staff", "Flow User"), cls.church_a)
		cls.staff_b = church_user(STAFF_B, ("Church Staff", "Flow User"), cls.church_b)
		cls.manager_a = church_user(MANAGER_A, ("Church Manager", "Flow User"), cls.church_a)
		cls.no_rights = ensure_user(NO_RIGHTS, "Office Flow Only", roles=("Flow User",))
		cls.website_user = ensure_user(WEBSITE_USER, "Office Website", roles=())
		cls.person_a = make_person("_Test Office", "Person A", church=cls.church_a).name
		cls.person_b = make_person("_Test Office", "Person B", church=cls.church_b).name
		cls.group_a = make_group("_Test Office Group A", cls.church_a)
		cls.group_b = make_group("_Test Office Group B", cls.church_b)

	def setUp(self):
		super().setUp()
		set_ai(1)
		insert_model(MODEL)
		self.flow.sync_agents()

	def get_arguments(self) -> dict[str, dict]:
		"""Arguments for each churchit tool, by its function name."""
		return {
			"get_agent_guide": {},
			"propose": {"doctype": "Group", "values": {"group_name": GROUP_NAME}},
			"get_smart_list_url": {"filters": [["Person", "first_name", "=", "_Test Office"]]},
			"get_smart_list_people": {"report": "_Test Office Report"},
			"first_time_guests_without_follow_up": {},
			"people_not_seen": {},
			"birthdays_and_anniversaries": {},
			"groups_needing_attention": {},
			"get_open_needs": {},
			"get_week_overview": {},
			"get_person_briefing": {"person": self.person_a},
			"get_group_briefing": {"group": self.group_a},
		}

	def call_as(self, user: str, tool: str, **arguments):
		"""Run a churchit tool as Flow does: as the person who chats, with the chat's context."""
		frappe.set_user(user)
		try:
			context = self.flow.ToolContext(session_id="_test", agent=OFFICE, user=user)
			return getattr(self.flow, tool)(**arguments, ctx=context)
		finally:
			frappe.set_user("Administrator")

	def test_each_tool_refuses_while_ai_is_off(self):
		set_ai(0)

		for tool, arguments in self.get_arguments().items():
			with self.subTest(tool=tool):
				self.assertRaises(frappe.PermissionError, self.call_as, self.manager_a, tool, **arguments)

	def test_each_tool_refuses_a_website_user(self):
		for tool, arguments in self.get_arguments().items():
			with self.subTest(tool=tool):
				self.assertRaises(frappe.PermissionError, self.call_as, self.website_user, tool, **arguments)

	def test_a_tool_refuses_a_desk_user_without_the_right(self):
		arguments = self.get_arguments()
		for tool in ("propose", "get_person_briefing", "get_group_briefing"):
			with self.subTest(tool=tool):
				self.assertRaises(
					frappe.PermissionError, self.call_as, self.no_rights, tool, **arguments[tool]
				)

	def test_two_churches_get_their_own_people_and_groups(self):
		"""Every church reads the whole directory, but a count of people covers the reader's churches."""
		filters = [["Person", "first_name", "=", "_Test Office"]]
		readers = ((self.staff_a, self.group_a, self.group_b), (self.staff_b, self.group_b, self.group_a))
		for reader, mine, theirs in readers:
			with self.subTest(reader=reader):
				self.assertEqual(self.call_as(reader, "get_smart_list_url", filters=filters)["count"], 1)
				self.assertEqual(self.call_as(reader, "get_group_briefing", group=mine)["group"], mine)
				self.assertRaises(
					frappe.PermissionError, self.call_as, reader, "get_group_briefing", group=theirs
				)

	def test_a_new_group_request_returns_a_draft_link_and_saves_nothing(self):
		chat = frappe.get_doc(
			{
				"doctype": "Flow Session",
				"name": "_Test Office Chat",
				"title": "_Test",
				"agent": OFFICE,
				"model": MODEL,
			}
		)
		chat.db_insert()
		chat.db_set("owner", self.manager_a, update_modified=False)

		answer = frappe.call(
			TOOL_CALLBACK,
			session_id=chat.name,
			tool="churchit__propose",
			args={"doctype": "Group", "values": {"group_name": GROUP_NAME}},
		)

		self.assertFalse(answer["is_error"], answer["content"])
		url = json.loads(answer["content"])["url"]
		self.assertIn("?ai_draft=", url)
		self.assertFalse(frappe.db.exists("Group", {"group_name": GROUP_NAME}))
		frappe.set_user(self.manager_a)
		draft = drafts.get_saved_draft(url.split("ai_draft=")[1])
		self.assertEqual((draft["values"], draft["source"]), ({"group_name": GROUP_NAME}, MODEL))


def church_user(email: str, roles: tuple, church: str) -> str:
	ensure_user(email, "Office", roles)
	set_user_church(email, church)
	return email


def make_group(group_name: str, church: str) -> str:
	group = {"doctype": "Group", "group_name": group_name, "church": church}
	return frappe.get_doc(group).insert(ignore_permissions=True).name


def get_panel_states() -> dict[str, str]:
	return {line["surface"]: line["state"] for line in get_churchit_agent_lines()}
