# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from church.utils import resolve_link_titles


class PrayerRequest(Document):
	def before_insert(self):
		if not self.status:
			self.status = frappe.db.get_value("Prayer Request Status", {"status": "Requested"}, "name")

	def validate(self):
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
