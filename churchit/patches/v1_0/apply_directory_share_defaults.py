# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give the people added from now on the member directory sharing that People Settings shows.

The settings set the Person defaults when they are saved, and migrate brings in their new fields without a save.
"""

import frappe


def execute():
	frappe.get_single("People Settings").set_share_defaults()
