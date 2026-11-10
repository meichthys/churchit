import frappe
from frappe.model.document import Document
from frappe.utils import today


class BankTransaction(Document):
	def autoname(self):
		if not self.txn_id:
			self.txn_id = frappe.model.naming.make_autoname("BT-.####")
		self.name = self.txn_id


@frappe.whitelist()
def match_transaction(txn_name, payment_name):
	txn = frappe.get_doc("Bank Transaction", txn_name)
	payment = frappe.get_doc("Missionary Payment", payment_name)

	if txn.status == "Matched":
		frappe.throw("This bank transaction is already matched.")

	if payment.status == "Reconciled":
		frappe.throw("This missionary payment is already reconciled.")

	# Link records
	txn.matched_payment = payment.name
	txn.status = "Matched"
	txn.save(ignore_permissions=True)

	payment.bank_transaction = txn.name
	payment.status = "Reconciled"
	payment.reconciled_by = frappe.session.user
	payment.reconciled_date = today()
	payment.save(ignore_permissions=True)

	return {"status": "success"}
