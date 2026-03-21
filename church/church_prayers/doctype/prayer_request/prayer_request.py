# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.website.website_generator import WebsiteGenerator


class PrayerRequest(Document):
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
	# Only show documents created by active user
	context.filters = {"owner": frappe.session.user}
	# Sort the portal list view by status descending
	context.order_by = "modified desc"
	return context
