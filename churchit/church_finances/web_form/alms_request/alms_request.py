import frappe

from churchit.utils import resolve_link_titles


def get_context(context):
	if context.get("reference_doc"):
		resolve_link_titles([context.reference_doc], "Alms Request")
