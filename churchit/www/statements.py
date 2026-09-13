# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/statements"
		raise frappe.Redirect

	context.no_cache = 1
	context.title = "Giving Statements"

	person = frappe.db.get_value("Person", {"user": frappe.session.user}, ["name", "family"], as_dict=True)
	context.person = person
	if not person:
		context.statements = []
		return

	context.statements = get_own_statements(person)

	requested = frappe.form_dict.get("name")
	if requested:
		context.statement = open_own_statement(requested, person)


def get_own_statements(person):
	"""Statements addressed to *person*, plus their household's."""
	or_filters = {"person": person.name}
	if person.family:
		or_filters["family"] = person.family

	return frappe.get_all(
		"Giving Statement",
		or_filters=or_filters,
		fields=["name", "title", "from_date", "to_date", "total_amount"],
		order_by="to_date desc",
	)


def open_own_statement(name, person):
	"""Load one statement, but only if it belongs to this person or household."""
	statement = frappe.get_doc("Giving Statement", name)
	if statement.person != person.name and not (person.family and statement.family == person.family):
		raise frappe.PermissionError
	return statement
