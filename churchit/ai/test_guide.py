# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Churchit guide for AI apps, and the Agent Instructions sentence that points to it."""

import ast
from pathlib import Path

import frappe
from frappe.api import discovery
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache
from frappe.mcp.tools.discover import search_methods

from churchit.ai.exposure import get_exposure
from churchit.ai.guide import (
	GUIDE_METHOD,
	POINTER,
	add_guide_pointer,
	get_agent_guide,
	get_guide_topics,
	get_skill_folder,
	has_guide_pointer,
)
from churchit.ai.switch import SETTINGS
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

APP = Path(frappe.get_app_path("churchit"))
SYSTEM_MANAGER = "_test_guide_system_manager@example.com"
CHURCH_MANAGER = "_test_guide_church_manager@example.com"
WEBSITE_USER = "_test_guide_website_user@example.com"


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value(SETTINGS, "enabled", enabled)


def set_instructions(text: str | None) -> None:
	frappe.db.set_single_value("System Settings", "agent_instructions", text)
	clear_system_settings_cache()


def get_instructions() -> str | None:
	return frappe.db.get_single_value("System Settings", "agent_instructions")


class GuideTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch, _other = make_two_churches()
		ensure_user(SYSTEM_MANAGER, "Guide System Manager", ("System Manager",))
		ensure_user(CHURCH_MANAGER, "Guide Church Manager", ("Church Manager",))
		set_user_church(CHURCH_MANAGER, branch)
		ensure_user(WEBSITE_USER, "Guide Website User", ())
		# A test site that skipped the setup wizard cannot save System Settings without these.
		for fieldname, value in (("language", "en"), ("time_zone", "UTC")):
			if not frappe.db.get_single_value("System Settings", fieldname):
				frappe.db.set_single_value("System Settings", fieldname, value)

	def setUp(self):
		super().setUp()
		set_ai(1)
		set_instructions("Our church keeps its records here.")
		self.addCleanup(clear_system_settings_cache)

	def as_user(self, user: str) -> None:
		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")


class TestAgentGuide(GuideTestCase):
	def test_the_guide_is_the_churchit_skill(self):
		self.as_user(CHURCH_MANAGER)
		self.assertEqual(get_agent_guide(), (get_skill_folder() / "SKILL.md").read_text())

	def test_a_topic_returns_its_reference_file(self):
		self.as_user(CHURCH_MANAGER)
		people = (get_skill_folder() / "reference" / "people.md").read_text()
		self.assertIn("people", get_guide_topics())
		self.assertEqual(get_agent_guide("people"), people)
		self.assertEqual(get_agent_guide("reference/people.md"), people)

	def test_a_topic_that_is_not_a_reference_file_is_refused(self):
		self.as_user(CHURCH_MANAGER)
		for topic in ("../../hooks", "../SKILL", "README", "/etc/passwd"):
			with self.assertRaisesRegex(frappe.ValidationError, "There is no guide on that topic"):
				get_agent_guide(topic)

	def test_church_rules_finds_the_guide_first(self):
		"""Frappe's MCP search_methods matches every word and sorts by path."""
		discovery.build_cache()
		self.as_user(CHURCH_MANAGER)
		self.assertEqual(search_methods("church rules")[0]["path"], GUIDE_METHOD)


class TestGuidePointer(GuideTestCase):
	def test_a_system_manager_adds_the_sentence_once(self):
		self.as_user(SYSTEM_MANAGER)
		self.assertFalse(has_guide_pointer())

		self.assertTrue(add_guide_pointer())
		expected = f"Our church keeps its records here.\n\n{POINTER}"
		self.assertEqual(get_instructions(), expected)
		self.assertTrue(has_guide_pointer())

		self.assertFalse(add_guide_pointer())
		self.assertEqual(get_instructions(), expected)

	def test_empty_instructions_get_only_the_sentence(self):
		set_instructions(None)
		self.as_user(SYSTEM_MANAGER)
		add_guide_pointer()
		self.assertEqual(get_instructions(), POINTER)

	def test_instructions_that_name_the_guide_in_other_words_stay_as_they_are(self):
		own = f"Read {GUIDE_METHOD} before anything else."
		set_instructions(own)
		self.as_user(SYSTEM_MANAGER)
		self.assertFalse(add_guide_pointer())
		self.assertEqual(get_instructions(), own)

	def test_only_a_system_manager_adds_the_sentence(self):
		self.as_user(CHURCH_MANAGER)
		self.assertRaises(frappe.PermissionError, add_guide_pointer)
		self.assertEqual(get_instructions(), "Our church keeps its records here.")


class TestGuidePointerLine(GuideTestCase):
	def line(self, user: str) -> dict:
		self.as_user(user)
		return next(line for line in get_exposure() if line["surface"] == "Agent Instructions")

	def test_a_system_manager_gets_the_button_while_the_sentence_is_missing(self):
		line = self.line(SYSTEM_MANAGER)
		self.assertEqual((line["state"], line["open"]), ("No Churchit guide", True))
		self.assertEqual(line["action"], "add_guide_pointer")

	def test_the_line_says_when_the_sentence_is_there(self):
		set_instructions(POINTER)
		line = self.line(SYSTEM_MANAGER)
		self.assertEqual((line["state"], line["open"]), ("Names the Churchit guide", False))
		self.assertNotIn("action", line)

	def test_no_button_for_a_church_manager_or_while_ai_is_off(self):
		self.assertNotIn("action", self.line(CHURCH_MANAGER))
		frappe.set_user("Administrator")
		set_ai(0)
		self.assertNotIn("action", self.line(SYSTEM_MANAGER))


def names_the_field(tree: ast.AST) -> bool:
	return any(
		(isinstance(node, ast.Constant) and node.value == "agent_instructions")
		or (isinstance(node, ast.Attribute) and node.attr == "agent_instructions")
		for node in ast.walk(tree)
	)


class TestNoUpdateWritesAgentInstructions(GuideTestCase):
	"""System Settings Agent Instructions belong to the site admin: only the button writes them."""

	def test_only_add_guide_pointer_writes_the_field(self):
		modules = [
			path.relative_to(APP).as_posix()
			for path in APP.rglob("*.py")
			if not path.name.startswith("test_") and names_the_field(ast.parse(path.read_text()))
		]
		self.assertEqual(modules, ["ai/guide.py"])

		tree = ast.parse((APP / "ai" / "guide.py").read_text())
		writers = [
			function.name
			for function in tree.body
			if isinstance(function, ast.FunctionDef)
			and any(
				isinstance(target, ast.Attribute) and target.attr == "agent_instructions"
				for node in ast.walk(function)
				if isinstance(node, ast.Assign)
				for target in node.targets
			)
		]
		self.assertEqual(writers, ["add_guide_pointer"])

	def test_no_hook_or_patch_names_the_button(self):
		files = [APP / "hooks.py", APP / "patches.txt", *(APP / "patches").rglob("*.py")]
		for path in files:
			text = path.read_text()
			for name in ("agent_instructions", "add_guide_pointer", "churchit.ai.guide"):
				self.assertNotIn(name, text, f"{path.relative_to(APP)} names {name}")


class TestGuideRefusals(GuideTestCase):
	def test_every_method_refuses_while_ai_is_off(self):
		set_ai(0)
		self.as_user(SYSTEM_MANAGER)
		for method in (get_agent_guide, add_guide_pointer):
			self.assertRaisesRegex(frappe.PermissionError, "AI is turned off", method)
		self.assertEqual(get_instructions(), "Our church keeps its records here.")

	def test_every_method_refuses_a_website_user_and_a_guest(self):
		for user in (WEBSITE_USER, "Guest"):
			self.as_user(user)
			for method in (get_agent_guide, add_guide_pointer):
				self.assertRaises(frappe.PermissionError, method)
