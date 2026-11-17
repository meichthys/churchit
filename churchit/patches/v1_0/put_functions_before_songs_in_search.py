# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Make Function a filter button of the search dialog instead of Song, unless someone moved the rows.

The first 5 rows of Global Search Settings are the dialog's filter buttons, and staff look up functions
every week. Churchit shipped Song 5th and Function 6th.
"""

import frappe

PREVIOUS_ORDER = ["Person", "Family", "Group", "Sermon", "Song", "Function"]


def execute():
	rows = frappe.get_all(
		"Global Search DocType",
		filters={"parent": "Global Search Settings"},
		fields=["name", "document_type", "idx"],
		order_by="idx",
	)
	if [row.document_type for row in rows[:6]] != PREVIOUS_ORDER:
		return

	song, function = rows[4], rows[5]
	frappe.db.set_value("Global Search DocType", song.name, "idx", function.idx, update_modified=False)
	frappe.db.set_value("Global Search DocType", function.name, "idx", song.idx, update_modified=False)
	frappe.cache.hdel("global_search", "search_priorities")
