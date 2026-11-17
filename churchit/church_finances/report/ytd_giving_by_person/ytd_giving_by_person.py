import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce, Concat_ws, Count, Max, Sum
from frappe.utils import cint
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	if data:
		data.append(get_total_row(data))
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 240},
		{"fieldname": "gift_count", "fieldtype": "Int", "label": _("# Gifts"), "width": 80},
		{"fieldname": "ytd_amount", "fieldtype": "Currency", "label": _("YTD Amount"), "width": 140},
		{"fieldname": "avg_gift", "fieldtype": "Currency", "label": _("Avg Gift"), "width": 120},
		{"fieldname": "last_gift_date", "fieldtype": "Date", "label": _("Last Gift"), "width": 120},
		{"fieldname": "prior_year_amount", "fieldtype": "Currency", "label": _("Prior Year"), "width": 140},
	]


def get_total_row(rows):
	"""Sum the amounts. The average gift is the total over all gifts, not a sum of averages. Prior Year stays
	empty when no one gave last year, as each person's cell does."""
	gift_count = sum(row["gift_count"] for row in rows)
	ytd_amount = sum(row["ytd_amount"] or 0 for row in rows)
	prior_year_amounts = [row["prior_year_amount"] for row in rows if row["prior_year_amount"] is not None]
	return {
		"person": _("Total"),
		"gift_count": gift_count,
		"ytd_amount": ytd_amount,
		"avg_gift": ytd_amount / gift_count if gift_count else 0,
		"last_gift_date": max((row["last_gift_date"] for row in rows if row["last_gift_date"]), default=None),
		"prior_year_amount": sum(prior_year_amounts) if prior_year_amounts else None,
		"is_total_row": 1,
	}


def get_data(filters=None):
	"""One row per giver. A gift is one check (by its number) or one payment type in a collection, so a check split
	across funds counts once."""
	year = cint((filters or {}).get("year")) or frappe.utils.now_datetime().year

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	gift = Concat_ws(":", Donation.parent, Donation.payment_type, Coalesce(Donation.check_number, ""))

	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Donation.person,
			Count(gift).distinct().as_("gift_count"),
			Sum(Donation.amount).as_("ytd_amount"),
			Max(Collection.date).as_("last_gift_date"),
		)
		.where(
			Donation.person.isnotnull()
			& (Donation.is_non_cash == 0)
			& in_year(Collection, year)
			& (Collection.docstatus == 1)
		)
		.groupby(Donation.person)
		.orderby(Sum(Donation.amount), order=Order.desc)
	)
	rows = scoped(query, Collection, filters).run(as_dict=True)

	prior_year = get_prior_year_amounts([row.person for row in rows], year - 1, filters)
	for row in rows:
		row.avg_gift = row.ytd_amount / row.gift_count
		row.prior_year_amount = prior_year.get(row.person)
	return rows


def get_prior_year_amounts(people: list[str], year: int, filters) -> dict:
	"""{person: the total of their cash gifts in *year*}, for the people who gave money then."""
	if not people:
		return {}

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person, Sum(Donation.amount).as_("amount"))
		.where(
			Donation.person.isin(people)
			& (Donation.is_non_cash == 0)
			& in_year(Collection, year)
			& (Collection.docstatus == 1)
		)
		.groupby(Donation.person)
	)
	return dict(scoped(query, Collection, filters).run())


def in_year(table, year: int):
	"""Criterion: the *table* row's date is in *year*. A range, unlike YEAR(date), can use an index."""
	return (table.date >= f"{year}-01-01") & (table.date < f"{year + 1}-01-01")
