import frappe

from church.utils import resolve_link_titles, setup_web_form_church_field


def get_context(context):
	setup_web_form_church_field(context)
	if context.get("reference_doc"):
		resolve_link_titles([context.reference_doc], "Alms Request")
