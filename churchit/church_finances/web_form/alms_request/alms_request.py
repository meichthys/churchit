import frappe

from churchit.church_finances.doctype.alms_request.alms_request import is_reviewed
from churchit.church_people.member_access import is_member_only
from churchit.utils import resolve_link_titles


def get_context(context):
	request = context.get("reference_doc")
	if not request:
		return
	# A reviewed request is the care team's: its requester reads it but no longer edits or deletes it.
	if is_member_only("Alms Request", frappe.session.user) and is_reviewed(request):
		context.allow_edit = 0
		context.has_delete_permission = False
	resolve_link_titles([request], "Alms Request")
