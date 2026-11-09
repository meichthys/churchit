import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "missionary",
			"fieldtype": "Link",
			"label": _("Missionary"),
			"options": "Missionary",
			"width": 200,
		},
		{
			"fieldname": "monthly_amount",
			"fieldtype": "Currency",
			"label": _("Monthly Amount"),
			"width": 150,
		},
		{
			"fieldname": "total_committed",
			"fieldtype": "Currency",
			"label": _("Total Committed"),
			"width": 150,
		},
		{
			"fieldname": "received_to_date",
			"fieldtype": "Currency",
			"label": _("Received to Date"),
			"width": 150,
		},
		{
			"fieldname": "balance",
			"fieldtype": "Currency",
			"label": _("Balance"),
			"width": 150,
		},
		{
			"fieldname": "last_payment_date",
			"fieldtype": "Date",
			"label": _("Last Payment Date"),
			"width": 120,
		},
		{
			"fieldname": "next_due_date",
			"fieldtype": "Date",
			"label": _("Next Due Date"),
			"width": 120,
		},
	]


def get_data(filters=None):
	MissionarySupportSchedule = frappe.qb.DocType("Missionary Support Schedule")
	Missionary = frappe.qb.DocType("Missionary")

	query = (
		frappe.qb.from_(MissionarySupportSchedule)
		.join(Missionary)
		.on(Missionary.name == MissionarySupportSchedule.missionary)
		.select(
			MissionarySupportSchedule.missionary,
			MissionarySupportSchedule.monthly_amount,
			MissionarySupportSchedule.total_committed,
			MissionarySupportSchedule.start_date,
			MissionarySupportSchedule.end_date,
			MissionarySupportSchedule.status,
		)
		.where(MissionarySupportSchedule.docstatus == 1)
	)

	# Apply church scoping
	query = scoped(query, MissionarySupportSchedule, filters)

	# If church filter is provided, also filter missionaries by church
	if filters and filters.get("church"):
		query = query.where(Missionary.church.isin(filters["church"]))

	rows = query.run(as_dict=True)

	# Enrich each row with computed fields
	result = []
	for row in rows:
		# Get missionary details
		miss = frappe.get_doc("Missionary", row.missionary)

		# Get total received from donations to this missionary's fund
		fund_name = f"Missionary: {miss.title}"
		received = 0
		last_payment = None
		next_due = None

		if frappe.db.exists("Fund", fund_name):
			# Get donations to this fund
			from churchit.church_finances.doctype.donation.donation import Donation
			from churchit.church_finances.doctype.collection.collection import Collection as CollectionDoc
			from churchit.church_scope import church_filters as cf

			Collection = frappe.qb.DocType("Collection")

			donation_query = (
				frappe.qb.from_(Donation)
				.join(Collection)
				.on(Collection.name == Donation.parent)
				.select(Donation.amount)
				.where(
					(Donation.parenttype == "Collection")
					& (Collection.church == miss.church)
					& (Donation.fund == fund_name)
				)
			)

			# Apply church scoping
			donation_query = cf(donation_query, Donation, filters)

			donations = donation_query.run(as_dict=True)
			received = sum(frappe.utils.flt(d.amount) for d in donations)

			# Get last payment date
			last_donation = (
				frappe.qb.from_(Donation)
				.join(Collection)
				.on(Collection.name == Donation.parent)
				.select(Collection.creation)
				.where(
					(Donation.parenttype == "Collection")
					& (Collection.church == miss.church)
					& (Donation.fund == fund_name)
				)
				.orderby(Collection.creation, order=Order.desc)
				.limit(1)
			)
			last_donation_query = cf(last_donation, Donation, filters)
			last_donation_rows = last_donation_query.run(as_dict=True)
			if last_donation_rows:
				last_payment = last_donation_rows[0].creation

		# Calculate total committed from schedule
		total_committed = frappe.utils.flt(row.total_committed) if row.total_committed else 0

		# Calculate balance
		balance = total_committed - received

		# Get next due date
		if row.monthly_amount and row.start_date:
			from frappe.utils import add_months, getdate, today

			start = getdate(row.start_date)
			today_date = getdate(today())

			if today_date < start:
				next_due = start
			else:
				months_passed = (today_date.year - start.year) * 12 + (today_date.month - start.month)
				next_due = add_months(start, months_passed + 1)

				if row.end_date and getdate(next_due) > getdate(row.end_date):
					next_due = None

		result.append(
			{
				"missionary": row.missionary,
				"missionary_name": miss.title,
				"monthly_amount": frappe.utils.flt(row.monthly_amount),
				"total_committed": total_committed,
				"received_to_date": received,
				"balance": balance,
				"last_payment_date": last_payment,
				"next_due_date": next_due,
				"status": row.status,
			}
		)

	return result