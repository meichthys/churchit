import json

import frappe

from churchit.utils import resolve_link_titles


def get_context(context):
	if context.get("reference_doc"):
		resolve_link_titles([context.reference_doc], "Function Sign-Up")
	sign_up_functions = set(frappe.get_all("Function", filters={"allow_sign_ups": 1}, pluck="name"))
	context.has_sign_up_functions = bool(sign_up_functions)

	# Filter the Function autocomplete options to only show functions with sign-ups enabled.
	# Options may be a JSON string of [{value, label}] objects (when show_title_field_in_link
	# is set) or a newline-separated string of names.
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "function":
			try:
				options = json.loads(field.options)
				field.options = json.dumps(
					[opt for opt in options if opt.get("value") in sign_up_functions],
					default=str,
				)
			except (json.JSONDecodeError, TypeError, AttributeError):
				options = (field.options or "").split("\n")
				field.options = "\n".join(opt for opt in options if opt in sign_up_functions)
			break


@frappe.whitelist()
def get_user_context():
	"""Return person and role info for the current user."""
	if frappe.session.user == "Guest":
		return None

	user_roles = frappe.get_roles(frappe.session.user)
	is_manager = "Church Manager" in user_roles or "System Manager" in user_roles

	person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")

	return {
		"person": person,
		"is_manager": is_manager,
	}


@frappe.whitelist()
def get_function_sign_up_items(function):
	"""Return the sign-up items configured on a Function, with live signed-up totals."""
	from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
		get_function_item_totals,
	)

	totals = get_function_item_totals(function)
	return [
		{
			"item": item,
			"quantity_needed": data["quantity_needed"],
			"quantity_signed_up": data["quantity_signed_up"],
		}
		for item, data in totals.items()
	]
