# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give members-only pages made with Frappe's old defaults the title and width of the other pages."""

import frappe


def execute():
	frappe.db.set_value(
		"Web Page",
		{"members_only": 1, "content_type": ("!=", "Page Builder"), "full_width": 1, "show_title": 0},
		{"full_width": 0, "show_title": 1},
	)
