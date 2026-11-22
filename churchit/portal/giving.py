# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's giving pages: the member's pledges and their giving statements."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, formatdate

from churchit.church_finances.doctype.fund.fund import format_amount
from churchit.church_finances.doctype.pledge.pledge import get_open_campaigns, get_pledges_by_campaign
from churchit.church_finances.report.pledge_progress.pledge_progress import get_received_for_pledge
from churchit.portal.access import require_page, require_person
from churchit.www.statements import get_own_statements


@frappe.whitelist(methods=["GET"])
def get_pledges() -> dict:
	"""The member's own pledges with what they gave toward each, and the campaigns open for a pledge. Reads only."""
	person = require_person()
	require_page("pledge")

	rows = frappe.get_list(
		"Pledge",
		filters={"person": person},
		fields=["name", "campaign", "amount", "frequency", "modified"],
		order_by="creation desc",
	)
	# church-scope: the campaigns of the member's own pledges, by name
	titles = dict(
		frappe.get_all(
			"Pledge Campaign",
			filters={"name": ("in", [row.campaign for row in rows] or [""])},
			fields=["name", "title"],
			as_list=True,
		)
	)
	open_campaigns = get_open_campaigns()
	return {
		"items": [get_pledge_row(row, titles, open_campaigns) for row in rows],
		"campaigns": [{"name": name, "title": title} for name, title in open_campaigns.items()],
		"existing": {campaign: row["name"] for campaign, row in get_pledges_by_campaign().items()},
		"frequencies": frappe.get_meta("Pledge").get_field("frequency").options.split("\n"),
	}


def get_pledge_row(row: frappe._dict, titles: dict[str, str], open_campaigns: dict[str, str]) -> dict:
	"""One pledge with its campaign title, the receipt amounts and whether the member may change it (the campaign must still be open)."""
	given = flt(get_received_for_pledge(row))
	return {
		"name": row.name,
		"campaign": row.campaign,
		"campaign_title": titles.get(row.campaign) or row.campaign,
		"amount": flt(row.amount),
		"frequency": row.frequency,
		"pledged_display": format_amount(row.amount),
		"given_display": format_amount(given),
		"remaining_display": format_amount(max(flt(row.amount) - given, 0)),
		"percent": min(round(given / flt(row.amount) * 100), 100) if flt(row.amount) else 0,
		"can_edit": row.campaign in open_campaigns
		and bool(frappe.has_permission("Pledge", "write", doc=row.name)),
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=True)
def save_pledge(campaign: str, amount: float, frequency: str, name: str | None = None) -> str:
	"""Make the member's own pledge, or change one of their pledges that they may edit. Changes data.

	Pledge.validate takes the person from the session and refuses a campaign that is not open to them.
	"""
	require_person()
	require_page("pledge")

	if name:
		pledge = frappe.get_doc("Pledge", name)
		pledge.check_permission("write")
	else:
		pledge = frappe.new_doc("Pledge")

	pledge.update({"campaign": campaign, "amount": flt(amount), "frequency": frequency})
	# Staff with a Person use the app too, so the member rules cannot key on a Website User alone.
	pledge.flags.from_member_app = True
	pledge.save()
	return pledge.name


@frappe.whitelist(methods=["GET"])
def get_statements() -> dict:
	"""The giving statements addressed to the member or their household, newest first. Reads only."""
	person = require_person()
	require_page("statements")

	own = frappe.db.get_value("Person", person, ["name", "family"], as_dict=True)
	return {
		"items": [
			{
				"name": row.name,
				"title": row.title,
				"from_date": str(row.from_date),
				"to_date": str(row.to_date),
				"period_display": _("{0} to {1}").format(formatdate(row.from_date), formatdate(row.to_date)),
				"total_display": format_amount(row.total_amount),
			}
			for row in get_own_statements(own)
		]
	}
