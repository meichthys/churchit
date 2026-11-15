# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Close Frappe's MCP server, which a Frappe 16 update turned on, until the church turns AI on.

Church AI Settings starts off. Each System Manager gets one notice, and only when MCP was open.
"""

from churchit.ai.switch import close_mcp_and_tell_system_managers


def execute():
	close_mcp_and_tell_system_managers()
