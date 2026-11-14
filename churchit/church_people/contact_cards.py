# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Contact verification cards: what a card shows for one person, and what a returned card changes.

The printed card (ContactVerification.get_cards) and the Returned Card dialog both read get_details,
the person's details for the items the Contact Verification ticks. record_returned_card takes the
dialog's copy of those details as the person corrected them on paper and saves the differences through
the Person save, and the Family save for a household address, so the contact table checks, sharing and
church rules apply as on the form. It records the text message answer as a Communication Consent and
stamps Contact Verified On.
"""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, formatdate, get_datetime, get_url_to_form, getdate, now_datetime, today
from frappe.utils.print_format_generator import get_qr_code

from churchit.church_communications.consent import latest_statuses
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	GIVEN,
	PAPER_FORM,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_people.derived import BIRTH
from churchit.church_people.details_link import get_details_url
from churchit.church_people.imports.record import ADDRESS_COLUMNS, get_contact_type
from churchit.contacts import (
	ADDRESS_DOCTYPE,
	ADDRESS_FIELD,
	DEFAULT_ADDRESS_TYPE,
	DEFAULT_PHONE_TYPE,
	EMAIL_DOCTYPE,
	EMAIL_FIELD,
	PHONE_DOCTYPE,
	PHONE_FIELD,
	get_other_holder,
)

VERIFICATION = "Contact Verification"
NOT_RETURNED = "Not Returned"
CONFIRMED = "Confirmed"
UPDATED = "Updated"
ANSWERED_ONLINE = "Answered Online"
RETURNED = (CONFIRMED, UPDATED, ANSWERED_ONLINE)
YES = "Yes"
NO = "No"
EMERGENCY_FIELDS = ("emergency_contact_name", "emergency_contact_phone")
# The Contact Verification check that shows each item on the cards.
SHOWN_BY = {
	"emails": "show_emails",
	"phones": "show_phones",
	"addresses": "show_addresses",
	"birthday": "show_birthday",
	"anniversary": "show_anniversary",
	"emergency_contact": "show_emergency_contact",
	"texting": "show_texting",
}
# A half page holds about ten lines, so a card shows at most this many of each.
MOST_ON_A_CARD = {"emails": 2, "phones": 3, "addresses": 2}
# An address on the card is one already on file only when every line matches, so a corrected state counts.
ADDRESS_KEY_COLUMNS = ("address_line1", "address_line2", "city", "state", "pincode", "country")
STALE = "This person changed since the card was opened. Close the card and record it again."


def get_shown(verification: Document) -> set[str]:
	"""The items that *verification*'s cards show."""
	return {item for item, check in SHOWN_BY.items() if verification.get(check)}


def get_details(verification: Document, person: Document) -> dict:
	"""*person*'s details for each item that *verification* shows, as the Returned Card dialog edits them."""
	shown = get_shown(verification)
	details = {"person": person.name, "full_name": person.full_name, "shown": sorted(shown)}
	if "emails" in shown:
		details["emails"] = [
			{"row": row.name, "email_address": row.email_address, "is_primary": row.is_primary}
			for row in person.get(EMAIL_FIELD)
		]
	if "phones" in shown:
		details["phones"] = [
			{
				"row": row.name,
				"phone_number": row.phone_number,
				"phone_type": row.phone_type,
				"is_primary": row.is_primary,
			}
			for row in person.get(PHONE_FIELD)
		]
	if "addresses" in shown:
		holder = get_address_holder(person)
		details["address_holder"] = holder.doctype
		details["address_holder_modified"] = str(holder.modified)
		details["addresses"] = get_address_rows(holder)
	if "birthday" in shown:
		birth = get_birth(person)
		details["birthday"] = birth.date if birth else None
		details["birthday_year_unknown"] = birth.year_unknown if birth and birth.date else 0
	if "anniversary" in shown:
		details["anniversary"] = person.anniversary
	if "emergency_contact" in shown and can_read_emergency_contact(person):
		details.update({field: person.get(field) for field in EMERGENCY_FIELDS})
	if "texting" in shown:
		status = latest_statuses([person.name], SMS).get(person.name)
		details["texting"] = {GIVEN: YES, WITHDRAWN: NO}.get(status, "")
	return details


def can_read_emergency_contact(person: Document) -> bool:
	level = frappe.get_meta("Person").get_field("emergency_contact_name").permlevel
	return level in person.get_permlevel_access("read")


def get_address_holder(person: Document) -> Document:
	"""*person*, or their Family when only the household holds an address the reader may see."""
	if person.get(ADDRESS_FIELD) or not person.family:
		return person
	family = frappe.get_doc("Family", person.family)
	return family if family.get(ADDRESS_FIELD) and family.has_permission("read") else person


def get_address_rows(holder: Document) -> list[dict]:
	"""The addresses of *holder*'s table, each with its Address fields."""
	rows = holder.get(ADDRESS_FIELD)
	addresses = frappe.get_list(
		"Address",
		filters={"name": ("in", [row.address for row in rows])},
		fields=["name", *ADDRESS_COLUMNS],
		limit_page_length=0,
	)
	by_name = {address.name: address for address in addresses}
	return [
		{
			"row": row.name,
			"address": row.address,
			**{column: by_name.get(row.address, {}).get(column) for column in ADDRESS_COLUMNS},
			"is_primary": row.is_primary,
			"is_mailing_address": row.is_mailing_address,
		}
		for row in rows
	]


def get_address_key(address: dict) -> tuple:
	"""*address*'s lines for comparing, with the site's country when it names none."""
	values = {**address, "country": address.get("country") or frappe.db.get_default("country")}
	return tuple(cstr(values.get(column)).strip().lower() for column in ADDRESS_KEY_COLUMNS)


def get_birth(person: Document):
	"""The person's Birth life event, with or without a date (a person is born once), or None."""
	return next((row for row in person.life_events if row.event_type == BIRTH), None)


def get_printed_card(verification: Document, person: Document, online_link: str | None = None) -> dict:
	"""What *person*'s card prints: name, QR codes, one line for each detail and lines to add more. The
	office QR code opens the card in the desk; *online_link* is the person's Update Your Details link."""
	details = get_details(verification, person)
	url = get_url_to_form(VERIFICATION, verification.name) + "?" + urlencode({"person": person.name})
	lines, adds = [], []
	for item in ("emails", "phones", "addresses"):
		if item not in details:
			continue
		rows = details[item]
		lines += [get_contact_line(item, row, details, len(rows)) for row in get_printed_rows(details, item)]
		if rows:
			adds.append(get_add_line(item))
		else:
			lines.append(get_blank_line(item))
	lines += get_date_lines(details)
	if "emergency_contact_name" in details:
		value = " ".join(filter(None, (details[field] for field in EMERGENCY_FIELDS))) or None
		lines.append(get_line(_("Emergency Contact"), value, hint=_("Name and phone:")))
	return {
		"person": person.name,
		"full_name": person.full_name,
		"photo": person.photo if verification.show_photo else None,
		"qr_code": get_qr_code(url),
		"online_qr_code": get_qr_code(online_link) if online_link else None,
		"lines": lines,
		"adds": adds,
		"asks_texting": "texting" in details,
	}


def get_printed_rows(details: dict, item: str) -> list[dict]:
	"""The rows of *item* that a card has room for."""
	return details.get(item, [])[: MOST_ON_A_CARD[item]]


def get_line(label: str, value: str | None, note: str | None = None, hint: str | None = None) -> dict:
	"""A card line: a value to tick Right or Wrong, or a blank to fill in with *hint* above it."""
	return {"label": label, "value": value, "note": note, "hint": None if value else hint}


def get_contact_line(item: str, row: dict, details: dict, count: int) -> dict:
	main = _("Main") if row["is_primary"] and count > 1 else None
	if item == "emails":
		return get_line(_("Email"), row["email_address"], main)
	if item == "phones":
		label = _("{0} Phone").format(_(row["phone_type"])) if row["phone_type"] else _("Phone")
		return get_line(label, row["phone_number"], main)
	return get_line(_("Address"), get_address_text(row), get_address_note(row, details["address_holder"]))


def get_address_text(row: dict) -> str:
	place = " ".join(filter(None, (row.get("state"), row.get("pincode"))))
	return ", ".join(
		filter(None, (row.get("address_line1"), row.get("address_line2"), row.get("city"), place))
	)


def get_address_note(row: dict, holder: str) -> str:
	uses = {
		(1, 1): _("Home and mailing address"),
		(1, 0): _("Home address"),
		(0, 1): _("Mailing address"),
	}.get((cint(row["is_primary"]), cint(row["is_mailing_address"])), "")
	if holder == "Family":
		return _("{0}, shared with the household").format(uses or _("Address"))
	return uses or None


def get_blank_line(item: str) -> dict:
	label, hint = {
		"emails": (_("Email"), _("We have none. Write yours here:")),
		"phones": (_("Phone"), _("We have none. Write yours here:")),
		"addresses": (_("Address"), _("Street, city, state and ZIP code:")),
	}[item]
	return get_line(label, None, hint=hint)


def get_add_line(item: str) -> dict:
	"""A line to write one more of *item*, with the boxes that say how to use it."""
	label, ticks = {
		"emails": (_("Another email"), [_("Make it my main email")]),
		"phones": (_("Another phone"), [_("Cell"), _("Home"), _("Main")]),
		"addresses": (_("Another address"), [_("Home"), _("Mailing")]),
	}[item]
	return {"label": label, "ticks": ticks}


def get_date_lines(details: dict) -> list[dict]:
	lines = []
	if "birthday" in details:
		value = details["birthday"] and format_day(details["birthday"], not details["birthday_year_unknown"])
		lines.append(get_line(_("Birthday"), value, hint=_("Month and day:")))
	if "anniversary" in details:
		value = details["anniversary"] and format_day(details["anniversary"], True)
		lines.append(get_line(_("Anniversary"), value, hint=_("Wedding date, if married:")))
	return lines


def format_day(day, with_year: bool) -> str:
	return formatdate(day, "MMMM d, y" if with_year else "MMMM d")


def forget_card_photos(person: str) -> None:
	"""Delete the photos of *person*'s returned cards, which show their handwriting and details."""
	# church-scope: every card of the one person being anonymized, whichever church holds it
	rows = frappe.get_all(
		"Contact Verification Person",
		filters={"person": person, "card_photo": ("is", "set")},
		fields=["name", "parent", "card_photo"],
	)
	for row in rows:
		attached = {"attached_to_doctype": VERIFICATION, "attached_to_name": row.parent}
		files = frappe.get_all("File", filters={"file_url": row.card_photo, **attached}, pluck="name")
		frappe.db.set_value(
			"Contact Verification Person", row.name, "card_photo", None, update_modified=False
		)
		for file in files:
			frappe.delete_doc("File", file, ignore_permissions=True, delete_permanently=True)


def get_online_link(request: str | None) -> str | None:
	"""The Update Your Details URL of a card's link, or None when it has none, it was used or it ended."""
	if not request:
		return None
	values = frappe.db.get_value("Web Form Request", request, ["first_used_on", "expires_on"], as_dict=True)
	if not values or values.first_used_on or (values.expires_on and values.expires_on < now_datetime()):
		return None
	return get_details_url(frappe.get_doc("Web Form Request", request))


def mark_answered_online(request: Document, method=None) -> None:
	"""on_update of Web Form Request: when a card's link is first used, mark its card Answered Online and
	stamp the person's Contact Verified On. The person saved Update Your Details, often as a guest with the
	link's key, so the Contact Verification is saved without a permission check."""
	if not request.first_used_on or not request.has_value_changed("first_used_on"):
		return
	# church-scope: the cards that carry this one link, whichever church printed them
	parents = frappe.get_all(
		"Contact Verification Person", filters={"details_request": request.name}, pluck="parent"
	)
	today_date = getdate(today())
	for parent in set(parents):
		record = frappe.get_doc(VERIFICATION, parent, for_update=True)
		for row in record.people:
			if row.details_request == request.name and row.status == NOT_RETURNED:
				row.update({"status": ANSWERED_ONLINE, "returned_on": today_date})
				stamp_verified_on(row.person, today_date)
		record.save(ignore_permissions=True)


def stamp_verified_on(person: str, day) -> None:
	"""Move *person*'s Contact Verified On forward to *day*, never back."""
	current = frappe.db.get_value("Person", person, "contact_verified_on")
	if not current or getdate(current) < day:
		frappe.db.set_value("Person", person, "contact_verified_on", day, update_modified=False)


@frappe.whitelist(methods=["GET"])
def get_returned_card(verification: str, person: str) -> dict:
	"""The details that *person*'s card on *verification* shows, with the card's status, for the Returned Card dialog. Reads only."""
	record = frappe.get_doc(VERIFICATION, verification)
	record.check_permission("read")
	row = record.get_person_row(person)
	person_doc = frappe.get_doc("Person", person)
	person_doc.check_permission("read")
	return {
		**get_details(record, person_doc),
		"status": row.status,
		"returned_on": row.returned_on,
		"note": row.note,
		"card_photo": row.card_photo,
		"modified": str(person_doc.modified),
	}


@frappe.whitelist(methods=["POST"])
def record_returned_card(verification: str, person: str, card: str | dict) -> str:
	"""Save what a returned contact verification card says and mark the card returned. Changes data.

	*card* is get_returned_card's answer as the person corrected it on paper. A contact row with remove
	set, or with no value, is deleted, and a row without a row name is added. The person's Contact Verified
	On becomes the Returned On date. Returns the card's status: Updated when anything changed, else
	Confirmed.
	"""
	record = frappe.get_doc(VERIFICATION, verification, for_update=True)
	record.check_permission("write")
	row = record.get_person_row(person)
	person_doc = frappe.get_doc("Person", person)
	person_doc.check_permission("write")
	returned = ReturnedCard(record, person_doc, frappe.parse_json(card))
	returned.save()
	row.update(
		{
			"status": UPDATED if returned.has_changes else CONFIRMED,
			"returned_on": returned.returned_on,
			"note": cstr(returned.card.get("note")).strip() or None,
			"card_photo": returned.card_photo or row.card_photo,
		}
	)
	record.save()
	return row.status


class ReturnedCard:
	"""One returned card applied to its person: the corrected details, the text answer and the date."""

	def __init__(self, verification: Document, person: Document, card: dict):
		self.verification = verification
		self.person = person
		self.card = frappe._dict(card)
		self.shown = get_shown(verification)
		self.returned_on = getdate(self.card.get("returned_on") or today())
		self.card_photo = self.get_card_photo()
		self.has_changes = False

	def save(self) -> None:
		if cstr(self.card.get("modified")) != str(self.person.modified):
			frappe.throw(_(STALE))
		if self.returned_on > getdate(today()):
			frappe.throw(_("Returned On cannot be in the future."))
		if "emails" in self.shown:
			self.apply_contacts(self.person, EMAIL_FIELD, EMAIL_DOCTYPE, "email_address", ())
		if "phones" in self.shown:
			self.apply_contacts(self.person, PHONE_FIELD, PHONE_DOCTYPE, "phone_number", ("phone_type",))
		if "addresses" in self.shown:
			self.apply_addresses()
		self.apply_person_fields()
		self.record_texting()
		if not self.person.contact_verified_on or getdate(self.person.contact_verified_on) < self.returned_on:
			self.person.contact_verified_on = self.returned_on
		self.person.save()

	def get_card_photo(self) -> str | None:
		"""The card's photo: a private File attached to the Contact Verification, or None."""
		url = self.card.get("card_photo")
		if not url:
			return None
		attached = {"attached_to_doctype": VERIFICATION, "attached_to_name": self.verification.name}
		if not frappe.db.exists("File", {"file_url": url, "is_private": 1, **attached}):
			frappe.throw(_("Attach the card photo to this Contact Verification as a private file."))
		return url

	def get_sent_rows(self, doc: Document, fieldname: str) -> list[dict]:
		"""The card's rows for *fieldname*, each naming a row *doc* still has or none; every saved row
		must be on the card, so a person changed meanwhile is never overwritten."""
		sent = self.card.get(fieldname)
		if not isinstance(sent, list):
			frappe.throw(_(STALE))
		names = [item.get("row") for item in sent if item.get("row")]
		if sorted(names) != sorted(row.name for row in doc.get(fieldname)):
			frappe.throw(_(STALE))
		return sent

	def apply_contacts(
		self, doc: Document, fieldname: str, child_doctype: str, value_field: str, extra: tuple
	):
		"""Make *doc*'s emails or phones what the card says, keeping each kept row's other columns."""
		saved = {row.name: row for row in doc.get(fieldname)}
		rows = []
		for item in self.get_sent_rows(doc, fieldname):
			value = cstr(item.get(value_field)).strip()
			row = saved.get(item.get("row"))
			if item.get("remove") or not value:
				self.has_changes |= row is not None
				continue
			if row is None:
				row = frappe.new_doc(child_doctype, parent_doc=doc, parentfield=fieldname)
			values = {value_field: value, "is_primary": cint(item.get("is_primary"))}
			values.update({field: item.get(field) or row.get(field) for field in extra})
			if child_doctype == PHONE_DOCTYPE and not values["phone_type"]:
				values["phone_type"] = get_contact_type(PHONE_DOCTYPE, "phone_type", DEFAULT_PHONE_TYPE)
			if row.get(value_field) != value:
				values["shared_from_type"] = doc.doctype
				values["shared_from"] = self.get_household_holder(child_doctype, value_field, value)
			self.has_changes |= any(cstr(row.get(field)) != cstr(new) for field, new in values.items())
			row.update(values)
			rows.append(row)
		doc.set(fieldname, rows)

	def get_household_holder(self, child_doctype: str, value_field: str, value: str) -> str | None:
		"""The member of the person's household who already holds *value*, which the person then shares.

		Anyone else who holds it is left for validate_contact_tables to refuse, as the form does, so a
		misread value never becomes another household's email or phone.
		"""
		holder = get_other_holder(self.person, child_doctype, value_field, value)
		family = self.person.family
		return (
			holder
			if holder and family and frappe.db.get_value("Person", holder, "family") == family
			else None
		)

	def apply_addresses(self) -> None:
		"""Make the person's addresses, or their household's, what the card says."""
		holder = get_address_holder(self.person)
		if (holder.doctype, str(holder.modified)) != (
			self.card.get("address_holder"),
			cstr(self.card.get("address_holder_modified")),
		):
			frappe.throw(_(STALE))
		saved = {row.name: row for row in holder.get(ADDRESS_FIELD)}
		known = self.get_known_addresses(holder)
		rows = []
		for item in self.get_sent_rows(holder, ADDRESS_FIELD):
			row = saved.get(item.get("row"))
			if item.get("remove") or not cstr(item.get("address_line1")).strip():
				self.has_changes |= row is not None
				continue
			if row is None:
				row = frappe.new_doc(ADDRESS_DOCTYPE, parent_doc=holder, parentfield=ADDRESS_FIELD)
				row.address_type = get_contact_type(ADDRESS_DOCTYPE, "address_type", DEFAULT_ADDRESS_TYPE)
			values = {
				"address": known.get(get_address_key(item)) or self.make_address(holder, item),
				"is_primary": cint(item.get("is_primary")),
				"is_mailing_address": cint(item.get("is_mailing_address")),
			}
			self.has_changes |= any(cstr(row.get(field)) != cstr(new) for field, new in values.items())
			row.update(values)
			rows.append(row)
		holder.set(ADDRESS_FIELD, rows)
		if holder.doctype == "Family":
			holder.check_permission("write")
			holder.save()

	def get_known_addresses(self, holder: Document) -> dict[tuple, str]:
		"""The Addresses of *holder* and of the person's household by address_key, so a card that names
		one of them reuses it instead of adding a copy."""
		holders = [holder]
		if holder.doctype == "Person" and holder.family:
			holders.append(frappe.get_doc("Family", holder.family))
		return {get_address_key(row): row["address"] for each in holders for row in get_address_rows(each)}

	def make_address(self, holder: Document, item: dict) -> str:
		"""A new Address with the card's lines, titled like the household or the person."""
		values = {column: cstr(item.get(column)).strip() or None for column in ADDRESS_COLUMNS}
		values["country"] = values["country"] or frappe.db.get_default("country")
		title = holder.family_name if holder.doctype == "Family" else self.person.full_name
		return (
			frappe.get_doc(
				{"doctype": "Address", "address_title": title, "address_type": "Personal", **values}
			)
			.insert()
			.name
		)

	def apply_person_fields(self) -> None:
		if "birthday" in self.shown:
			self.apply_birthday()
		fields = []
		if "anniversary" in self.shown:
			fields.append("anniversary")
		if "emergency_contact" in self.shown and "emergency_contact_name" in self.card:
			fields += EMERGENCY_FIELDS
		for field in fields:
			value = cstr(self.card.get(field)).strip() or None
			if cstr(self.person.get(field)) != cstr(value):
				self.person.set(field, value)
				self.has_changes = True

	def apply_birthday(self) -> None:
		"""Give the person's Birth life event the card's date: add the event when needed, or clear its date."""
		day = getdate(self.card.birthday) if self.card.get("birthday") else None
		year_unknown = cint(self.card.get("birthday_year_unknown")) if day else 0
		birth = get_birth(self.person)
		if not day:
			if birth and birth.date:
				birth.update({"date": None, "year_unknown": 0})
				self.has_changes = True
			return
		if birth and birth.date and getdate(birth.date) == day and cint(birth.year_unknown) == year_unknown:
			return
		birth = birth or self.person.append("life_events", {"event_type": BIRTH})
		birth.update({"date": day, "year_unknown": year_unknown})
		self.has_changes = True

	def record_texting(self) -> None:
		"""Record the card's Yes or No to text messages as a consent from a paper form, when it is new."""
		answer = self.card.get("texting")
		if "texting" not in self.shown or answer not in (YES, NO):
			return
		status = GIVEN if answer == YES else WITHDRAWN
		if latest_statuses([self.person.name], SMS).get(self.person.name) == status:
			return
		frappe.has_permission("Communication Consent", "create", throw=True)
		when = now_datetime() if self.returned_on == getdate(today()) else get_datetime(self.returned_on)
		record([self.person.name], SMS, status, method=PAPER_FORM, recorded_on=when)
		self.has_changes = True
