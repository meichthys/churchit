# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_scope import has_church_access
from churchit.contacts import ADDRESS_DOCTYPE, EMAIL_DOCTYPE, PHONE_DOCTYPE

COMPARED_FIELDS = (
	"full_name",
	"nickname",
	"birth_date",
	"gender",
	"family",
	"membership",
	"membership_status",
	"church",
	"last_attended_on",
	"creation",
)
ADDRESS_FIELDS = ("address_line1", "address_line2", "city", "state", "pincode")


class PossibleDuplicate(Document):
	def validate(self):
		# One record per pair, whichever person the matcher started from. Names are fetched before validate.
		if self.other_person < self.person:
			self.person, self.other_person = self.other_person, self.person
			self.person_name, self.other_person_name = self.other_person_name, self.person_name
		self.refuse_moving_to_another_church()

	def refuse_moving_to_another_church(self):
		"""A pair whose people change stays in the user's churches, as stored and as saved.

		Only matching opens pairs, with ignore_permissions. The people are read-only in the form only, and
		the pair takes its church from `person` after Frappe checked the write right on the pair as the
		caller sent it.
		"""
		if self.flags.ignore_permissions or not (
			self.has_value_changed("person") or self.has_value_changed("other_person")
		):
			return
		before = self.get_doc_before_save()
		if before and not has_church_access(frappe.session.user, before.church):
			frappe.throw(_("This pair belongs to another church."), frappe.PermissionError)
		if not has_church_access(frappe.session.user, self.church):
			frappe.throw(_("This pair would belong to another church."), frappe.PermissionError)

	def onload(self):
		self.set_onload("people", get_comparison([self.person, self.other_person]))


def get_comparison(people: list[str]) -> dict[str, dict]:
	"""The details the form shows side by side, by person, for the people the user may read."""
	rows = frappe.get_list("Person", filters={"name": ("in", people)}, fields=["name", *COMPARED_FIELDS])
	readable = [row.name for row in rows]
	families = dict(
		frappe.get_list(
			"Family",
			filters={"name": ("in", [row.family for row in rows if row.family])},
			fields=["name", "family_name"],
			as_list=True,
		)
	)
	emails = get_contact_values(EMAIL_DOCTYPE, "email_address", readable)
	phones = get_contact_values(PHONE_DOCTYPE, "phone_number", readable)
	addresses = get_addresses(readable)
	return {
		row.name: {
			**row,
			"family_name": families.get(row.family),
			"emails": emails.get(row.name, []),
			"phones": phones.get(row.name, []),
			"addresses": addresses.get(row.name, []),
		}
		for row in rows
	}


def get_contact_values(child_doctype: str, value_field: str, people: list[str]) -> dict[str, list[str]]:
	values: dict[str, list[str]] = {}
	if not people:
		return values
	for row in frappe.get_all(
		child_doctype,
		filters={"parenttype": "Person", "parent": ("in", people)},
		fields=["parent", value_field],
		order_by="idx asc",
	):
		values.setdefault(row.parent, []).append(row[value_field])
	return values


def get_addresses(people: list[str]) -> dict[str, list[str]]:
	"""Each person's addresses on one line each, marked when mail sent there came back."""
	if not people:
		return {}
	rows = frappe.get_all(
		ADDRESS_DOCTYPE,
		filters={"parenttype": "Person", "parent": ("in", people)},
		fields=["parent", "address", "is_returned_mail"],
		order_by="idx asc",
	)
	lines = {
		address.name: ", ".join(filter(None, (address.get(field) for field in ADDRESS_FIELDS)))
		for address in frappe.get_all(
			"Address",
			filters={"name": ("in", [row.address for row in rows])},
			fields=["name", *ADDRESS_FIELDS],
		)
	}
	addresses: dict[str, list[str]] = {}
	for row in rows:
		line = lines.get(row.address) or row.address
		if row.is_returned_mail:
			line = _("{0} (mail returned)").format(line)
		addresses.setdefault(row.parent, []).append(line)
	return addresses
