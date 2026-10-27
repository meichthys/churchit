import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "user", "fieldtype": "Link", "label": _("User"), "options": "User", "width": 200},
		{"fieldname": "bible_reference", "fieldtype": "Data", "label": _("Reference"), "width": 200},
		{
			"fieldname": "translation",
			"fieldtype": "Link",
			"label": _("Translation"),
			"options": "Bible Translation",
			"width": 160,
		},
		{"fieldname": "group", "fieldtype": "Link", "label": _("Group"), "options": "Group", "width": 160},
		{"fieldname": "progress", "fieldtype": "Percent", "label": _("Progress"), "width": 100},
		{"fieldname": "memorized", "fieldtype": "Check", "label": _("Memorized"), "width": 100},
		{"fieldname": "memorized_on", "fieldtype": "Date", "label": _("Memorized On"), "width": 120},
		{
			"fieldname": "times_memorized",
			"fieldtype": "Int",
			"label": _("Perfect Runs"),
			"width": 110,
		},
	]


def get_data(filters):
	"""Items of users whose Person is in a church the reader may see, and of users with no Person when unscoped."""
	Item = frappe.qb.DocType("Bible Memory Item")
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Item)
		.left_join(Person)
		.on(Person.user == Item.user)
		.select(
			Item.name,
			Item.user,
			Item.bible_reference,
			Item.translation,
			Item.group,
			Item.progress,
			Item.memorized,
			Item.memorized_on,
			Item.times_memorized,
		)
		.orderby(Item.memorized, order=Order.desc)
		.orderby(Item.memorized_on, order=Order.desc)
		.orderby(Item.modified, order=Order.desc)
	)

	memorized = filters.get("memorized")
	if memorized in (1, "1", True, "Yes"):
		query = query.where(Item.memorized == 1)
	elif memorized in (0, "0", False, "No"):
		query = query.where(Item.memorized == 0)
	if filters.get("user"):
		query = query.where(Item.user == filters["user"])
	if filters.get("group"):
		frappe.has_permission("Group", doc=filters["group"], throw=True)
		query = query.where(Item.group == filters["group"])

	return scoped(query, Person, filters).run(as_dict=True)
