import frappe
from frappe import _
from frappe.query_builder.functions import Count

from churchit.church_scope import is_multi_church
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Church"), "options": "Church", "width": 250},
		{"fieldname": "people", "fieldtype": "Int", "label": _("People"), "width": 100},
		{"fieldname": "families", "fieldtype": "Int", "label": _("Families"), "width": 100},
	]


def get_data():
	"""One row per church the user may see, with that church's own counts."""
	churches = frappe.get_list("Church", order_by="lft asc", pluck="name")
	if not is_multi_church():
		people, families = frappe.db.count("Person"), frappe.db.count("Family")
		return [{"name": name, "people": people, "families": families} for name in churches]
	people = count_by_church("Person")
	families = count_by_church("Family")
	return [
		{"name": name, "people": people.get(name, 0), "families": families.get(name, 0)} for name in churches
	]


def count_by_church(doctype):
	table = frappe.qb.DocType(doctype)
	rows = frappe.qb.from_(table).select(table.church, Count("*").as_("total")).groupby(table.church).run()
	return {church: total for church, total in rows}
