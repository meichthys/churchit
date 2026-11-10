import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class MissionarySupportSummary(Document):
	def validate(self):
		self.total_donations = flt(self.total_donations)
		self.total_disbursed = flt(self.total_disbursed)
		self.retained = self.total_donations - self.total_disbursed


@frappe.whitelist()
def generate_990_summary(year):
	year = int(year)
	start_date = f"{year}-01-01"
	end_date = f"{year}-12-31"

	# Find all missionaries with activity (donations or payments) in that year
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	MissionaryPayment = frappe.qb.DocType("Missionary Payment")

	# Get missionaries from donations in year where status = Paid
	don_missionaries = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.missionary)
		.where(
			(Donation.missionary.isnotnull())
			& (Donation.missionary != "")
			& (Donation.status == "Paid")
			& (Collection.docstatus == 1)
			& (Collection.date >= start_date)
			& (Collection.date <= end_date)
		)
		.distinct()
		.run(as_list=True)
	)

	# Get missionaries from missionary payments in year where status = Sent or Reconciled
	pay_missionaries = (
		frappe.qb.from_(MissionaryPayment)
		.select(MissionaryPayment.missionary)
		.where(
			(MissionaryPayment.missionary.isnotnull())
			& (MissionaryPayment.missionary != "")
			& (MissionaryPayment.status.isin(["Sent", "Reconciled"]))
			& (MissionaryPayment.payment_date >= start_date)
			& (MissionaryPayment.payment_date <= end_date)
		)
		.distinct()
		.run(as_list=True)
	)

	missionary_names = set([m[0] for m in don_missionaries] + [m[0] for m in pay_missionaries])

	for missionary in missionary_names:
		# Total donations: sum of all Donation records where missionary is set and status = Paid in that year
		don_sum_query = (
			frappe.qb.from_(Donation)
			.join(Collection)
			.on(Collection.name == Donation.parent)
			.select(frappe.qb.functions.Sum(Donation.amount))
			.where(
				(Donation.missionary == missionary)
				& (Donation.status == "Paid")
				& (Collection.docstatus == 1)
				& (Collection.date >= start_date)
				& (Collection.date <= end_date)
			)
		)
		don_res = don_sum_query.run()
		total_donations = flt(don_res[0][0]) if don_res and don_res[0][0] else 0

		# Total disbursed: sum of all Missionary Payment records (status = Sent or Reconciled) for that missionary in that year, where tax_deductible = 1
		pay_sum_query = (
			frappe.qb.from_(MissionaryPayment)
			.select(frappe.qb.functions.Sum(MissionaryPayment.amount))
			.where(
				(MissionaryPayment.missionary == missionary)
				& (MissionaryPayment.status.isin(["Sent", "Reconciled"]))
				& (MissionaryPayment.tax_deductible == 1)
				& (MissionaryPayment.payment_date >= start_date)
				& (MissionaryPayment.payment_date <= end_date)
			)
		)
		pay_res = pay_sum_query.run()
		total_disbursed = flt(pay_res[0][0]) if pay_res and pay_res[0][0] else 0

		retained = total_donations - total_disbursed
		church = frappe.db.get_value("Missionary", missionary, "church")

		# Check if summary exists for missionary + year
		existing = frappe.db.exists(
			"Missionary Support Summary",
			{"year": year, "missionary": missionary}
		)

		if existing:
			summary_doc = frappe.get_doc("Missionary Support Summary", existing)
			summary_doc.total_donations = total_donations
			summary_doc.total_disbursed = total_disbursed
			summary_doc.retained = retained
			summary_doc.fiscal_year_start = start_date
			summary_doc.fiscal_year_end = end_date
			summary_doc.church = church
			summary_doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({
				"doctype": "Missionary Support Summary",
				"year": year,
				"missionary": missionary,
				"church": church,
				"total_donations": total_donations,
				"total_disbursed": total_disbursed,
				"retained": retained,
				"fiscal_year_start": start_date,
				"fiscal_year_end": end_date,
			}).insert(ignore_permissions=True)

	return {"status": "success", "count": len(missionary_names)}
