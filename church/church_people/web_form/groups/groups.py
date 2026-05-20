import frappe


def get_context(context):
	pass


def get_list_context(context):
	"""Filter the /groups listing to groups the user is a member of
	(restricted to ``show_in_portal``)."""
	user = frappe.session.user
	person = frappe.db.get_value("Person", {"user": user}, "name") if user != "Guest" else None

	my_groups = (
		[r.parent for r in frappe.get_all("Group Member", {"person": person, "parenttype": "Group"}, ["parent"])]
		if person else []
	)

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		filters = list(filters or [])
		filters.append(["name", "in", my_groups or [""]])
		filters.append(["show_in_portal", "=", 1])
		return frappe.get_list(
			doctype,
			fields="distinct *",
			filters=filters,
			limit_start=limit_start,
			limit_page_length=limit_page_length,
			order_by="group_name",
			ignore_permissions=True,
		)

	context.get_list = get_list
	context.order_by = "group_name"
	return context
