# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import date as Date

import frappe
from frappe import _
from frappe.core.doctype.data_import.import_provider import ImportProvider
from frappe.core.doctype.data_import.importer import ACTION_INSERT, INSERT
from frappe.model.document import Document
from frappe.utils import add_days, flt, get_datetime, getdate

from churchit.church_people.imports.people import SPREADSHEET
from churchit.church_people.imports.record import clean, get_imported_people
from churchit.church_scope import church_filters, default_church, is_multi_church, scoped
from churchit.contacts import EMAIL_DOCTYPE, get_primary_emails


class GivingImportProvider(ImportProvider):
	"""Adds each row of a giving history, such as a processor's export, as a Donation under its Gift ID.

	The Donation goes in the draft Collection of the row's batch and date. Finance checks and submits the
	Collections, which puts the gifts on the funds and the statements. A row that cannot be imported, or
	was imported before, is refused.
	"""

	def validate(self, import_file) -> list[dict]:
		if import_file.import_type != INSERT:
			return [{"message": _("A giving import only adds gifts. Choose Insert New Records.")}]

		rows = [(row.row_number, doc) for row in import_file.data if (doc := row.parse_doc(self.doctype))]
		history = GivingHistory([doc for _row, doc in rows])
		first_rows = {}
		warnings = []
		for row, doc in rows:
			gift_id = clean(doc.get("gift_id"))
			if gift_id and gift_id in first_rows:
				message = _("This gift is also on row {0}.").format(first_rows[gift_id])
			else:
				first_rows.setdefault(gift_id, row)
				message = history.get_refusal(doc)
			if message:
				warnings.append({"row": row, "message": message})
		return warnings

	def import_row(self, importer, doc):
		# A locking read waits for a concurrent import of the same Gift ID, then sees its gift.
		history = GivingHistory([doc], lock_gift_ids=True)
		if message := history.get_refusal(doc):
			frappe.throw(message)

		donation = {
			"fund": doc.get("fund"),
			"payment_type": doc.get("payment_type"),
			"person": history.get_givers(doc)[0],
			"amount": round_amount(doc.get("amount")),
			"check_number": clean(doc.get("check_number")),
			"notes": clean(doc.get("notes")),
			"legacy_id": clean(doc.get("gift_id")),
		}
		batch = clean(doc.get("batch")) or importer.data_import.name
		return add_to_collection(batch, getdate(doc.get("date")), donation), ACTION_INSERT


class GivingHistory:
	"""What the site already holds about the gifts of some import rows, read once for all of them."""

	def __init__(self, docs: list[dict], lock_gift_ids: bool = False):
		self.church = default_church() if is_multi_church() else None
		gift_ids = {clean(doc.get("gift_id")) for doc in docs} - {None}
		self.imported_gift_ids = get_imported_gift_ids(gift_ids, for_update=lock_gift_ids)
		self.people = get_imported_people(
			{(person_system(doc), clean(doc.get("person_id"))) for doc in docs if clean(doc.get("person_id"))}
		)
		self.people_by_email = get_people_by_email({email_key(doc) for doc in docs} - {None})
		self.online_gifts = get_charged_online_gifts(
			{getdate(doc.get("date")) for doc in docs if doc.get("date")}
		)
		self.fund_churches = {
			fund: frappe.db.get_value("Fund", fund, "church")
			for fund in {doc.get("fund") for doc in docs} - {None}
		}
		self.non_cash_types = set(frappe.get_all("Payment Type", {"is_non_cash": 1}, pluck="name"))

	def get_refusal(self, doc: dict) -> str | None:
		"""Why the row cannot be imported, or None."""
		gift_id = clean(doc.get("gift_id"))
		if not gift_id:
			return _("This row has no Gift ID.")
		if gift_id in self.imported_gift_ids:
			return _("Gift {0} is already imported.").format(gift_id)
		if message := self.get_fund_refusal(doc.get("fund")):
			return message
		if doc.get("payment_type") in self.non_cash_types:
			return _("Non-cash gifts cannot be imported. Enter them in a collection with a description.")
		givers = self.get_givers(doc)
		if not givers:
			return _("No one has this Person ID or email in your churches.")
		if len(givers) > 1:
			return _("More than one person has this email. Give the row a Person ID.")
		if (round_amount(doc.get("amount")), getdate(doc.get("date")), email_key(doc)) in self.online_gifts:
			return _(
				"An Online Donation that the gateway charged has the same amount, date and email. Churchit records that gift from the Online Donation, so leave this row out."
			)
		return None

	def get_fund_refusal(self, fund: str) -> str | None:
		owner = self.fund_churches.get(fund)
		if self.church and owner and owner != self.church:
			return _(
				"Fund {0} belongs to another church. Tick Shared with all churches on it, or choose a fund of your church."
			).format(fund)
		return None

	def get_givers(self, doc: dict) -> list[str]:
		"""The person the row's Person ID was imported as, else everyone who has its email."""
		if person_id := clean(doc.get("person_id")):
			if person := self.people.get((person_system(doc), person_id)):
				return [person]
		return self.people_by_email.get(email_key(doc), [])


def person_system(doc: dict) -> str:
	return clean(doc.get("person_system")) or SPREADSHEET


def email_key(doc: dict) -> str | None:
	email = clean(doc.get("email"))
	return email.lower() if email else None


def round_amount(amount) -> float:
	return flt(amount, frappe.get_precision("Donation", "amount"))


def get_imported_gift_ids(gift_ids: set[str], for_update: bool = False) -> set[str]:
	"""The *gift_ids* already on a Donation of a Collection in the importer's churches that is not cancelled."""
	if not gift_ids:
		return set()
	Collection, Donation = frappe.qb.DocType("Collection"), frappe.qb.DocType("Donation")
	query = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on(Donation.parent == Collection.name)
		.select(Donation.legacy_id)
		.where(
			(Donation.parenttype == "Collection")
			& Donation.legacy_id.isin(list(gift_ids))
			& (Collection.docstatus < 2)
		)
	)
	if for_update:
		query = query.for_update()
	return set(scoped(query, Collection, {}).run(pluck=True))


def get_people_by_email(emails: set[str]) -> dict[str, list[str]]:
	"""{email: the people in the importer's churches who have it}."""
	if not emails:
		return {}
	Email, Person = frappe.qb.DocType(EMAIL_DOCTYPE), frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Email)
		.join(Person)
		.on(Email.parent == Person.name)
		.select(Email.email_address, Person.name)
		.distinct()
		.where((Email.parenttype == "Person") & Email.email_address.isin(list(emails)))
	)
	people = {}
	for email, person in scoped(query, Person, {}).run():
		people.setdefault(email.lower(), []).append(person)
	return people


def get_charged_online_gifts(dates: set[Date]) -> set[tuple[float, Date, str]]:
	"""(amount charged, date, email) of the charged Online Donations in the importer's churches on *dates*.

	Charged is Paid, Needs Review, or Pending with a completed payment (its callback was lost), because
	Finance records the last two later. A gift's email is the one given on /give, and its giver's primary email.
	"""
	if not dates:
		return set()
	OnlineDonation, Request = frappe.qb.DocType("Online Donation"), frappe.qb.DocType("Integration Request")
	query = (
		frappe.qb.from_(OnlineDonation)
		.left_join(Request)
		.on(
			(Request.reference_doctype == "Online Donation")
			& (Request.reference_docname == OnlineDonation.name)
			& (Request.status == "Completed")
		)
		.select(
			OnlineDonation.amount,
			OnlineDonation.fee_amount,
			OnlineDonation.creation,
			OnlineDonation.email,
			OnlineDonation.person,
		)
		.where(
			(
				OnlineDonation.status.isin(["Paid", "Needs Review"])
				| ((OnlineDonation.status == "Pending") & Request.name.isnotnull())
			)
			& (OnlineDonation.creation >= min(dates))
			& (OnlineDonation.creation < add_days(max(dates), 1))
		)
	)
	gifts = scoped(query, OnlineDonation, {}).run(as_dict=True)
	giver_emails = get_primary_emails("Person", [gift.person for gift in gifts])
	return {
		(round_amount(flt(gift.amount) + flt(gift.fee_amount)), getdate(gift.creation), email.lower())
		for gift in gifts
		for email in (gift.email, giver_emails.get(gift.person))
		if email
	}


def add_to_collection(batch: str, date: Date, donation: dict) -> Document:
	"""Add *donation* to the draft Collection of *batch* and *date* in the importer's church, and to its expected total."""
	filters = church_filters(default_church(), import_batch=batch, date=get_datetime(date), docstatus=0)
	if name := frappe.db.get_value("Collection", filters, "name", for_update=True):
		collection = frappe.get_doc("Collection", name)
		collection.append("donations", donation)
		collection.expected_total = flt(
			flt(collection.expected_total) + flt(donation["amount"]), collection.precision("expected_total")
		)
		return collection.save()

	return frappe.get_doc(
		{
			"doctype": "Collection",
			"import_batch": batch,
			"date": get_datetime(date),
			"expected_total": donation["amount"],
			"donations": [donation],
		}
	).insert()
