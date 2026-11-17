# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, flt
from pypika import Order

from churchit.church_people.household import members
from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	if filters.get("campaign"):
		frappe.has_permission("Pledge Campaign", doc=filters["campaign"], throw=True)
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "campaign",
			"fieldtype": "Link",
			"label": _("Campaign"),
			"options": "Pledge Campaign",
			"width": 160,
		},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 180},
		{"fieldname": "family", "fieldtype": "Link", "label": _("Family"), "options": "Family", "width": 130},
		{"fieldname": "frequency", "fieldtype": "Data", "label": _("Frequency"), "width": 100},
		{"fieldname": "goal_amount", "fieldtype": "Currency", "label": _("Goal"), "width": 120},
		{"fieldname": "pledged", "fieldtype": "Currency", "label": _("Pledged"), "width": 120},
		{"fieldname": "received", "fieldtype": "Currency", "label": _("Received"), "width": 120},
		{"fieldname": "progress", "fieldtype": "Percent", "label": _("Progress"), "width": 100},
	]


def get_data(filters):
	"""A row per campaign (goal, pledged and received), then a row per pledge against its givers' gifts.

	A gift counts on one pledge only, see `get_received_by_pledge`.
	"""
	campaigns = get_campaigns(filters)
	pledges = get_pledges([campaign.name for campaign in campaigns], filters)

	data = []
	for campaign in campaigns:
		gifts = get_gifts_by_person(campaign)
		own_pledges = [pledge for pledge in pledges if pledge.campaign == campaign.name]
		pledged = sum(flt(pledge.amount) for pledge in own_pledges)
		received = sum(gifts.values())
		data.append(
			{
				"campaign": campaign.name,
				"goal_amount": campaign.goal_amount,
				"pledged": pledged,
				"received": received,
				"progress": get_progress(received, campaign.goal_amount),
				"church": campaign.church,
				"bold": 1,
			}
		)
		received_by_pledge = get_received_by_pledge(own_pledges, gifts)
		for pledge in own_pledges:
			received = received_by_pledge[id(pledge)]
			data.append(
				{
					**pledge,
					"pledged": pledge.amount,
					"received": received,
					"progress": get_progress(received, pledge.amount),
				}
			)
	return data


def get_received_by_pledge(pledges: list, gifts: dict) -> dict[int, float]:
	"""{id(pledge): received} where each person's gifts count on one pledge of the campaign.

	A person's own pledges take their gifts in the order given: each one fills to its amount, and the last
	takes the rest. A household pledge then takes the gifts of the person and of each living family member
	that no earlier pledge took, so the pledge rows never add up to more than the campaign received.
	"""
	received = {}
	taken = set()
	remaining = dict(gifts)
	own_pledges = [pledge for pledge in pledges if not pledge.family]
	last_own = {pledge.person: pledge for pledge in own_pledges}
	for pledge in own_pledges:
		left = remaining.get(pledge.person, 0)
		is_last = last_own[pledge.person] is pledge
		received[id(pledge)] = left if is_last else min(flt(pledge.amount), left)
		remaining[pledge.person] = left - received[id(pledge)]
		taken.add(pledge.person)

	for pledge in pledges:
		if not pledge.family:
			continue
		givers = ({pledge.person} | set(members(pledge.family))) - taken
		taken |= givers
		received[id(pledge)] = sum(gifts.get(giver, 0) for giver in givers)
	return received


def get_received_for_pledge(pledge) -> float:
	"""What was given toward *pledge*, counted as the report counts it.

	Reads the campaign's other pledges unscoped, because the share of a household depends on them, and
	returns only this pledge's number.
	"""
	campaign = frappe.get_doc("Pledge Campaign", pledge.campaign)
	# church-scope: the campaign's own pledges; only the caller's own total leaves this function
	pledges = frappe.get_all(
		"Pledge",
		filters={"campaign": campaign.name},
		fields=["name", "campaign", "person", "family", "amount"],
		order_by="creation",
	)
	received = get_received_by_pledge(pledges, get_gifts_by_person(campaign))
	return next(received[id(row)] for row in pledges if row.name == pledge.name)


def get_progress(received: float, target: float) -> float | None:
	return flt(received / target * 100, 1) if flt(target) else None


def get_campaigns(filters):
	Campaign = frappe.qb.DocType("Pledge Campaign")
	query = (
		frappe.qb.from_(Campaign)
		.select(
			Campaign.name,
			Campaign.church,
			Campaign.fund,
			Campaign.start_date,
			Campaign.end_date,
			Campaign.goal_amount,
		)
		.orderby(Campaign.start_date, order=Order.desc)
	)
	if filters.get("campaign"):
		query = query.where(Campaign.name == filters["campaign"])
	return scoped(query, Campaign, filters).run(as_dict=True)


def get_pledges(campaigns, filters):
	if not campaigns:
		return []
	Pledge = frappe.qb.DocType("Pledge")
	query = (
		frappe.qb.from_(Pledge)
		.select(Pledge.campaign, Pledge.person, Pledge.family, Pledge.frequency, Pledge.amount, Pledge.church)
		.where(Pledge.campaign.isin(campaigns))
		.orderby(Pledge.creation)
	)
	return scoped(query, Pledge, filters).run(as_dict=True)


def get_gifts_by_person(campaign) -> dict[str | None, float]:
	"""{person: total} of the gifts to *campaign*, with None for the gifts of no known person.

	A gift is a Donation row of a submitted Collection to the campaign's fund, from the start date to the end of
	the end date. The fund balance is not read, so an expense or a transfer never changes the figures.
	"""
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	query = (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person, Sum(Donation.amount).as_("total"))
		.where(
			(Donation.parenttype == "Collection")
			& (Collection.docstatus == 1)
			& (Donation.fund == campaign.fund)
			& (Collection.date >= campaign.start_date)
			& (Collection.date < add_days(campaign.end_date, 1))
		)
		.groupby(Donation.person)
	)
	# The campaign's church keeps its own money: a shared fund also takes other churches' gifts.
	if campaign.church:
		query = query.where(Collection.church == campaign.church)
	return {row.person: flt(row.total) for row in query.run(as_dict=True)}
