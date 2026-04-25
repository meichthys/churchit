# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from church.utils import resolve_link_titles


class AlmsRequest(Document):
	def before_save(self):
		# Set the alms request title
		recipient_label = self.recipient or ""
		if self.recipient and self.recipient_type:
			meta = frappe.get_meta(self.recipient_type)
			if meta.title_field:
				recipient_label = (
					frappe.db.get_value(self.recipient_type, self.recipient, meta.title_field)
					or self.recipient
				)
		parts = [recipient_label, str(self.amount or ""), self.status or ""]
		self.title = " - ".join(p for p in parts if p)


@frappe.whitelist()
def create_expense(alms_request_name):
	"""Create a Expense from the given Alms Request."""
	alms = frappe.get_doc("Alms Request", alms_request_name)
	alms.check_permission("read")
	# Make sure an expense type and amount are provided
	if not alms.amount:
		frappe.throw("⚠️ An amount is required for an expense to be created.")
	if not alms.expense_type:
		frappe.throw("⚠️ An expense type is required for an expense to be created.")
	expense = frappe.new_doc("Expense")
	expense.title = f"Alms: {alms.title}"
	expense.amount = alms.amount
	expense.type = alms.expense_type
	expense.date = frappe.utils.now()
	expense.insert()
	expense.submit()
	frappe.db.set_value("Alms Request", alms_request_name, "associated_expense", expense.name)


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
