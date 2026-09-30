# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

from churchit.church_people.member_access import pin_to_members_own_person, validate_members_recipient
from churchit.utils import resolve_link_titles

CLOSED_STATUSES = ("Answered", "Archived", "Closed")


class PrayerRequest(Document):
	def before_insert(self):
		if not self.status:
			self.status = frappe.db.get_value("Prayer Request Status", {"status": "Requested"}, "name")

	def validate(self):
		self.validate_public_church()
		pin_to_members_own_person(self, "requestor")
		validate_members_recipient(self)
		# Resolve the display name for the dynamic recipient link using the linked
		# doctype's title_field (e.g. full_name for Person). Stored so it can be
		# shown in web form list views, which cannot resolve Dynamic Link titles.
		# See: https://github.com/frappe/frappe/issues/27330
		if self.recipient and self.recipient_type:
			meta = frappe.get_meta(self.recipient_type)
			title_field = meta.title_field or "name"
			self.recipient_name = (
				frappe.db.get_value(self.recipient_type, self.recipient, title_field) or self.recipient
			)
		else:
			self.recipient_name = None

	def validate_public_church(self):
		"""Keep a website request to a church the site actually offers.

		The anonymous web form carries the church of the page that took it, which
		is the only signal a guest gives; cleared here, `ensure_church` settles it.
		"""
		if frappe.session.user != "Guest" or not self.church:
			return
		if not frappe.db.get_value("Church", self.church, "publish"):
			self.church = None

	def has_webform_permission(self):
		# Invoked by web forms with apply_document_permissions=0
		# (the community-prayer-requests form) to grant read access to non-private
		# requests, without loosening the standard DocPerm (owner-only) used elsewhere.
		return frappe.session.user != "Guest" and not self.is_private


def get_list_context(context):
	context.filters = {"owner": frappe.session.user}
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		from frappe.www.list import get_list as default_get_list

		rows = default_get_list(doctype, txt, filters, limit_start, limit_page_length, **kwargs)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context
