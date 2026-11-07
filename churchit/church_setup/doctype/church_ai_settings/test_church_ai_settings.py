# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who may turn AI on, the acknowledgment, and MCP closing when AI turns off."""

import frappe
from frappe.core.doctype.system_settings.system_settings import clear_system_settings_cache

from churchit.ai.switch import SETTINGS, is_ai_on
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

BRANCH_MANAGER = "_test_ai_branch_manager@example.com"
CHURCH_MANAGER = "_test_ai_church_manager@example.com"


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
		_root, branch, _other = make_two_churches()
		ensure_user(BRANCH_MANAGER, "AI Branch Manager", roles=("Church Manager",))
		frappe.get_doc(
			{"doctype": "User Permission", "user": BRANCH_MANAGER, "allow": "Church", "for_value": branch}
		).insert(ignore_permissions=True)

		frappe.set_user(BRANCH_MANAGER)
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
