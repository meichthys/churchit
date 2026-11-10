import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class MissionaryPaymentBatch(Document):
	def autoname(self):
		if not self.batch_number:
			self.batch_number = frappe.model.naming.make_autoname("MPB-.####")
		self.name = self.batch_number

	def validate(self):
		self.calculate_total()
		self.handle_status_changes()

	def calculate_total(self):
		total = 0
		for row in self.payments:
			if row.payment:
				amount = frappe.db.get_value("Missionary Payment", row.payment, "amount")
				total += flt(amount)
		self.total_amount = total

	def handle_status_changes(self):
		if self.has_value_changed("status"):
			if self.status == "Sent":
				self.sent_date = today()
				self.sent_by = frappe.session.user
				self.update_payments_status("Sent")
				self.send_batch_sent_notification()
			elif self.status == "Reconciled":
				self.reconciled_date = today()
				self.reconciled_by = frappe.session.user
				self.update_payments_status("Reconciled")

	def update_payments_status(self, new_status):
		for row in self.payments:
			if row.payment:
				p_doc = frappe.get_doc("Missionary Payment", row.payment)
				p_doc.status = new_status
				p_doc.batch = self.name
				if new_status == "Sent":
					p_doc.sent_date = self.sent_date
					p_doc.sent_by = self.sent_by
				elif new_status == "Reconciled":
					p_doc.reconciled_date = self.reconciled_date
					p_doc.reconciled_by = self.reconciled_by
				p_doc.save(ignore_permissions=True)

	def send_batch_sent_notification(self):
		from churchit.church_missions.doctype.missionary_support_schedule.missionary_support_schedule import (
			get_treasurer_emails,
		)

		recipients = get_treasurer_emails()
		if not recipients:
			return

		context = {
			"batch_number": self.batch_number,
			"total_amount": self.total_amount,
			"count": len(self.payments),
			"reference": self.reference or "",
			"batch_date": self.batch_date,
		}

		template_path = "churchit/templates/batch_sent.html"
		try:
			message = frappe.render_template(template_path, context)
		except Exception:
			message = f"Batch {self.batch_number} has been sent with total amount {self.total_amount} across {len(self.payments)} payments."

		subject = f"Missionary Payment Batch Sent: {self.batch_number}"
		frappe.sendmail(recipients=recipients, subject=subject, message=message)


@frappe.whitelist()
def create_batch_from_payments(payment_names, payment_method="Wire", reference=None):
	if isinstance(payment_names, str):
		import json

		payment_names = json.loads(payment_names)

	if not payment_names:
		frappe.throw("No payments provided to create batch.")

	batch = frappe.get_doc(
		{
			"doctype": "Missionary Payment Batch",
			"batch_date": today(),
			"payment_method": payment_method,
			"reference": reference,
			"status": "Draft",
			"payments": [{"payment": p} for p in payment_names],
		}
	)
	batch.insert(ignore_permissions=True)

	# Update payments to link batch
	for p_name in payment_names:
		frappe.db.set_value("Missionary Payment", p_name, "batch", batch.name)

	return batch.name
