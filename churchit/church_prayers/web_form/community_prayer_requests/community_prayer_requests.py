import frappe

from churchit.church_scope import church_filters, default_church, session_church
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
		# This list ignores permissions, so the member's own church is applied by hand.
		# church_filters rather than an equality: it admits shared records, which a
		# hand-written `church == x` would drop the day a request can be shared.
		scope = church_filters(session_church() or default_church())
		filters += [[field, *condition] for field, condition in scope.items()]

		rows = frappe.get_list(
			doctype,
			fields="*",
			distinct=True,
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
