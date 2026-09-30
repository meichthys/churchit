import json

import frappe
from frappe import _

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	get_item_totals,
	is_open_for_sign_up,
)
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import church_filters, session_church, session_person
from churchit.utils import resolve_link_titles


def get_context(context):
	if context.get("reference_doc"):
		# Link fields render as Autocomplete on the portal, which shows the raw docname
		# once the field is read only. Resolve the titles into a separate map for display:
		# rewriting them on reference_doc would leave the client script without the real
		# Function name, which it needs to load that function's sign-up items.
		display_doc = frappe._dict(context.reference_doc)
		resolve_link_titles([display_doc], "Function Sign-Up")
		context.link_titles = {
			"function": display_doc.function,
			"person": display_doc.person,
		}
	sign_up_functions = set(
		frappe.get_all("Function", filters=church_filters(session_church(), allow_sign_ups=1), pluck="name")
	)
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

	# The form script reads is_manager as "may sign up someone else", which only staff may.
	return {
		"person": session_person(),
		"is_manager": not is_portal_member(),
	}


@frappe.whitelist()
def get_function_sign_up_items(function: str):
	"""Return the sign-up items configured on a Function, with live signed-up totals.

	Members hold no Function DocPerm, so the check is the one the form lists functions by.
	"""
	if not is_open_for_sign_up(function):
		frappe.throw(_("This function is not open for you to sign up."), frappe.PermissionError)
	totals = get_item_totals(function)
	return [
		{
			"item": item,
			"quantity_needed": data["quantity_needed"],
			"quantity_signed_up": data["quantity_signed_up"],
		}
		for item, data in totals.items()
	]
