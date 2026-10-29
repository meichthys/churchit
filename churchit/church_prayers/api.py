import frappe
from frappe import _
from frappe.permissions import has_permission
from frappe.utils import now_datetime


@frappe.whitelist(methods=["POST"])
def create_prayer(prayer_request: str, content: str | None = None):
	"""Record a Prayer for a Prayer Request on behalf of the current user.

	Any logged-in user who can see the target request, in the desk or on the Community
	Prayer Requests page, may pray for it. Prayer records are created with ignore_permissions
	since Church Users don't have DocPerm to create Prayers directly, so they go through this endpoint.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to pray."), frappe.PermissionError)

	pr = frappe.get_doc("Prayer Request", prayer_request)
	if not (has_permission(pr.doctype, "read", pr, print_logs=False) or pr.has_webform_permission()):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
	if not person:
		frappe.throw(_("No Person record is linked to your user account."))

	prayer = frappe.get_doc(
		{
			"doctype": "Prayer",
			"person": person,
			"date": now_datetime(),
			"content": content or None,
			"topics": [{"topic_type": "Prayer Request", "topic": pr.name}],
		}
	)
	prayer.insert(ignore_permissions=True)
	return {"name": prayer.name}
