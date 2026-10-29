import frappe

from churchit.church_prayers.prayer_access import get_community_filters, get_open_request_filters
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
			# The web list sends the form's condition as {field: [operator, value]}.
			filters = [[k, *v] if isinstance(v, list) else [k, "=", v] for k, v in filters.items()]
		filters = list(filters or [])
		# This list ignores permissions, so the member's church, visibilities and open requests are applied
		# here, after the browser's filters, which can only narrow them.
		open_filters, or_filters = get_open_request_filters()
		conditions = {**get_community_filters(), **open_filters}
		filters += [[field, *condition] for field, condition in conditions.items()]

		rows = frappe.get_list(
			doctype,
			fields="*",
			distinct=True,
			filters=filters,
			or_filters=or_filters,
			limit_start=limit_start,
			limit_page_length=limit_page_length,
			order_by="modified desc",
			ignore_permissions=True,
		)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context
