import frappe
from frappe import _

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
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Payment"),
			"options": "Missionary Payment",
			"width": 120,
		},
		{
			"fieldname": "payment_date",
			"fieldtype": "Date",
			"label": _("Payment Date"),
			"width": 110,
		},
		{
			"fieldname": "missionary",
			"fieldtype": "Link",
			"label": _("Missionary"),
			"options": "Missionary",
			"width": 180,
		},
		{
			"fieldname": "amount",
			"fieldtype": "Currency",
			"label": _("Amount"),
			"width": 120,
		},
		{
			"fieldname": "batch",
			"fieldtype": "Link",
			"label": _("Batch"),
			"options": "Missionary Payment Batch",
			"width": 120,
		},
		{
			"fieldname": "reference",
			"fieldtype": "Data",
			"label": _("Reference"),
			"width": 120,
		},
	]


def get_data(filters=None):
	MissionaryPayment = frappe.qb.DocType("Missionary Payment")
	query = (
		frappe.qb.from_(MissionaryPayment)
		.select(
			MissionaryPayment.name,
			MissionaryPayment.payment_date,
			MissionaryPayment.missionary,
			MissionaryPayment.amount,
			MissionaryPayment.batch,
			MissionaryPayment.reference,
		)
		.where(MissionaryPayment.status == "Sent")
	)

	query = scoped(query, MissionaryPayment, filters)

	if filters:
		if filters.get("missionary"):
			query = query.where(MissionaryPayment.missionary == filters["missionary"])

	return query.run(as_dict=True)
