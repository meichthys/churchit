# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_prayers.prayer_access import get_active_request_filters


@frappe.whitelist(methods=["GET", "POST"])
def get(
	chart_name: str | None = None,
	chart: str | dict | None = None,
	no_cache: bool | int | None = None,
	filters: str | list | dict | None = None,
	**kwargs,
) -> dict:
	"""Chart source: the active prayer requests the reader may read, by type, past End Dates left out. Reads only.

	`get_list` applies the reader's rights, church and Visibility, as the Active Prayer Requests card does.
	"""
	active, or_filters = get_active_request_filters()
	rows = frappe.get_list(
		"Prayer Request",
		fields=["type", {"COUNT": "*", "as": "count"}],
		filters=active,
		or_filters=or_filters,
		group_by="type",
		order_by="count desc",
	)
	return {
		"labels": [row.type or _("No Type") for row in rows],
		"datasets": [{"name": _("Active Prayer Requests"), "values": [row.count for row in rows]}],
	}
