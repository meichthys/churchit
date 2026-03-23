import frappe


def get_context(context):
	pass


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
