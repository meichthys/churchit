# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fixture helpers shared by the app's tests.

Tests run inside one transaction per test class, so records made by one test
are visible to the next. Helpers here either look up an existing record first
(``ensure``) or take names the caller keeps unique (``make_person``).
"""

import frappe


def ensure(doctype, filters, values=None):
	"""Return the name of the record matching *filters*, inserting it if missing."""
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **(values or filters)})
	return doc.insert(ignore_permissions=True).name


def ensure_user(email, first_name, roles=("Church User",)):
	"""Return *email* after making sure a User with the given roles exists."""
	if frappe.db.exists("User", email):
		return email
	user = frappe.new_doc("User")
	user.update({"email": email, "first_name": first_name})
	user.flags.no_welcome_mail = True
	for role in roles:
		user.append("roles", {"role": role})
	user.insert(ignore_permissions=True)
	return email


def make_person(first_name, last_name=None, **values):
	return frappe.get_doc(
		{"doctype": "Person", "first_name": first_name, "last_name": last_name, **values}
	).insert(ignore_permissions=True)


def make_function(function_name, **values):
	function_type = ensure("Function Type", {"type": "_Test Function Type"})
	return frappe.get_doc(
		{
			"doctype": "Function",
			"function_name": function_name,
			"type": function_type,
			"start_date": "2031-05-01",
			**values,
		}
	).insert(ignore_permissions=True)


def make_address(title, **values):
	return frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Personal",
			"address_line1": "1 Main St",
			"city": "Springfield",
			"country": "United States",
			**values,
		}
	).insert(ignore_permissions=True)
