# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, get_datetime, now_datetime

from churchit.church_people.contact_cards import (
	NOT_RETURNED,
	RETURNED,
	SHOWN_BY,
	get_online_link,
	get_printed_card,
)
from churchit.church_people.details_link import make_details_request
from churchit.church_scope import default_church, document_church, is_multi_church

IN_PROGRESS = "In Progress"
COMPLETED = "Completed"
PRIVATE_FILES = "/private/files/"
# How long a card's Update Your Details link works after Handed Out On.
CARD_LINK_DAYS = 30


class ContactVerification(Document):
	"""A set of paper cards that ask people to check their contact information, and which cards came back."""

	def validate(self):
		self.add_group_members()
		self.refuse_people_listed_twice()
		self.refuse_another_churches_people()
		self.refuse_public_card_photos()
		self.keep_what_returned_cards_showed()
		self.make_online_links()
		self.set_counts()

	def add_group_members(self) -> None:
		"""Add the living members of a newly picked Group who are not listed yet."""
		if not self.group or not (self.is_new() or self.has_value_changed("group")):
			return
		group = frappe.get_doc("Group", self.group)
		group.check_permission("read")
		members = [row.person for row in group.members]
		listed = {row.person for row in self.people}
		for person in get_living_people(members):
			if person not in listed:
				self.append("people", {"person": person, "status": NOT_RETURNED})

	def refuse_people_listed_twice(self) -> None:
		seen = set()
		for row in self.people:
			if row.person in seen:
				frappe.throw(_("Row {0}: {1} is on the list twice.").format(row.idx, frappe.bold(row.person)))
			seen.add(row.person)

	def refuse_another_churches_people(self) -> None:
		"""The cards carry this church's name and only its staff record them, so each person added must be
		one of its people. Rows saved before are left alone, so a merge that renames a person still saves."""
		before = self.get_doc_before_save()
		saved = {(row.name, row.person) for row in before.people} if before else set()
		added = [row.person for row in self.people if (row.name, row.person) not in saved]
		if not added or not is_multi_church():
			return
		own_church = document_church(self) or default_church()
		# church-scope: comparing each added person's church with this verification's own
		rows = frappe.get_all("Person", filters={"name": ("in", added)}, fields=["full_name", "church"])
		others = sorted(row.full_name for row in rows if row.church != own_church)
		if others:
			frappe.throw(_("These people belong to another church: {0}.").format(", ".join(others)))

	def keep_what_returned_cards_showed(self) -> None:
		"""Refuse a change to what the cards show once a card came back: the cards in people's hands show
		the old items, and the Returned Card dialog must show the same ones."""
		before = self.get_doc_before_save()
		if not before or not any(row.status in RETURNED for row in before.people):
			return
		if any(self.has_value_changed(check) for check in SHOWN_BY.values()):
			frappe.throw(
				_(
					"Cards have come back already, so what the cards show cannot change. Make a new Contact Verification instead."
				)
			)

	def refuse_public_card_photos(self) -> None:
		for row in self.people:
			if row.card_photo and not row.card_photo.startswith(PRIVATE_FILES):
				frappe.throw(_("Row {0}: upload the card photo as a private file.").format(row.idx))

	def set_counts(self) -> None:
		self.card_count = len(self.people)
		self.returned_count = sum(row.status in RETURNED for row in self.people)
		self.status = COMPLETED if self.card_count and self.returned_count == self.card_count else IN_PROGRESS

	def make_online_links(self) -> None:
		"""Give each card not returned yet a one-time Update Your Details link that works CARD_LINK_DAYS
		after Handed Out On. A new date moves the end of the unused links, and unticking the box ends them."""
		expires_on = add_days(self.handed_out_on, CARD_LINK_DAYS) if self.show_online_link else now_datetime()
		is_moved = not self.is_new() and (
			self.has_value_changed("handed_out_on") or self.has_value_changed("show_online_link")
		)
		for row in self.people:
			if row.details_request and is_moved:
				set_link_end(row.details_request, expires_on)
			elif not row.details_request and self.show_online_link and row.status == NOT_RETURNED:
				frappe.get_doc("Person", row.person).check_permission("write")
				row.details_request = make_details_request(row.person, expires_on).name

	def get_person_row(self, person: str) -> Document:
		"""The row of *person*, who must be on this Contact Verification."""
		row = next((row for row in self.people if row.person == person), None)
		if not row:
			frappe.throw(_("{0} has no card on this Contact Verification.").format(frappe.bold(person)))
		return row

	def get_cards(self) -> list[dict]:
		"""The cards to print, in list order: the living people the reader may see, and only those whose
		card has not come back when Print Only Cards Not Returned is ticked."""
		rows = [row for row in self.people if not (self.print_only_not_returned and row.status in RETURNED)]
		readable = set(get_living_people([row.person for row in rows]))
		return [
			get_printed_card(
				self,
				frappe.get_doc("Person", row.person),
				get_online_link(row.details_request) if self.show_online_link else None,
			)
			for row in rows
			if row.person in readable
		]


def set_link_end(request: str, expires_on) -> None:
	"""End an unused card link on *expires_on*. A used link stays closed."""
	# Only a Website Manager writes a Web Form Request; the caller changes the Contact Verification it belongs to.
	if not frappe.db.get_value("Web Form Request", request, "first_used_on"):
		frappe.db.set_value("Web Form Request", request, "expires_on", get_datetime(expires_on))


def get_living_people(people: list[str]) -> list[str]:
	"""Those of *people* who have not died, that the reader may see, in no particular order."""
	if not people:
		return []
	return frappe.get_list(
		"Person",
		filters={"name": ("in", people), "is_deceased": 0},
		pluck="name",
		limit_page_length=0,
	)
