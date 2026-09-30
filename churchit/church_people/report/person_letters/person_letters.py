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
		{"fieldname": "parent", "fieldtype": "Link", "label": _("From"), "options": "Person", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 100},
		{
			"fieldname": "share_with_church",
			"fieldtype": "Check",
			"label": _("Share w/ Church?"),
			"width": 120,
		},
		{"fieldname": "shared_date", "fieldtype": "Date", "label": _("Shared Date"), "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": _("Is Private?"), "width": 100},
		{"fieldname": "file", "fieldtype": "Link", "label": _("File"), "options": "File", "width": 150},
		{"fieldname": "content", "fieldtype": "Data", "label": _("Content"), "width": 300},
	]


def get_data(filters=None):
	Letter = frappe.qb.DocType("Letter")
	Person = frappe.qb.DocType("Person")

	query = (
		frappe.qb.from_(Letter)
		.join(Person)
		.on(Person.name == Letter.parent)
		.select(
			Letter.parent,
			Letter.date,
			Letter.share_with_church,
			Letter.shared_date,
			Letter.is_private,
			Letter.file,
			Letter.content,
		)
		.where(Letter.parenttype == "Person")
		.orderby(Letter.parent)
	)
	return scoped(query, Person, filters).run(as_dict=True)
