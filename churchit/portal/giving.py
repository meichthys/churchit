# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's giving pages: the member's pledges and their giving statements."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, formatdate, getdate, today

from churchit.church_finances.doctype.fund.fund import format_amount, get_give_path
from churchit.church_finances.doctype.pledge.pledge import get_open_campaigns
from churchit.church_finances.report.pledge_progress.pledge_progress import get_received_for_pledge
from churchit.portal.access import require_page, require_person


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
	campaigns = {
		campaign.name: campaign
		for campaign in frappe.get_all(
			"Pledge Campaign",
			filters={"name": ("in", [row.campaign for row in rows] or [""])},
			fields=["name", "title", "fund", "church", "start_date", "end_date"],
		)
	}
	# church-scope: whether the funds of those campaigns take gifts, by name
	giving_funds = set(
		frappe.get_all(
			"Fund",
			filters={
				"name": ("in", [campaign.fund for campaign in campaigns.values()] or [""]),
				"allow_giving": 1,
			},
			pluck="name",
		)
	)
	open_campaigns = get_open_campaigns()
	return {
		"items": [get_pledge_row(row, campaigns, giving_funds, open_campaigns) for row in rows],
		"campaigns": [{"name": name, "title": title} for name, title in open_campaigns.items()],
		# reversed: rows run newest first, and the newest pledge to a campaign wins.
		"existing": {row.campaign: row.name for row in reversed(rows)},
		"frequencies": frappe.get_meta("Pledge").get_field("frequency").options.split("\n"),
	}


def get_pledge_row(
	row: frappe._dict,
	campaigns: dict[str, frappe._dict],
	giving_funds: set[str],
	open_campaigns: dict[str, str],
) -> dict:
	"""One pledge with its campaign title, the receipt amounts, whether the member may change it (the campaign must still be open) and where to give toward it."""
	given = flt(get_received_for_pledge(row))
	campaign = campaigns.get(row.campaign)
	percent = min(round(given / flt(row.amount) * 100), 100) if flt(row.amount) else 0
	return {
		"name": row.name,
		"campaign": row.campaign,
		"campaign_title": (campaign and campaign.title) or row.campaign,
		"amount": flt(row.amount),
		"frequency": row.frequency,
		"pledged_display": format_amount(row.amount),
		"given_display": format_amount(given),
		"remaining_display": format_amount(max(flt(row.amount) - given, 0)),
		"percent": percent,
		"can_edit": row.campaign in open_campaigns
		and bool(frappe.has_permission("Pledge", "write", doc=row.name)),
		"give_path": get_give_path(campaign.fund, campaign.church)
		if is_giving_open(campaign, giving_funds) and percent < 100
		else None,
	}


def is_giving_open(campaign: frappe._dict | None, giving_funds: set[str]) -> bool:
	"""Whether gifts to the campaign's fund count toward it now: the fund takes gifts and today is within the dates."""
	return bool(
		campaign
		and campaign.fund in giving_funds
		and getdate(campaign.start_date) <= getdate(today()) <= getdate(campaign.end_date)
	)


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


def get_own_statements(person):
	"""Statements addressed to *person*, plus their household's."""
	or_filters = {"person": person.name}
	if person.family:
		or_filters["family"] = person.family

	# church-scope: the signed-in member's own statements, by their person and family
	return frappe.get_all(
		"Giving Statement",
		or_filters=or_filters,
		fields=["name", "title", "from_date", "to_date", "total_amount"],
		order_by="to_date desc",
	)
