import frappe
from frappe.model.document import Document


class Budget(Document):
	def before_save(self):
		self.budgeted_amount = sum(row.budgeted_amount or 0 for row in (self.lines or []))

	@frappe.whitelist()
	def add_all_expense_types(self):
		existing = {row.expense_type for row in (self.lines or [])}
		types = frappe.get_all("Expense Type", filters={"is_group": 0}, pluck="name")
		added = 0
		for t in sorted(types):
			if t not in existing:
				self.append("lines", {"expense_type": t, "budgeted_amount": 0})
				added += 1
		self.before_save()
		return added
