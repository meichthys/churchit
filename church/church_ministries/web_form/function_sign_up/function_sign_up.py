import frappe


def get_context(context):
	if frappe.session.user == "Guest":
		return

	person = frappe.db.get_value("Person", {"portal_user": frappe.session.user}, "name")
	if person:
		context.person = person


@frappe.whitelist()
def get_person_for_user():
	"""Return the Person linked to the current logged-in user."""
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("Person", {"portal_user": frappe.session.user}, "name")
