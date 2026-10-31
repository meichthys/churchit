# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Point a site's saved People layout at the relabelled Visitation Follow-ups Needed card.

A desk edit to a standard workspace is kept as a Custom Workspace snapshot, and a block finds its
number card by the row label, so the old label would draw an empty tile.
"""

import json

import frappe

OLD_LABEL = "Visitation Followups Needed"
NEW_LABEL = "Visitation Follow-ups Needed"


def execute():
	content = frappe.db.get_value("Custom Workspace", "People", "content")
	if not content or OLD_LABEL not in content:
		return

	blocks = json.loads(content)
	for block in blocks:
		if block["type"] == "number_card" and block["data"].get("number_card_name") == OLD_LABEL:
			block["data"]["number_card_name"] = NEW_LABEL

	frappe.db.set_value("Custom Workspace", "People", "content", json.dumps(blocks))
