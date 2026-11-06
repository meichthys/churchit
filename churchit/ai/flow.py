# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's agents and tools for Flow, Frappe's AI agents.

Only Flow's hooks load this module, so a Frappe without Flow never imports frappe.flow.
"""


def agents() -> list:
	"""The churchit agents Flow keeps as Flow Agents (flow_agents hook). None yet."""
	return []
