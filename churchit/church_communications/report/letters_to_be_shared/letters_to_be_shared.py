import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce

from churchit.church_scope import church_filter
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "parenttype", "fieldtype": "Data", "label": _("Type"), "width": 120},
		{
			"fieldname": "parent",
			"fieldtype": "Dynamic Link",
			"label": _("From"),
			"options": "parenttype",
			"width": 150,
		},
		{"fieldname": "date", "fieldtype": "Date", "label": _("Received"), "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": _("Private?"), "width": 80},
		{"fieldname": "file", "fieldtype": "Data", "label": _("File"), "width": 200},
		{"fieldname": "content", "fieldtype": "Data", "label": _("Content"), "width": 300},
	]


def get_data(filters=None):
	Letter = frappe.qb.DocType("Letter")

	query = (
		frappe.qb.from_(Letter)
		.select(
			Letter.parenttype,
			Letter.parent,
			Letter.date,
			Letter.is_private,
			Coalesce(Letter.file, "").as_("file"),
			Letter.content,
			Letter.name,
		)
		.where((Letter.share_with_church == 1) & Letter.shared_date.isnull())
	)
	churches = church_filter(filters)
	if churches is not None:
		query = query.where(
			from_church(Letter, "Person", churches) | from_church(Letter, "Missionary", churches)
		)
	return query.run(as_dict=True)


def from_church(Letter, parenttype, churches):
	"""Letters whose parent record (a Person or Missionary) belongs to one of `churches`."""
	parent = frappe.qb.DocType(parenttype)
	owners = frappe.qb.from_(parent).select(parent.name).where(parent.church.isin(churches))
	return (Letter.parenttype == parenttype) & Letter.parent.isin(owners)
