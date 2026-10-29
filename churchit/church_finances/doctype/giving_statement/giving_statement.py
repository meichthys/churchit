# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, now_datetime, sbool

from churchit.church_foundations.doctype.church.church import inherited_value
from churchit.church_people.household import salutation
from churchit.church_scope import CHURCH_FIELD, has_church_access, root_church, scoped
from churchit.contacts import primary_email

STATEMENT_ROLES = ("Church Manager", "Church Finance", "System Manager")
EMAIL_TEMPLATE = "Giving Statement"
PRINT_FORMAT = "Contribution Statement"


class GivingStatement(Document):
	"""A donor's contributions for a period, as an issued document.

	Lines are rebuilt from the underlying Donations on every save, so correcting
	a mis-entered gift and re-saving reissues an accurate statement.
	"""

	def validate(self):
		self.refuse_another_churches_statement()
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date."))

		self.set_title()
		self.set_email()
		self.build_lines()

	def refuse_another_churches_statement(self):
		"""A statement is made in, or moved out of, only a church the user holds.

		Frappe checks the create right before an empty `church` is fetched from the person, and checks
		write on the church the caller sends, not the stored one. The person's church does not count:
		generate_statements issues a statement in the issuer's church for a giver from another church on
		purpose. Writes with ignore_permissions are the app's own and are not refused.
		"""
		if self.flags.ignore_permissions or not (
			self.has_value_changed("person") or self.has_value_changed(CHURCH_FIELD)
		):
			return
		stored = self.get_doc_before_save() or frappe._dict()
		for church in (self.church, stored.church):
			if not has_church_access(frappe.session.user, church):
				frappe.throw(
					_("{0} is not one of your churches, so you cannot issue or move its statements.").format(
						frappe.db.get_value("Church", church, "church_name") or church
					),
					frappe.PermissionError,
				)

	@property
	def period(self) -> str:
		start, end = getdate(self.from_date), getdate(self.to_date)
		return str(start.year) if start.year == end.year else f"{start.year}-{end.year}"

	def set_title(self):
		full_name = frappe.db.get_value("Person", self.person, "full_name") or self.person
		self.title = f"{full_name} - {self.period}"

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
		before = self.get_doc_before_save()
		self.set("lines", [])
		for row in get_donations(self.covered_people, self.from_date, self.to_date):
			self.append("lines", row)
		self.total_amount = flt(sum(row.amount or 0 for row in self.lines), self.precision("total_amount"))
		# Changed lines have not been emailed yet, even with the same total (a non-cash gift adds 0).
		if not before or get_line_values(before.lines) != get_line_values(self.lines):
			self.emailed_on = None

	def send_by_email(self):
		"""Queue this statement to its email address with its PDF, then log and stamp the send.

		The PDF is made when the email leaves the queue, so the caller can hold the row lock meanwhile.
		"""
		context = {
			"doc": self,
			"addressee": salutation(self.family)
			or frappe.db.get_value("Person", self.person, "first_name")
			or _("Friend"),
			"period": self.period,
			"church_name": statement_header(self.church)["name"],
		}
		email = frappe.get_doc("Email Template", EMAIL_TEMPLATE).get_formatted_email(context)
		queued = frappe.sendmail(
			recipients=[self.email],
			subject=email["subject"],
			message=email["message"],
			reference_doctype=self.doctype,
			reference_name=self.name,
			attachments=[
				{
					"print_format_attachment": 1,
					"doctype": self.doctype,
					"name": self.name,
					"print_format": PRINT_FORMAT,
				}
			],
		)
		# The queue drops an address that unsubscribed from all email.
		if not queued:
			return
		make_access_log(doctype=self.doctype, document=self.name, method="Email", file_type="PDF")
		self.db_set({"email": self.email, "emailed_on": now_datetime()})


def get_line_values(lines) -> list[tuple]:
	"""What the *lines* of a statement say, in a fixed order, to tell whether a rebuild changed them."""
	return sorted(
		(
			str(getdate(line.date)),
			line.person or "",
			line.fund or "",
			line.payment_type or "",
			line.check_number or "",
			flt(line.amount),
			line.description or "",
		)
		for line in lines
	)


def get_donations(people, from_date, to_date):
	"""Submitted donations by *people* to tax-deductible funds between the two dates, oldest first."""
	if not people:
		return []

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	Fund = frappe.qb.DocType("Fund")

	query = (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.inner_join(Fund)
		.on(Fund.name == Donation.fund)
		.select(
			Collection.date,
			Donation.person,
			Donation.fund,
			Donation.payment_type,
			Donation.check_number,
			Donation.amount,
			Donation.description,
		)
		.where(
			(Donation.parenttype == "Collection")
			& Donation.person.isin(people)
			& (Fund.is_tax_deductible == 1)
			& (Collection.docstatus == 1)
			& (Collection.date >= from_date)
			& (Collection.date < add_days(to_date, 1))
		)
		.orderby(Collection.date)
	)
	return scoped(query, Collection, {}).run(as_dict=True)


def statement_header(church=None):
	"""Church identity and acknowledgment wording printed on every statement.

	Exposed to templates through the ``jinja`` hook so the statement markup can
	stay free of lookups. A branch without its own legal name or tax id prints
	its parent's, since the parent is then the legal entity issuing the receipt.
	"""
	church = church or root_church()
	if not church:
		return {"name": "", "tax_id": "", "address": "", "acknowledgment": acknowledgment()}

	address = frappe.db.get_value("Church", church, "address")
	return {
		"name": inherited_value(church, "legal_name")
		or frappe.db.get_value("Church", church, "church_name")
		or "",
		"tax_id": inherited_value(church, "tax_id") or "",
		"address": frappe.get_doc("Address", address).get_display() if address else "",
		"acknowledgment": acknowledgment(church),
	}


def acknowledgment(church=None):
	"""The acknowledgment wording for *church*, else the site-wide text."""
	return frappe.get_cached_doc("Giving Settings").get_statement_acknowledgment(church) or ""


def get_givers(from_date, to_date):
	"""Everyone with a submitted donation to a tax-deductible fund in the period, within the issuer's churches.

	Unscoped, a branch issuing statements also issued them for other churches,
	and each landed in the branch's own church: a statement takes its church
	from its person, which a branch cannot read, so it fell back to the issuer's.
	"""
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	Fund = frappe.qb.DocType("Fund")

	query = (
		frappe.qb.from_(Donation)
		.inner_join(Collection)
		.on(Collection.name == Donation.parent)
		.inner_join(Fund)
		.on(Fund.name == Donation.fund)
		.select(Donation.person)
		.distinct()
		.where(
			(Donation.parenttype == "Collection")
			& Donation.person.isnotnull()
			& (Fund.is_tax_deductible == 1)
			& (Collection.docstatus == 1)
			& (Collection.date >= from_date)
			& (Collection.date < add_days(to_date, 1))
		)
	)
	return scoped(query, Collection, {}).run(pluck=True)


def get_statement_recipients(from_date, to_date):
	"""Map every giver in the period onto the record their statement belongs to.

	Returns ``[{"person", "family"}]``, one entry per statement to issue. When
	Giving Settings groups by household, everyone in a Family collapses onto its
	primary contact, or onto the first giver found when it has none.
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
	return frappe.db.get_value("Family", family, "primary_contact") or fallback


@frappe.whitelist(methods=["POST"])
def generate_statements(from_date: str, to_date: str):
	"""Create a statement for every giver in the period. Returns how many were made.

	Re-running is safe: a statement already covering the same period for the same
	recipient is rebuilt rather than duplicated.
	"""
	frappe.only_for(STATEMENT_ROLES)

	created = updated = 0
	for recipient in get_statement_recipients(from_date, to_date):
		# Only the issuer's statements count: another church may have issued its own for this giver.
		existing = frappe.get_list(
			"Giving Statement",
			filters={"person": recipient["person"], "from_date": from_date, "to_date": to_date},
			pluck="name",
			limit=1,
		)
		if existing:
			frappe.get_doc("Giving Statement", existing[0]).save()
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


@frappe.whitelist(methods=["POST"])
def email_statements(from_date: str, to_date: str, resend: bool = False) -> int:
	"""Queue an email of every statement for the period that the user can read. Returns how many.

	The job skips a statement with no email, and one already emailed unless *resend* is set.
	"""
	frappe.only_for(STATEMENT_ROLES)
	if not frappe.db.exists("Email Template", EMAIL_TEMPLATE):
		frappe.throw(
			_("Statement emails use the Email Template {0}, which this site does not have.").format(
				EMAIL_TEMPLATE
			)
		)

	EmailAccount.find_outgoing(_raise_error=True)

	names = frappe.get_list(
		"Giving Statement", filters={"from_date": from_date, "to_date": to_date}, pluck="name"
	)
	if names:
		frappe.enqueue(
			send_statement_emails,
			queue="long",
			names=names,
			resend=bool(sbool(resend)),
			enqueue_after_commit=True,
		)
	return len(names)


def send_statement_emails(names: list[str], resend: bool = False):
	"""Email each of *names* whose person has an address now, and commit after each, so a rerun sends each statement once."""
	for name in names:
		# A second run waits here, then finds emailed_on set.
		statement = frappe.get_doc("Giving Statement", name, for_update=True)
		# The person may have changed or removed the address since the statement was built.
		statement.set_email()
		if statement.email and (resend or not statement.emailed_on):
			statement.send_by_email()
		frappe.db.commit()
