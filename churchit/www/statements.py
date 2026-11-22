# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/statements"
		raise frappe.Redirect

	requested = frappe.form_dict.get("name")
	if not requested:
		raise frappe.PageDoesNotExistError

	person = frappe.db.get_value("Person", {"user": frappe.session.user}, ["name", "family"], as_dict=True)
	if not person:
		raise frappe.PermissionError

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = "Giving Statements"
	context.statement = open_own_statement(requested, person)


def open_own_statement(name, person):
	"""Load one statement, but only if it belongs to this person or household."""
	statement = frappe.get_doc("Giving Statement", name)
	if statement.person != person.name and not (person.family and statement.family == person.family):
		raise frappe.PermissionError
	return statement
