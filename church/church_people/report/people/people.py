import frappe
from frappe.query_builder.functions import GroupConcat
from frappe.utils import nowdate

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "full_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "family_name", "fieldtype": "Data", "label": "Family", "width": 150},
		{"fieldname": "roles", "fieldtype": "Data", "label": "Roles", "width": 250},
		{"fieldname": "membership_status", "fieldtype": "Link", "label": "Member Status", "options": "Member Status", "width": 120},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
		{"fieldname": "is_member", "fieldtype": "Check", "label": "Member", "width": 80},
		{"fieldname": "is_baptized", "fieldtype": "Check", "label": "Baptized", "width": 80},
	]


def get_data(filters=None):
	filters = filters or {}
	today = nowdate()

	Person = frappe.qb.DocType("Person")
	Family = frappe.qb.DocType("Family")
	Position = frappe.qb.DocType("Position")
	PositionType = frappe.qb.DocType("Position Type")

	roles = GroupConcat(PositionType.position).distinct().as_("roles")

	query = (
		frappe.qb.from_(Person)
		.left_join(Family)
		.on(Family.name == Person.family)
		.left_join(Position)
		.on(
			(Position.parent == Person.name)
			& (Position.parenttype == "Person")
			& (Position.end_date.isnull() | (Position.end_date >= today))
		)
		.left_join(PositionType)
		.on(PositionType.name == Position.position)
		.select(
			Person.name,
			Person.full_name,
			Person.is_member,
			Person.membership_status,
			Person.is_baptized,
			Person.family,
			Family.family_name,
			Person.birthday,
			roles,
		)
		.groupby(Person.name)
		.orderby(Person.full_name)
	)

	if filters.get("person_name"):
		query = query.where(Person.full_name.like(f"%{filters['person_name']}%"))
	if filters.get("is_member"):
		query = query.where(Person.is_member == 1)
	if filters.get("is_baptized"):
		query = query.where(Person.is_baptized == 1)
	if filters.get("family"):
		query = query.where(Person.family == filters["family"])
	if filters.get("role"):
		ActivePosition = frappe.qb.DocType("Position")
		role_subquery = (
			frappe.qb.from_(ActivePosition)
			.select(ActivePosition.parent)
			.where(
				(ActivePosition.position == filters["role"])
				& (ActivePosition.end_date.isnull() | (ActivePosition.end_date >= today))
			)
		)
		query = query.where(Person.name.isin(role_subquery))

	return query.run(as_dict=True)
