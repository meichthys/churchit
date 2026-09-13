# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from churchit.contacts import primary_email


class GivingStatement(Document):
	"""A donor's contributions for a period, as an issued document.

	Lines are rebuilt from the underlying Donations on every save, so correcting
	a mis-entered gift and re-saving reissues an accurate statement.
	"""

	def validate(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date."))

		self.set_title()
		self.set_email()
		self.build_lines()

	def set_title(self):
		full_name = frappe.db.get_value("Person", self.person, "full_name") or self.person
		start, end = getdate(self.from_date), getdate(self.to_date)
		period = start.year if start.year == end.year else f"{start.year}-{end.year}"
		self.title = f"{full_name} - {period}"

	def set_email(self):
		self.email = primary_email(frappe.get_doc("Person", self.person))

	@property
	def covered_people(self):
		"""Every person whose giving belongs on this statement."""
		if not self.family:
			return [self.person]
		members = frappe.get_all("Family Members", filters={"parent": self.family}, pluck="member")
		return members or [self.person]

	def build_lines(self):
		self.set("lines", [])
		for row in get_donations(self.covered_people, self.from_date, self.to_date):
			self.append("lines", row)
		self.total_amount = sum(row.amount or 0 for row in self.lines)


def get_donations(people, from_date, to_date):
	"""Submitted donations by *people* between the two dates, oldest first."""
	if not people:
		return []

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	return (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.select(
			Collection.date,
			Donation.person,
			Donation.fund,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
		)
		.where(
			(Donation.parenttype == "Collection")
			& Donation.person.isin(people)
			& (Collection.docstatus == 1)
			& (Collection.date >= from_date)
			& (Collection.date <= to_date)
		)
		.orderby(Collection.date)
		.run(as_dict=True)
	)


def statement_header():
	"""Church identity and acknowledgment wording printed on every statement.

	Exposed to templates through the ``jinja`` hook so the statement markup can
	stay free of lookups.
	"""
	church = frappe.get_all(
		"Church",
		fields=["church_name", "legal_name", "tax_id", "address"],
		order_by="lft asc",
		limit=1,
	)
	church = church[0] if church else {}

	address = ""
	if church.get("address"):
		address = frappe.get_doc("Address", church["address"]).get_display()

	return {
		"name": church.get("legal_name") or church.get("church_name") or "",
		"tax_id": church.get("tax_id") or "",
		"address": address,
		"acknowledgment": frappe.db.get_single_value("Giving Settings", "statement_acknowledgment") or "",
	}


def get_givers(from_date, to_date):
	"""Everyone with a submitted donation in the period."""
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")

	return (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.select(Donation.person)
		.distinct()
		.where(
			(Donation.parenttype == "Collection")
			& Donation.person.isnotnull()
			& (Collection.docstatus == 1)
			& (Collection.date >= from_date)
			& (Collection.date <= to_date)
		)
		.run(pluck=True)
	)


def get_statement_recipients(from_date, to_date):
	"""Map every giver in the period onto the record their statement belongs to.

	Returns ``[{"person", "family"}]`` — one entry per statement to issue. When
	Giving Settings groups by household, everyone in a Family collapses onto the
	head of household, or the first member when no head is marked.
	"""
	givers = get_givers(from_date, to_date)
	if not givers:
		return []

	by_household = frappe.db.get_single_value("Giving Settings", "statement_grouping") != "Person"
	if not by_household:
		return [{"person": person, "family": None} for person in givers]

	recipients = {}
	for person in givers:
		family = frappe.db.get_value("Person", person, "family")
		if not family:
			recipients[person] = {"person": person, "family": None}
			continue
		if family not in recipients:
			recipients[family] = {"person": household_recipient(family, person), "family": family}
	return list(recipients.values())


def household_recipient(family, fallback):
	"""The person a household statement is addressed to."""
	head = frappe.get_all(
		"Person", filters={"family": family, "is_head_of_household": 1}, pluck="name", limit=1
	)
	return head[0] if head else fallback


@frappe.whitelist()
def generate_statements(from_date, to_date):
	"""Create a statement for every giver in the period. Returns how many were made.

	Re-running is safe: a statement already covering the same period for the same
	recipient is rebuilt rather than duplicated.
	"""
	frappe.only_for(("Church Manager", "System Manager"))

	created = updated = 0
	for recipient in get_statement_recipients(from_date, to_date):
		existing = frappe.db.exists(
			"Giving Statement",
			{"person": recipient["person"], "from_date": from_date, "to_date": to_date},
		)
		if existing:
			frappe.get_doc("Giving Statement", existing).save()
			updated += 1
			continue

		frappe.get_doc(
			{
				"doctype": "Giving Statement",
				"person": recipient["person"],
				"family": recipient["family"],
				"from_date": from_date,
				"to_date": to_date,
			}
		).insert()
		created += 1

	return {"created": created, "updated": updated}
