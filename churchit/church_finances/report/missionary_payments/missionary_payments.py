import frappe
from frappe import _
from churchit.church_scope import scoped

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Missionary Payment"),
			"options": "Missionary Payment",
			"width": 120,
		},
		{
			"fieldname": "missionary",
			"fieldtype": "Link",
			"label": _("Missionary"),
			"options": "Missionary",
			"width": 180,
		},
		{
			"fieldname": "status",
			"fieldtype": "Select",
			"label": _("Status"),
			"width": 100,
		},
		{
			"fieldname": "amount",
			"fieldtype": "Currency",
			"label": _("Amount"),
			"width": 120,
		},
		{
			"fieldname": "payment_date",
			"fieldtype": "Date",
			"label": _("Payment Date"),
			"width": 110,
		},
		{
			"fieldname": "reference",
			"fieldtype": "Data",
			"label": _("Reference"),
			"width": 120,
		},
		{
			"fieldname": "fund",
			"fieldtype": "Link",
			"label": _("Fund"),
			"options": "Fund",
			"width": 150,
		}
	]

def get_data(filters=None):
	MissionaryPayment = frappe.qb.DocType("Missionary Payment")
	query = (
		frappe.qb.from_(MissionaryPayment)
		.select(
			MissionaryPayment.name,
			MissionaryPayment.missionary,
			MissionaryPayment.status,
			MissionaryPayment.amount,
			MissionaryPayment.payment_date,
			MissionaryPayment.reference,
			MissionaryPayment.fund
		)
	)

	query = scoped(query, MissionaryPayment, filters)

	if filters:
		if filters.get("missionary"):
			query = query.where(MissionaryPayment.missionary == filters["missionary"])
		if filters.get("status"):
			query = query.where(MissionaryPayment.status == filters["status"])

	return query.run(as_dict=True)
