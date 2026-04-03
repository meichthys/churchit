import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form, nowdate


class FundTransfer(Document):
	def before_save(self):
		fund_part = f"{self.from_fund or ''} to {self.to_fund or ''}".strip()
		parts = [fund_part, str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)

	def validate(self):
		if self.from_fund == self.to_fund:
			frappe.throw("Source and destination funds must be different.")
		if self.amount <= 0:
			frappe.throw("Transfer amount must be greater than zero.")

	def on_submit(self):
		self.transfer_funds()

	def on_cancel(self):
		self.remove_fund_transfer_transactions()

	def transfer_funds(self):
		from_fund = frappe.get_doc("Fund", self.from_fund)
		to_fund = frappe.get_doc("Fund", self.to_fund)

		transfer_note = self.notes or ""
		from_note = f"Transfer to {self.to_fund}"
		to_note = f"Transfer from {self.from_fund}"
		if transfer_note:
			from_note += f" — {transfer_note}"
			to_note += f" — {transfer_note}"

		# Add transactions (no manual balance updates needed)
		from_fund.append(
			"transactions",
			{
				"amount": -self.amount,
				"source_type": "Fund Transfer",
				"source": self.name,
				"date": self.date or nowdate(),
				"notes": from_note,
			},
		)

		to_fund.append(
			"transactions",
			{
				"amount": self.amount,
				"source_type": "Fund Transfer",
				"source": self.name,
				"date": self.date or nowdate(),
				"notes": to_note,
			},
		)

		from_fund.save(ignore_permissions=True)
		to_fund.save(ignore_permissions=True)

		frappe.msgprint(
			f"✅ Transferred ${self.amount} from "
			f"{get_link_to_form('Fund', self.from_fund)} to "
			f"{get_link_to_form('Fund', self.to_fund)}."
		)

	def remove_fund_transfer_transactions(self):
		# Remove matching transactions from both funds
		for fund_name in [self.from_fund, self.to_fund]:
			fund_doc = frappe.get_doc("Fund", fund_name)
			# Keep only transactions not from this transfer
			fund_doc.set(
				"transactions",
				[
					tx
					for tx in fund_doc.transactions
					if not (tx.source_type == "Fund Transfer" and tx.source == self.name)
				],
			)
			fund_doc.save(ignore_permissions=True)
			fund_doc.reload()

		frappe.msgprint(
			f"⏪ Reverted transfer of ${self.amount} from "
			f"{get_link_to_form('Fund', self.from_fund)} to "
			f"{get_link_to_form('Fund', self.to_fund)}."
		)
