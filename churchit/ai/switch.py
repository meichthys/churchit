# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch. Church AI Settings decides whether churchit uses AI at all.

While it is off, every churchit AI feature refuses and Frappe's MCP server stays closed. The switch
never turns MCP on: System Settings stays the only owner of enable_mcp.
"""

import frappe
from frappe import _

SETTINGS = "Church AI Settings"


def is_ai_on() -> bool:
	"""True while Church AI Settings is enabled.

	Off until migrate has synced the doctype: pre-model-sync patches still save records (their own
	Patch Log among them) on the schema being upgraded.
	"""
	try:
		frappe.get_meta(SETTINGS)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return False
	return bool(frappe.db.get_single_value(SETTINGS, "enabled"))


def require_ai(feature: str | None = None) -> None:
	"""Raise PermissionError while AI is off. Every churchit AI method and job asks this first."""
	if not is_ai_on():
		raise frappe.PermissionError(_("AI is turned off on this site."))


def has_flow() -> bool:
	"""True on a Frappe that ships Flow, Frappe's AI agents."""
	return bool(frappe.db.exists("DocType", "Flow Agent"))


def extend_bootinfo(bootinfo) -> None:
	"""Stub, A1.1: tell the desk whether AI is on (frappe.boot.churchit.ai)."""


def refuse_mcp_while_ai_off(doc, method=None) -> None:
	"""Stub, A1.2: System Settings validate; refuse turning enable_mcp on while AI is off."""


def close_mcp_while_ai_off() -> None:
	"""Stub, A1.2: after_install and after_migrate; keep enable_mcp at 0 while AI is off."""


def create_ai_app_notification() -> None:
	"""Stub, A1.9: insert the "AI app connected" Notification once (after_install and a v1_0 patch)."""
