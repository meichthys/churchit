# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Test helpers for churchit's AI code."""

from contextlib import contextmanager

import frappe


@contextmanager
def as_agent():
	"""Run the block as if Frappe's MCP server were handling the request (an agent call)."""
	from frappe.mcp.transport import RequestContext

	previous = getattr(frappe.local, "mcp_request", None)
	frappe.local.mcp_request = RequestContext(method="tools/call")
	try:
		yield
	finally:
		frappe.local.mcp_request = previous
