import frappe
from frappe.model.document import Document


class MissionaryPayment(Document):
	def validate(self):
		if self.status == "Sent" and not self.sent_date:
			self.sent_date = frappe.utils.today()
			self.sent_by = frappe.session.user
		elif self.status == "Reconciled" and not self.reconciled_date:
			self.reconciled_date = frappe.utils.today()
			self.reconciled_by = frappe.session.user


@frappe.whitelist()
def mark_as_sent(name, reference):
	doc = frappe.get_doc("Missionary Payment", name)
	doc.check_permission("write")
	doc.reference = reference
	doc.status = "Sent"
	doc.sent_date = frappe.utils.today()
	doc.sent_by = frappe.session.user
	doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist()
def reconcile(name, reference):
	doc = frappe.get_doc("Missionary Payment", name)
	doc.check_permission("write")
	doc.reference = reference
	doc.status = "Reconciled"
	doc.reconciled_date = frappe.utils.today()
	doc.reconciled_by = frappe.session.user
	doc.save(ignore_permissions=True)
	return doc
