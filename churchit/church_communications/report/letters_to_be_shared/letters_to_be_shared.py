import frappe
from frappe.query_builder.functions import Coalesce

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "parenttype", "fieldtype": "Data", "label": "Type", "width": 120},
		{"fieldname": "parent", "fieldtype": "Dynamic Link", "label": "From", "options": "parenttype", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": "Received", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Private?", "width": 80},
		{"fieldname": "file", "fieldtype": "Data", "label": "File", "width": 200},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]


def get_data():
	Letter = frappe.qb.DocType("Letter")

	return (
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
		.run(as_dict=True)
	)
