# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Guards for agent calls: what an AI app connected over MCP, or a Flow tool call, may not do.

Frappe gives an app no hook to keep a doctype, a field or a method away from MCP, so these guards
read Frappe's own request marker (frappe.local.mcp_request) and refuse. They only ever refuse.
"""

import frappe
from frappe import _


def is_agent_call() -> bool:
	"""True inside a request to Frappe's MCP server."""
	return getattr(frappe.local, "mcp_request", None) is not None


def refuse_in_agent_call(message: str | None = None) -> None:
	"""Raise PermissionError inside an agent call. Methods that send, merge or erase call this first."""
	if is_agent_call():
		raise frappe.PermissionError(message or _("An AI app cannot do this. Do it yourself in the desk."))


def refuse_agent_write(doc, method=None) -> None:
	"""Stub, A1.6: doc_events "*" validate, before_cancel and on_trash."""


def has_never_to_ai_permission(doc, ptype=None, user=None) -> bool:
	"""Stub, A1.5: has_permission for the T0 doctypes."""
	return True


def never_to_ai_query_conditions(user=None, doctype=None) -> str:
	"""Stub, A1.5: permission_query_conditions for the T0 doctypes."""
	return ""


@frappe.whitelist(methods=["POST"])
def make_email(**kwargs):
	"""Send an email from Frappe's email dialog, unless an AI app asks. Sends messages.

	Replaces frappe.core.doctype.communication.email.make (override_whitelisted_methods), which MCP's
	call_method also applies, so the desk dialog keeps working and an AI app is refused.
	"""
	from frappe.core.doctype.communication import email

	refuse_in_agent_call(_("An AI app cannot send email. Send it yourself from the desk."))
	return frappe.call(email.make, **kwargs)
