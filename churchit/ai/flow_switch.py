# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The master AI switch over Flow, Frappe's AI agents.

While AI is off, no Flow chat, run, trigger or knowledge ingest can start. These hooks work on
Flow's documents and never import frappe.flow; a Frappe without Flow never calls them.
"""


def has_agent_permission(doc, ptype=None, user=None) -> bool:
	"""Stub, A2.4: has_permission on Flow Agent."""
	return True


def agent_query_conditions(user=None, doctype=None) -> str:
	"""Stub, A2.4: permission_query_conditions on Flow Agent."""
	return ""


def has_session_permission(doc, ptype=None, user=None) -> bool:
	"""Stub, A2.4: has_permission on Flow Session."""
	return True


def check_new_session(doc, method=None) -> None:
	"""Stub, A2.4: Flow Session before_insert."""


def check_trigger(doc, method=None) -> None:
	"""Stub, A2.8: Flow Trigger validate."""


def check_knowledge_source(doc, method=None) -> None:
	"""Stub, A2.9: Flow Knowledge Source validate."""
