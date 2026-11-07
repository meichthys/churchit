# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who may turn AI on or unblock a doctype, the acknowledgment, MCP closing when AI turns off, and the
form's warnings."""

import json
import re
from pathlib import Path

import frappe
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
from frappe.tests.utils import FrappeTestCase

from churchit.ai.switch import SETTINGS, extend_bootinfo, is_ai_on
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

BRANCH_MANAGER = "_test_ai_branch_manager@example.com"
CHURCH_MANAGER = "_test_ai_church_manager@example.com"

FORM_FOLDER = Path(__file__).parent
FLOW_SECTIONS = ("warning_flow_agents_section", "warning_knowledge_section", "knowledge_section")
ONE_LINE = 80
# What the manual and AGENTS.md say the form tells.
PROMISED = (
	"Revoke a connected app in the OAuth Bearer Token list",
	"Church AI User",
	"frappe/Flow",
	"Webhooks and Server Scripts",
	"Flow does not check who may read each record",
)


def turn_on(acknowledged: int = 1):
	settings = frappe.get_single(SETTINGS)
	settings.enabled = 1
	settings.acknowledged = acknowledged
	settings.save()
	return settings


def turn_off():
	settings = frappe.get_single(SETTINGS)
	settings.enabled = 0
	settings.save()
	return settings


def make_branch_manager() -> str:
	"""A Church Manager of one branch church."""
	_root, branch, _other = make_two_churches()
	ensure_user(BRANCH_MANAGER, "AI Branch Manager", roles=("Church Manager",))
	frappe.get_doc(
		{"doctype": "User Permission", "user": BRANCH_MANAGER, "allow": "Church", "for_value": branch}
	).insert(ignore_permissions=True)
	return BRANCH_MANAGER


class TestChurchAISettings(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, {"enabled": 0, "acknowledged": 0})

	def tearDown(self):
		super().tearDown()
		clear_system_settings_cache()

	def test_turning_ai_on_needs_the_acknowledgment(self):
		self.assertRaisesRegex(frappe.ValidationError, "What an AI App Can See", turn_on, acknowledged=0)
		self.assertFalse(is_ai_on())

	def test_turning_ai_on_stamps_who_and_when(self):
		settings = turn_on()
		self.assertTrue(is_ai_on())
		self.assertEqual(settings.acknowledged_by, "Administrator")
		self.assertIsNotNone(settings.acknowledged_on)

	def test_turning_ai_off_clears_the_acknowledgment(self):
		turn_on()
		settings = turn_off()
		self.assertEqual(
			(settings.acknowledged, settings.acknowledged_by, settings.acknowledged_on), (0, None, None)
		)

	def test_a_save_that_leaves_ai_on_keeps_who_turned_it_on(self):
		"""Only turning AI on stamps it; a REST save of the stamp is ignored."""
		stamped = turn_on()
		settings = frappe.get_single(SETTINGS)
		settings.acknowledged_by = "Guest"
		settings.acknowledged_on = "2020-01-01 00:00:00"
		settings.save()

		self.assertEqual(frappe.db.get_single_value(SETTINGS, "acknowledged_by"), stamped.acknowledged_by)
		self.assertEqual(
			str(frappe.db.get_single_value(SETTINGS, "acknowledged_on")), str(stamped.acknowledged_on)
		)

	def test_turning_ai_on_leaves_mcp_as_it_is(self):
		for enable_mcp in (0, 1):
			frappe.db.set_single_value(SETTINGS, {"enabled": 0, "acknowledged": 0})
			frappe.db.set_single_value("System Settings", "enable_mcp", enable_mcp)
			turn_on()
			self.assertEqual(frappe.db.get_single_value("System Settings", "enable_mcp"), enable_mcp)

	def test_turning_ai_off_closes_mcp_and_says_so(self):
		turn_on()
		frappe.db.set_single_value("System Settings", "enable_mcp", 1)
		turn_off()
		self.assertEqual(frappe.db.get_single_value("System Settings", "enable_mcp"), 0)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{"reference_doctype": SETTINGS, "comment_type": "Info", "content": ("like", "%MCP%")},
			)
		)

	def test_a_branch_church_manager_cannot_turn_ai_on_but_can_turn_it_off(self):
		frappe.set_user(make_branch_manager())
		self.assertRaises(frappe.PermissionError, turn_on)
		frappe.set_user("Administrator")

		turn_on()
		frappe.set_user(BRANCH_MANAGER)
		turn_off()
		self.assertFalse(is_ai_on())

	def test_a_church_manager_of_every_church_can_turn_ai_on(self):
		make_two_churches()
		ensure_user(CHURCH_MANAGER, "AI Church Manager", roles=("Church Manager",))
		frappe.db.delete("User Permission", {"user": CHURCH_MANAGER, "allow": "Church"})
		frappe.clear_cache(user=CHURCH_MANAGER)

		frappe.set_user(CHURCH_MANAGER)
		turn_on()
		self.assertTrue(is_ai_on())

	def test_a_branch_church_manager_can_block_a_doctype_but_not_unblock_one(self):
		"""Unblocking loosens Flow knowledge for every church, as turning AI on does."""
		settings = frappe.get_single(SETTINGS)
		settings.blocked_knowledge_doctypes = []
		settings.append("blocked_knowledge_doctypes", {"document_type": "Person"})
		settings.save()

		frappe.set_user(make_branch_manager())
		settings = frappe.get_single(SETTINGS)
		settings.append("blocked_knowledge_doctypes", {"document_type": "Note"})
		settings.save()
		settings.blocked_knowledge_doctypes = settings.blocked_knowledge_doctypes[1:]
		self.assertRaisesRegex(frappe.PermissionError, "remove a DocType", settings.save)


class TestWarningSections(FrappeTestCase):
	"""Each warning is a closed Section Break titled "Warning: ..." that church_ai_settings.js fills."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fields = json.loads((FORM_FOLDER / "church_ai_settings.json").read_text())["fields"]
		cls.names = [field["fieldname"] for field in cls.fields]
		cls.sections = [
			field
			for field in cls.fields
			if field["fieldtype"] == "Section Break" and field["fieldname"].startswith("warning_")
		]

	def test_each_warning_is_a_closed_section_with_a_title_and_a_one_line_description(self):
		self.assertTrue(self.sections)
		for section in self.sections:
			with self.subTest(section["fieldname"]):
				self.assertTrue(section.get("collapsible"))
				self.assertTrue(section["label"].startswith("Warning: "))
				self.assertTrue(0 < len(section.get("description", "")) < ONE_LINE)

	def test_the_script_fills_the_text_field_of_each_warning_and_no_other(self):
		script = (FORM_FOLDER / "church_ai_settings.js").read_text()
		filled = set(re.findall(r"\b(warning_\w+):", script))
		sections = {section["fieldname"].removesuffix("_section") for section in self.sections}

		self.assertEqual(filled, sections)
		for name in sections:
			next_field = self.names[self.names.index(f"{name}_section") + 1]
			self.assertEqual(next_field, f"{name}_html")

	def test_the_script_keeps_the_sentences_that_the_docs_promise(self):
		script = (FORM_FOLDER / "church_ai_settings.js").read_text()
		for sentence in PROMISED:
			self.assertIn(sentence, script)

	def test_without_flow_no_shown_text_names_flow(self):
		"""The summary names no Flow, and a section that shows without Flow keeps each Flow sentence in
		only_with_flow."""
		script = (FORM_FOLDER / "church_ai_settings.js").read_text()
		intro = script[script.index("function intro_html") : script.index("function get_warnings")]
		self.assertNotIn("Flow", intro)

		warnings = script[script.index("function get_warnings") : script.index("function paragraphs")]
		parts = re.split(r"\b(warning_\w+):", warnings)
		for name, code in zip(parts[1::2], parts[2::2], strict=True):
			section = self.fields[self.names.index(f"{name}_section")]
			if section["fieldname"] in FLOW_SECTIONS:
				continue
			shown = re.sub(r"only_with_flow\(\[.*?\]\)", "", code, flags=re.DOTALL)
			for text in (shown, section["label"], section["description"]):
				self.assertNotIn("Flow", text, name)

	def test_the_flow_sections_hide_unless_the_boot_says_flow_is_present(self):
		bootinfo = frappe._dict()
		extend_bootinfo(bootinfo)
		self.assertIn("flow", bootinfo.churchit["ai"])

		for name in FLOW_SECTIONS:
			section = self.fields[self.names.index(name)]
			self.assertIn("frappe.boot.churchit.ai.flow", section.get("depends_on", ""))
