import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "parent", "fieldtype": "Link", "label": "From", "options": "Missionary", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 100},
		{"fieldname": "share_with_church", "fieldtype": "Check", "label": "Share w/ Church?", "width": 120},
		{"fieldname": "shared_date", "fieldtype": "Date", "label": "Shared Date", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Is Private?", "width": 100},
		{"fieldname": "file", "fieldtype": "Link", "label": "File", "options": "File", "width": 150},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]


def get_data():
	Letter = frappe.qb.DocType("Letter")
	Missionary = frappe.qb.DocType("Missionary")

	return (
		frappe.qb.from_(Letter)
		.join(Missionary)
		.on(Missionary.name == Letter.parent)
		.select(
			Letter.parent,
			Letter.date,
			Letter.share_with_church,
			Letter.shared_date,
			Letter.is_private,
			Letter.file,
			Letter.content,
		)
		.where(Letter.parenttype == "Missionary")
		.orderby(Letter.parent)
		.run(as_dict=True)
	)
