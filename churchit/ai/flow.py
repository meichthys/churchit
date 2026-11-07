# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's agents and tools for Flow, Frappe's AI agents.

Only Flow's hooks and code that has checked switch.has_flow() load this module, so a Frappe without
Flow never imports it, nor frappe.flow through it.
"""

import frappe


def agents() -> list:
	"""The churchit agents Flow keeps as Flow Agents (flow_agents hook). None yet."""
	return []


def is_ready() -> bool:
	"""True when Flow can run churchit's agents: a chat model is enabled and every agent is synced.

	Call it only after switch.has_flow(), since it reads Flow's doctypes. An embedding model only
	searches Knowledge, so it runs no agent.
	"""
	if not frappe.db.exists("Flow Model", {"enabled": 1, "embedding": 0}):
		return False
	return all(frappe.db.exists("Flow Agent", agent.name) for agent in agents())
