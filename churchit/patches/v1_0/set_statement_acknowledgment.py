# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Seed the contribution-statement acknowledgment on sites that predate the field.

A DocType default only fills a new record, and Giving Settings is a Single that
already exists everywhere, so upgrading sites would print statements with the
acknowledgment missing. US churches need that sentence for gifts of $250 or more
(IRS Publication 1771), so an empty value is a compliance problem rather than a
cosmetic one. Only fills a blank value — a church that has worded its own keeps it.
"""

import frappe

DEFAULT_TEXT = "No goods or services were provided in exchange for these contributions."


def execute():
	if not frappe.db.exists("DocType", "Giving Settings"):
		return

	if frappe.db.get_single_value("Giving Settings", "statement_acknowledgment"):
		return

	frappe.db.set_single_value("Giving Settings", "statement_acknowledgment", DEFAULT_TEXT)
