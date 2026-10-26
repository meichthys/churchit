# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from churchit.church_communications.consent import latest_statuses
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WEB_FORM,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS
from churchit.church_people.derived import BIRTH
from churchit.church_people.doctype.marital_status.marital_status import MARRIED
from churchit.church_people.doctype.person.person import get_display_name
from churchit.church_people.family_relations import ROLE_OF_TYPE, ROLE_TYPES
from churchit.church_people.followup import start_cards
from churchit.church_people.matching import (
	SHARES_NOTHING,
	find_matches,
	find_or_add_person,
	record_possible_duplicates,
)
from churchit.church_people.membership import VISITOR
from churchit.church_scope import is_multi_church
from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, get_holders

NEW = "New"
PROCESSED = "Processed"
SPAM = "Spam"
# The Follow-up Trigger a card starts workflows on, and the Person source of the people it adds.
CONNECTION_CARD = "Connection Card"


class ConnectionCard(Document):
	"""What a guest filled in on the Connection Card web form, and the person Churchit found or added for it."""

	def validate(self):
		self.full_name = get_display_name(self.first_name, self.last_name)
		self.keep_only_a_published_church()

	def after_insert(self):
		frappe.enqueue_doc(self.doctype, self.name, "process", enqueue_after_commit=True)

	def keep_only_a_published_church(self):
		"""Keep the church the web form carried from the page's address only when it names a published church.

		Anyone can type the address, so any other church is dropped and `ensure_church` settles it.
		"""
		if not (self.is_new() and frappe.flags.in_web_form and self.church):
			return
		if not is_multi_church() or not frappe.db.get_value("Church", self.church, "publish"):
			self.church = None

	def process(self):
		"""Background job: link or add the card's person and start their follow-up, once.

		It runs as whoever sent the card, a guest for the web form, so its writes skip permissions.
		"""
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) != NEW:
			return
		if self.website:
			self.db_set("status", SPAM)
			return

		person = self.find_or_add_person()
		self.db_set({"person": person, "status": PROCESSED, "processed_on": now_datetime()})
		self.record_consent(person)
		# A trigger row with no value matches any card, so a card with no interests still starts those.
		for interest in [row.interest for row in self.interests] or [None]:
			start_cards(CONNECTION_CARD, person, self.church, value=interest, source=self)

	def find_or_add_person(self) -> str:
		"""The one person who strongly matches the card, else a new Visitor and their household.

		The matches are left for staff. A card that matched someone adds nobody from its household,
		because guest input never changes an existing person; its rows stay on the card for staff.
		"""
		person, added = find_or_add_person(self.candidate, self.church, CONNECTION_CARD)
		if added:
			self.add_household(frappe.get_doc("Person", person))
		return person

	def record_consent(self, person: str):
		"""Record Church News by email, or by text, for each box ticked beside an address or number.

		Anyone can type a member's name and email, so a tick counts only for an address or number already
		on the person's record, as a new Visitor's are, and never overrides a withdrawal on record.
		"""
		for channel, is_ticked, contact, child_doctype, value_field in (
			(EMAIL, self.email_consent, self.email, EMAIL_DOCTYPE, "email_address"),
			(SMS, self.sms_consent, self.phone, PHONE_DOCTYPE, "phone_number"),
		):
			if (
				is_ticked
				and contact
				and get_holders("Person", child_doctype, value_field, contact, parent=person)
				and latest_statuses([person], channel, CHURCH_NEWS).get(person) != WITHDRAWN
			):
				record([person], channel, GIVEN, CHURCH_NEWS, WEB_FORM)

	@property
	def candidate(self) -> dict:
		"""The card as the matcher reads a person."""
		return {
			"first_name": self.first_name,
			"last_name": self.last_name,
			"emails": [self.email] if self.email else [],
			"phones": [self.phone] if self.phone else [],
		}

	def add_household(self, guest: Document) -> None:
		"""Add the people the guest came with as Visitors, in a new Family with the guest as its primary contact.

		A spouse joins through the marriage link, which names them Husband or Wife. The others join with the
		relationship the guest gave, so the Family works out each household role.
		"""
		if not self.household_members:
			return
		family = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": guest.household_name,
				"primary_contact": guest.name,
				"members": [{"member": guest.name}],
			}
		).insert(ignore_permissions=True)
		relationships = {
			self.add_household_member(row, guest.name): row.relationship for row in self.household_members
		}

		family.reload()
		for person, relationship in relationships.items():
			if person not in family.member_names:
				family.append("members", {"member": person, "relationship_to_primary_contact": relationship})
		family.save(ignore_permissions=True)

	def add_household_member(self, row, guest: str) -> str:
		"""Add one person the guest came with as a Visitor, with the birth date and relationship the guest gave."""
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": row.first_name,
				"last_name": row.last_name or self.last_name,
				"church": self.church,
				"membership": VISITOR,
				"source": CONNECTION_CARD,
				**SHARES_NOTHING,
				"life_events": [{"event_type": BIRTH, "date": row.birth_date}] if row.birth_date else [],
			}
		)
		person.update(get_relationship_values(row.relationship, guest))
		person.insert(ignore_permissions=True)

		candidate = {
			"first_name": person.first_name,
			"last_name": person.last_name,
			"birth_date": row.birth_date,
		}
		record_possible_duplicates(
			person.name, find_matches(candidate, church=self.church, exclude=person.name)
		)
		return person.name


def get_relationship_values(relationship: str | None, guest: str) -> dict:
	"""The Person fields a relationship to the guest settles: the gender it names, and a marriage to the guest."""
	role = ROLE_OF_TYPE.get(relationship)
	if not role:
		return {}
	values = {"spouse": guest, "marital_status": MARRIED} if role == "spouse" else {}
	male, female = ROLE_TYPES[role]
	if male != female:
		values["gender"] = "Male" if relationship == male else "Female"
	return values
