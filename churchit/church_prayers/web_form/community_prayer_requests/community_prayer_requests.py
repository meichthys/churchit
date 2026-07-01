import frappe

from churchit.utils import resolve_link_titles


def get_context(context):
	if context.get("reference_doc"):
		resolve_link_titles([context.reference_doc], "Prayer Request")


def get_list_context(context):
	# The Prayer Request doctype's get_list_context restricts to `owner = <user>`.
	# Clear that so this community view shows requests from everyone.
	context.filters = None
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		if isinstance(filters, dict):
			filters = [[k, "=", v] for k, v in filters.items()]
		filters = list(filters or [])
		# Force is_private = 0 so private requests never leak, regardless of client input.
		filters.append(["is_private", "=", 0])

		rows = frappe.get_list(
			doctype,
			fields="distinct *",
			filters=filters,
			limit_start=limit_start,
			limit_page_length=limit_page_length,
			order_by="modified desc",
			ignore_permissions=True,
		)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context
