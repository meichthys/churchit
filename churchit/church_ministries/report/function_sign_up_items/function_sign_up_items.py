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
			"fieldname": "sign_up_display",
			"fieldtype": "HTML",
			"label": _("Sign Up"),
			"width": 250,
		},
		{
			"fieldname": "function_display",
			"fieldtype": "HTML",
			"label": _("Function"),
			"width": 200,
		},
		{
			"fieldname": "item",
			"fieldtype": "Link",
			"label": _("Item"),
			"options": "Sign-Up Item",
			"width": 200,
		},
		{
			"fieldname": "person_display",
			"fieldtype": "HTML",
			"label": _("Person"),
			"width": 250,
		},
		{"fieldname": "my_quantity", "fieldtype": "Int", "label": _("Quantity"), "width": 100},
	]


def get_data(filters=None):
	filters = filters or {}

	SignUp = frappe.qb.DocType("Function Sign-Up")
	SignUpItem = frappe.qb.DocType("Function Sign-Up Item")
	Function = frappe.qb.DocType("Function")
	Person = frappe.qb.DocType("Person")

	query = (
		frappe.qb.from_(SignUp)
		.inner_join(SignUpItem)
		.on(SignUp.name == SignUpItem.parent)
		.inner_join(Function)
		.on(SignUp.function == Function.name)
		.inner_join(Person)
		.on(SignUp.person == Person.name)
		.select(
			SignUp.name,
			SignUp.title,
			SignUp.function,
			Function.function_name,
			SignUpItem.item,
			SignUp.person,
			Person.full_name,
			SignUpItem.my_quantity,
		)
		.orderby(SignUp.name)
		.orderby(SignUp.function)
		.orderby(SignUpItem.item)
	)

	if filters.get("function"):
		query = query.where(SignUp.function == filters["function"])
	if filters.get("item"):
		query = query.where(SignUpItem.item == filters["item"])
	if filters.get("person"):
		query = query.where(SignUp.person == filters["person"])

	rows = scoped(query, Function, filters).run(as_dict=True)

	# Format as clickable links with titles
	for row in rows:
		row["sign_up_display"] = f'<a href="/app/function-sign-up/{row["name"]}">{row["title"]}</a>'
		row["function_display"] = f'<a href="/app/function/{row["function"]}">{row["function_name"]}</a>'
		row["person_display"] = f'<a href="/app/person/{row["person"]}">{row["full_name"]}</a>'

	return rows
