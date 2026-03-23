import frappe


def get_context(context):
	# Filter the Function autocomplete options to only show functions with sign-ups enabled
	sign_up_functions = set(
		frappe.get_all("Function", filters={"allow_sign_ups": 1}, pluck="name")
	)
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "function":
			if isinstance(field.options, str):
				options = field.options.split("\n")
			else:
				options = field.options or []
			field.options = "\n".join(
				opt for opt in options if opt in sign_up_functions
			)
			break


@frappe.whitelist()
def get_user_context():
	"""Return church, person, and role info for the current user."""
	if frappe.session.user == "Guest":
		return None

	user_roles = frappe.get_roles(frappe.session.user)
	is_manager = "Church Manager" in user_roles or "System Manager" in user_roles

	church = frappe.db.get_value("User", frappe.session.user, "church")
	person = frappe.db.get_value("Person", {"portal_user": frappe.session.user}, "name")

	return {
		"church": church,
		"person": person,
		"is_manager": is_manager,
	}
