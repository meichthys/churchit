import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, flt


class MissionarySupportSchedule(Document):
	def validate(self):
		if self.monthly_amount and self.monthly_amount < 0:
			frappe.throw("Monthly Amount cannot be negative.")

		if self.end_date and self.start_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw("End Date cannot be before Start Date.")

		self._calculate_total_committed()
		self.recalculate_variance_fields()

	def _calculate_total_committed(self):
		if not self.monthly_amount or not self.start_date:
			self.total_committed = 0
			return

		start = getdate(self.start_date)
		end = getdate(self.end_date) if self.end_date else getdate(today())

		if end < start:
			self.total_committed = 0
			return

		months = (end.year - start.year) * 12 + (end.month - start.month) + 1
		self.total_committed = flt(self.monthly_amount) * months

	def recalculate_variance_fields(self):
		# sums all Missionary Payment records (status = Sent or Reconciled) for that schedule's missionary within the schedule's date range
		if not self.missionary:
			self.total_disbursed = 0
			self.variance = flt(self.total_committed)
			self.variance_flagged = 0
			return

		MissionaryPayment = frappe.qb.DocType("Missionary Payment")
		query = (
			frappe.qb.from_(MissionaryPayment)
			.select(frappe.qb.functions.Sum(MissionaryPayment.amount))
			.where(
				(MissionaryPayment.missionary == self.missionary)
				& (MissionaryPayment.status.isin(["Sent", "Reconciled"]))
			)
		)

		if self.start_date:
			query = query.where(MissionaryPayment.payment_date >= self.start_date)
		if self.end_date:
			query = query.where(MissionaryPayment.payment_date <= self.end_date)

		res = query.run()
		disbursed = flt(res[0][0]) if res and res[0][0] else 0
		self.total_disbursed = disbursed

		committed = flt(self.total_committed)
		# variance = total_committed - total_disbursed
		self.variance = committed - disbursed

		# check threshold
		threshold = flt(self.variance_threshold) if self.variance_threshold is not None else 10.0
		if committed > 0:
			pct = abs(flt(self.variance)) / committed * 100
			self.variance_flagged = 1 if pct > threshold else 0
		else:
			self.variance_flagged = 0

	@frappe.whitelist()
	def recalculate(self):
		self.recalculate_variance_fields()
		self.save(ignore_permissions=True)
		return {"total_disbursed": self.total_disbursed, "variance": self.variance, "variance_flagged": self.variance_flagged}

	@frappe.whitelist()
	def get_received_to_date(self):
		if not self.missionary:
			return 0

		fund_name = f"Missionary: {frappe.db.get_value('Missionary', self.missionary, 'title')}"
		if not frappe.db.exists("Fund", fund_name):
			return 0

		from churchit.church_scope import church_filters
		donations = frappe.get_all(
			"Donation",
			filters=church_filters(frappe.get_cached_doc("Fund", fund_name).church, {"fund": fund_name}),
			fields=["amount"],
		)
		return sum(flt(d.amount) for d in donations)

	@frappe.whitelist()
	def get_balance(self):
		committed = flt(self.total_committed)
		received = flt(self.get_received_to_date())
		return committed - received


@frappe.whitelist()
def recalculate_all_schedules():
	schedules = frappe.get_all("Missionary Support Schedule", filters={"status": "Active"}, fields=["name"])
	for s in schedules:
		doc = frappe.get_doc("Missionary Support Schedule", s.name)
		doc.recalculate_variance_fields()
		doc.save(ignore_permissions=True)


def daily_variance_check():
	"""Scheduled task (daily): recalculate total_disbursed and variance, flag if exceeds threshold, and notify Treasurer."""
	schedules = frappe.get_all(
		"Missionary Support Schedule",
		filters={"status": "Active"},
		fields=["name", "missionary", "total_committed", "total_disbursed", "variance", "variance_threshold", "variance_flagged", "notification_recipient"],
	)

	for sched in schedules:
		doc = frappe.get_doc("Missionary Support Schedule", sched.name)
		old_flag = doc.variance_flagged
		doc.recalculate_variance_fields()
		doc.save(ignore_permissions=True)

		# If variance exceeds threshold and wasn't flagged or we want to alert on check
		if doc.variance_flagged == 1:
			send_variance_alert(doc)


def send_variance_alert(schedule_doc):
	recipients = [schedule_doc.notification_recipient] if schedule_doc.notification_recipient else get_treasurer_emails()
	if not recipients:
		return

	missionary_name = frappe.db.get_value("Missionary", schedule_doc.missionary, "title") or schedule_doc.missionary
	committed = flt(schedule_doc.total_committed)
	disbursed = flt(schedule_doc.total_disbursed)
	variance = flt(schedule_doc.variance)
	pct = round(abs(variance) / committed * 100, 2) if committed > 0 else 0

	subject = f"Variance alert: {missionary_name} — committed ${committed}, disbursed ${disbursed}, variance ${variance} ({pct}%)"
	message = f"<p>Variance alert for <b>{missionary_name}</b>:</p><ul><li>Committed: ${committed}</li><li>Disbursed: ${disbursed}</li><li>Variance: ${variance} ({pct}%)</li></ul>"

	frappe.sendmail(recipients=recipients, subject=subject, message=message)


def create_recurring_missionary_payments():
	"""Daily scheduled task to generate recurring missionary payments from active schedules and run variance check."""
	today_date = getdate(today())
	schedules = frappe.get_all(
		"Missionary Support Schedule",
		filters={"status": "Active"},
		fields=["name", "missionary", "monthly_amount", "start_date", "end_date", "last_payment_month", "notify_treasurer", "notification_recipient"],
	)

	for sched in schedules:
		if not sched.monthly_amount or not sched.start_date:
			continue

		start = getdate(sched.start_date)
		end = getdate(sched.end_date) if sched.end_date else None

		if today_date < start:
			continue
		if end and today_date > end:
			continue

		current_month_str = today_date.strftime("%Y-%m")
		if sched.last_payment_month and sched.last_payment_month.strftime("%Y-%m") == current_month_str:
			continue

		payment_date_str = f"{current_month_str}-01"
		existing = frappe.db.exists(
			"Missionary Payment",
			{
				"missionary": sched.missionary,
				"payment_date": ["between", [f"{current_month_str}-01", f"{current_month_str}-31"]],
			},
		)
		if existing:
			frappe.db.set_value("Missionary Support Schedule", sched.name, "last_payment_month", payment_date_str, update_modified=False)
			continue

		from churchit.church_finances.doctype.fund.fund import get_or_create_missionary_fund
		fund_name = get_or_create_missionary_fund(sched.missionary)

		donation = frappe.get_doc({
			"doctype": "Donation",
			"fund": fund_name,
			"missionary": sched.missionary,
			"amount": sched.monthly_amount,
			"currency": "USD",
			"status": "Paid",
		}).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name}, fields=["name"])
		if payments:
			payment_name = payments[0].name
			frappe.db.set_value("Missionary Payment", payment_name, "payment_date", payment_date_str, update_modified=False)
		else:
			payment = frappe.get_doc({
				"doctype": "Missionary Payment",
				"donation": donation.name,
				"missionary": sched.missionary,
				"fund": fund_name,
				"amount": sched.monthly_amount,
				"payment_date": payment_date_str,
				"status": "Scheduled",
				"tax_deductible": 1,
			}).insert(ignore_permissions=True)
			payment_name = payment.name

		sched_doc = frappe.get_doc("Missionary Support Schedule", sched.name)
		sched_doc.append("missionary_payments", {"payment": payment_name})
		sched_doc.last_payment_month = payment_date_str
		sched_doc.save(ignore_permissions=True)

		if sched.notify_treasurer:
			send_missionary_payment_due_notification(sched_doc, payment_name, current_month_str)

	# Run daily variance check
	daily_variance_check()


def get_treasurer_emails():
	users = frappe.get_all(
		"Has Role",
		filters={"role": "Church Treasurer", "parenttype": "User"},
		fields=["parent"],
	)
	if not users:
		users = frappe.get_all(
			"Has Role",
			filters={"role": "Church Finance", "parenttype": "User"},
			fields=["parent"],
		)
	emails = [u.parent for u in users if u.parent]
	return emails or ["treasurer@example.com"]


def send_missionary_payment_due_notification(schedule_doc, payment_name, month_year):
	recipients = [schedule_doc.notification_recipient] if schedule_doc.notification_recipient else get_treasurer_emails()
	if not recipients:
		return

	missionary_name = frappe.db.get_value("Missionary", schedule_doc.missionary, "title") or schedule_doc.missionary
	payment_doc = frappe.get_doc("Missionary Payment", payment_name)

	context = {
		"missionary_name": missionary_name,
		"month_year": month_year,
		"amount": payment_doc.amount,
		"fund": payment_doc.fund,
		"payment_date": payment_doc.payment_date,
		"payment_link": frapy_get_url(payment_name),
	}

	template_path = "churchit/templates/missionary_payment_due.html"
	try:
		message = frappe.render_template(template_path, context)
	except Exception:
		message = f"Missionary Payment Due for {missionary_name} ({month_year}): Amount {payment_doc.amount}, Fund {payment_doc.fund}."

	subject = f"Missionary Payment Due: {missionary_name} — {month_year}"
	frappe.sendmail(recipients=recipients, subject=subject, message=message)


def frapy_get_url(payment_name):
	from frappe.utils import get_url
	return f"{get_url()}/app/missionary-payment/{payment_name}"
