# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove a person's personal data and keep their record, so their giving and attendance still count.

`anonymize` names the person Anonymized and clears what says who they are: names, contact details, letters,
photo, medical notes, anniversary, skills, how they heard of the church, the login and the IDs of an import.
It also clears the church fields a System Manager added with Customize Form, on the person and on an
anonymized family, because Churchit cannot tell which of them are personal. The login is disabled too, so
signing in cannot add the person again. The person leaves their family and their spouse, and loses each
relationship, on their record and on other people's, because named relatives would say who they are. A family
left with no one in it is anonymized too, since its name and contact details were the person's; a family that
keeps members loses the person's first name from its name.

A Birth life event goes, because a birth date identifies a person. The other life events keep their type and
date, so the number of baptisms or new members in a year stays right, and lose their location and notes.

The records that name the person keep the link and lose the copies of the person's name and email addresses in
their text (titles, fetched names, donor emails). Their notes, connection cards and the pickup restrictions that
protect them as a child are deleted outright, since everything in them is about the person and nothing in them
is counted. The change history, comments and
attachments of the person and of the records about them (`RECORDS_ABOUT_THE_PERSON`) are deleted, because they
hold the old values, and the messages kept on them lose their addresses and text. A record that names the
person in a field of its own also loses the answers kept on it to a Question Set, and its change history
(`clear_answers`). A Function Sign-Up that names the person only as an attendee loses that attendee's answers
and its change history, and the others' answers stay. A sign-up the person made keeps no typed name, email or
phone (`forget_sign_up_details`), and nor does a guest sign-up left unlinked with one of their email addresses.

A member's Personal Data Deletion Request anonymizes their Person once Frappe has deleted their login
(`anonymize_on_data_deletion`).
"""

import re
from collections.abc import Iterable

import frappe
from frappe import _
from frappe.core.doctype.comment.comment import update_comments_in_parent
from frappe.model import no_value_fields, table_fields
from frappe.model.delete_doc import get_linked_docs
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name, get_workflow_state_field
from frappe.query_builder.functions import Coalesce, Lower

from churchit.church_people.derived import BIRTH
from churchit.church_people.doctype.person.person import (
	UNKNOWN_GENDER,
	get_display_name,
	remove_relationships_with,
)
from churchit.church_people.membership import INACTIVE, living_people_filter
from churchit.church_people.person_data_map import LinkedRecord, linked_records
from churchit.contacts import CONTACT_TABLES, UNIQUE_VALUE_FIELDS
from churchit.questions import clear_answers, get_answer_tables

ANONYMIZED = "Anonymized"
# Person fields that say who the person is.
PERSONAL_FIELDS = (
	"last_name",
	"middle_name",
	"nickname",
	"previous_last_name",
	"prefix",
	"suffix",
	"photo",
	"medical_notes",
	"emergency_contact_name",
	"emergency_contact_phone",
	"alergies",
	"anniversary",
	"graduation_year",
	"grade",
	"spouse",
	"marital_status",
	"family",
	"user",
	"team_calendar_key",
	"legacy_system",
	"legacy_id",
	"how_heard",
)
# Person tables whose every row is personal.
PERSONAL_TABLES = ("emails", "phones", "addresses", "letters", "skills", "relationships")
# Records wholly about the person, by the field naming them, deleted rather than kept.
PERSONAL_DOCTYPES = (
	("Person Note", "person"),
	("Connection Card", "person"),
	("Form Response", "person"),
	("Pickup Restriction", "child"),
	("Group Join Request", "person"),
)
# Records about the person that a church keeps, by the field naming them. Their history, comments, attachments
# and messages are about the person, so those go. A field naming someone in a role, such as caregiver, is not.
RECORDS_ABOUT_THE_PERSON = (
	("Alms Request", "requestor"),
	("Background Check", "person"),
	("Care Assignment", "person"),
	("Care Request", "person"),
	("Communication Consent", "person"),
	("Counseling Case", "person"),
	("Follow-up Card", "person"),
	("Function Sign-Up", "person"),
	("Giving Statement", "person"),
	("Member Transfer", "person"),
	("Online Donation", "person"),
	("Pledge", "person"),
	("Prayer Request", "requestor"),
	("Visitation Log", "person"),
)
# What the registrant typed about themselves on a sign-up, which a linked Person makes a copy.
SIGN_UP_REGISTRANT_FIELDS = ("registrant_name", "email", "phone")
# What a message kept on a forgotten record keeps of its address, number and text.
BLANK_MESSAGE = {"recipients": None, "cc": None, "bcc": None, "phone_no": None, "content": ""}
# Field types where a record that names the person can hold a copy of their name or email address.
TEXT_FIELDTYPES = ("Data", "Small Text", "Text", "Long Text", "Text Editor")
MANAGERS = ("Church Manager", "System Manager")


@frappe.whitelist(methods=["POST"])
def anonymize_person(person: str) -> None:
	"""Remove *person*'s personal data, for a Church Manager or System Manager who may change them."""
	frappe.only_for(MANAGERS, message=True)
	frappe.get_doc("Person", person).check_permission("write")
	anonymize(person)


def anonymize(person: str, emails: Iterable[str] = ()) -> None:
	"""Remove *person*'s personal data, and the copies of it on the records that name them; keep the record.

	*emails* adds addresses of the person's that their record may no longer show, such as a deletion request's.
	"""
	doc = frappe.get_doc("Person", person)
	names, own_emails = get_identity(doc)
	emails = own_emails | {email.lower() for email in emails}
	first_name, family = doc.first_name, doc.family
	addresses = [row.address for row in doc.addresses]
	disable_login(doc.user)
	if doc.spouse:
		# The spouse keeps their own marital status and anniversary; only the link to this record goes.
		frappe.db.set_value("Person", {"name": doc.spouse, "spouse": doc.name}, "spouse", None)
	strip_person(doc)
	doc.save(ignore_permissions=True)
	remove_relationships_with(person)
	forget(doc.doctype, doc.name, addresses)
	if family:
		leave_family(family, first_name)
	for child_doctype in UNIQUE_VALUE_FIELDS:
		# Someone who shared this person's email or phone holds it alone from now on.
		frappe.db.set_value(
			child_doctype,
			{"shared_from_type": "Person", "shared_from": person},
			"shared_from",
			None,
			update_modified=False,
		)
	forget_records_about(person)
	forget_sign_up_details(person, emails)
	records = linked_records(person)
	remove_copies(records, names, emails)
	for record in records:
		if get_answer_tables(record.doctype):
			clear_answers(frappe.get_doc(record.doctype, record.name))
	doc.add_comment("Info", _("Personal data removed."))


def disable_login(user: str | None) -> None:
	"""Disable *user*, so that signing in cannot add the person again from the login's name and email."""
	if user and frappe.db.get_value("User", user, "enabled"):
		login = frappe.get_doc("User", user)
		login.enabled = 0
		login.save(ignore_permissions=True)


def forget_records_about(person: str) -> None:
	"""Delete the notes and connection cards about *person*, and forget the history of the others a church keeps.

	Nothing is left in Deleted Documents.
	"""
	# church-scope: every record about the one person being anonymized, whichever church holds it
	for doctype, fieldname in PERSONAL_DOCTYPES:
		for name in frappe.get_all(doctype, filters={fieldname: person}, pluck="name"):
			# A follow-up card it started is forgotten below; unlink it so the delete is not refused.
			frappe.db.set_value(
				"Follow-up Card",
				{"source_type": doctype, "source_name": name},
				{"source_type": None, "source_name": None},
				update_modified=False,
			)
			frappe.delete_doc(doctype, name, ignore_permissions=True, delete_permanently=True)
	for doctype, fieldname in RECORDS_ABOUT_THE_PERSON:
		for name in frappe.get_all(doctype, filters={fieldname: person}, pluck="name"):
			forget(doctype, name)


def forget_sign_up_details(person: str, emails: set[str]) -> None:
	"""Clear what a registrant typed about themselves on *person*'s own sign-ups, and delete the answers given
	for *person* as an attendee of any sign-up, with that sign-up's change history. The others' answers stay.
	"""
	forget_unlinked_sign_ups(emails)
	# church-scope: the sign-ups of the one person being anonymized, whichever church holds them
	frappe.db.set_value(
		"Function Sign-Up",
		{"person": person},
		dict.fromkeys(SIGN_UP_REGISTRANT_FIELDS),
		update_modified=False,
	)
	rows = frappe.get_all(
		"Function Sign-Up Attendee",
		filters={"parenttype": "Function Sign-Up", "person": person},
		fields=["name", "parent"],
	)
	if rows:
		frappe.db.delete(
			"Question Answer",
			{"parenttype": "Function Sign-Up", "attendee": ("in", [row.name for row in rows])},
		)
		frappe.db.delete(
			"Version", {"ref_doctype": "Function Sign-Up", "docname": ("in", [row.parent for row in rows])}
		)


def forget_unlinked_sign_ups(emails: set[str]) -> None:
	"""Forget the guest sign-ups made with one of *emails* and linked to nobody, as the person's own.

	`link_registrant` leaves a sign-up unlinked when the person is already signed up for the function.
	"""
	if not emails:
		return

	SignUp = frappe.qb.DocType("Function Sign-Up")
	# church-scope: the sign-ups of the one person being anonymized, whichever church holds them
	names = (
		frappe.qb.from_(SignUp)
		.select(SignUp.name)
		.where(Coalesce(SignUp.person, "") == "")
		.where(Lower(SignUp.email).isin(list(emails)))
	).run(pluck=True)
	for name in names:
		doc = frappe.get_doc("Function Sign-Up", name)
		for row in doc.attendees:
			if doc.is_registrant_row(row):
				frappe.db.set_value(row.doctype, row.name, "attendee_name", ANONYMIZED, update_modified=False)
		# The title named the typed name, as set_title builds it.
		function_name = frappe.db.get_value("Function", doc.function, "function_name")
		title = " - ".join(part for part in (function_name, ANONYMIZED) if part)
		frappe.db.set_value(
			doc.doctype,
			name,
			{**dict.fromkeys(SIGN_UP_REGISTRANT_FIELDS), "title": title},
			update_modified=False,
		)
		clear_answers(doc)
		forget(doc.doctype, name)


def get_identity(doc: Document) -> tuple[set[str], set[str]]:
	"""The names *doc* goes by and its email addresses, as a copy on another record spells them.

	The names come from the name fields as well as the stored ones, which Frappe's own deletion request may
	have redacted already.
	"""
	names = {
		doc.full_name,
		doc.display_name,
		" ".join(filter(None, (doc.first_name, doc.last_name))),
		get_display_name(doc.first_name, doc.last_name, doc.nickname, doc.suffix),
	}
	emails = {row.email_address.lower() for row in doc.emails if row.email_address}
	return {name for name in names if name and name != ANONYMIZED}, emails


def strip_person(doc: Document) -> None:
	"""Clear what says who *doc* is, keeping the life events and positions a church counts."""
	doc.update({fieldname: None for fieldname in PERSONAL_FIELDS})
	doc.update({"first_name": ANONYMIZED, "gender": UNKNOWN_GENDER, "hide_from_directory": 1})
	for fieldname in PERSONAL_TABLES:
		doc.set(fieldname, [])
	doc.set("life_events", [row for row in doc.life_events if row.event_type != BIRTH])
	for row in doc.life_events:
		row.update({"location": None, "notes": None})
	for row in doc.positions:
		row.notes = None
	blank_church_fields(doc)


def blank_church_fields(doc: Document) -> None:
	"""Clear each field added with Customize Form, mandatory ones too, since any of them may be personal.

	A workflow's state field stays: a blank state is a move back to the first state, which the workflow refuses.
	"""
	workflow = get_workflow_name(doc.doctype)
	state_field = workflow and get_workflow_state_field(workflow)
	for field in doc.meta.get_custom_fields():
		if field.fieldname == state_field:
			continue
		if field.fieldtype in table_fields:
			doc.set(field.fieldname, [])
		elif field.fieldtype not in no_value_fields:
			doc.set(field.fieldname, None)
	doc.flags.ignore_mandatory = True


def leave_family(family: str, first_name: str) -> None:
	"""Anonymize the person's *family* when no one is left in it, else take their *first_name* off its name.

	A household is named after its primary contact, "Doe - John", so the name becomes "Doe".
	"""
	if not frappe.db.exists("Family Members", {"parenttype": "Family", "parent": family}):
		anonymize_family(family)
		return
	surname, dash, named = frappe.db.get_value("Family", family, "family_name").rpartition("-")
	if dash and surname.strip() and named.strip().casefold() == first_name.casefold():
		frappe.db.set_value("Family", family, "family_name", surname.strip())


def anonymize_family(family: str) -> None:
	"""Strip a family left with no one in it, whose name and contact details were its last member's."""
	doc = frappe.get_doc("Family", family)
	addresses = [row.address for row in doc.addresses]
	doc.update({"family_name": ANONYMIZED, "photo": None, "legacy_system": None, "legacy_id": None})
	for fieldname, *_rest in CONTACT_TABLES:
		doc.set(fieldname, [])
	blank_church_fields(doc)
	doc.save(ignore_permissions=True)
	forget(doc.doctype, doc.name, addresses)


def forget(doctype: str, name: str, addresses: Iterable[str] = ()) -> None:
	"""Delete a record's change history, comments and attachments, and each of *addresses* nothing links to now.

	The messages kept on the record lose their addresses and text but stay, so a Church Email still counts its
	copy and never sends it again.
	"""
	attachments = frappe.get_all(
		"File", filters={"attached_to_doctype": doctype, "attached_to_name": name}, pluck="name"
	)
	for file in attachments:
		frappe.delete_doc("File", file, ignore_permissions=True, delete_permanently=True)
	frappe.db.delete("Version", {"ref_doctype": doctype, "docname": name})
	frappe.db.delete("Comment", {"reference_doctype": doctype, "reference_name": name})
	frappe.db.set_value(
		"Communication",
		{"reference_doctype": doctype, "reference_name": name},
		BLANK_MESSAGE,
		update_modified=False,
	)
	# Frappe keeps the start of each comment and message on the record itself, for its list view.
	update_comments_in_parent(doctype, name, [])
	for address in set(addresses):
		if not get_linked_docs(frappe.get_doc("Address", address)):
			frappe.delete_doc("Address", address, ignore_permissions=True, delete_permanently=True)


def remove_copies(records: list[LinkedRecord], names: set[str], emails: set[str]) -> None:
	"""In the text fields of *records*, write Anonymized for each of *names* and remove each of *emails*."""
	replacements = [(re.compile(rf"(?<!\w){re.escape(name)}(?!\w)"), ANONYMIZED) for name in names]
	replacements += [(re.compile(re.escape(email), re.IGNORECASE), "") for email in emails]
	for record in records:
		scrub_record(record, replacements)


def scrub_record(record: LinkedRecord, replacements: list[tuple[re.Pattern, str]]) -> None:
	"""Apply each (pattern, replacement) of *replacements* to the text fields of *record*."""
	fields = [
		df.fieldname
		for df in frappe.get_meta(record.doctype).fields
		if df.fieldtype in TEXT_FIELDTYPES and not df.is_virtual
	]
	values = frappe.db.get_value(record.doctype, record.name, fields, as_dict=True) if fields else {}
	changed = {}
	for fieldname, value in (values or {}).items():
		scrubbed = value
		for pattern, replacement in replacements if value else ():
			scrubbed = pattern.sub(replacement, scrubbed)
		if scrubbed != value:
			changed[fieldname] = scrubbed.strip() or None
	if changed:
		frappe.db.set_value(record.doctype, record.name, changed, update_modified=False)


def anonymize_on_data_deletion(doc: Document, method=None) -> None:
	"""doc_events on_change of Personal Data Deletion Request: anonymize the Person of a deleted login.

	Frappe gives the login the request's name before it marks the request Deleted, and may have redacted the
	address on the person's record by then, so the request's own address is passed on.
	"""
	if doc.status != "Deleted":
		return
	# church-scope: the people of one deleted login, whichever church they belong to
	for person in frappe.get_all("Person", filters={"user": doc.name}, pluck="name"):
		anonymize(person, emails=[doc.email])


# People the daily job anonymizes in one run; the rest wait for the next day.
REMOVALS_PER_RUN = 50


def remove_due_personal_data() -> None:
	"""Daily job: remove the personal data of people Inactive longer than People Settings allows.

	A run takes the longest Inactive first, up to `REMOVALS_PER_RUN`, and commits each person, so a person who
	fails is logged and the others still go.
	"""
	years = get_retention_years()
	if not years:
		return
	Person = frappe.qb.DocType("Person")
	# church-scope: People Settings' rule covers every church's people and shows nobody anything
	query = get_due_query(Person, frappe.utils.add_years(frappe.utils.today(), -years))
	for person, inactive_since in (
		query.select(Person.name, Person.inactive_since).limit(REMOVALS_PER_RUN).run()
	):
		try:
			anonymize(person)
			frappe.get_doc("Person", person).add_comment(
				"Info",
				_("Removed because the person has been Inactive since {0}, {1} years or more.").format(
					frappe.utils.formatdate(inactive_since), years
				),
			)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				_("Could not remove the personal data of {0}").format(person),
				reference_doctype="Person",
				reference_name=person,
			)


def get_retention_years() -> int:
	"""People Settings' years Inactive before personal data is removed; 0 removes nothing."""
	return frappe.utils.cint(frappe.db.get_single_value("People Settings", "remove_inactive_after_years"))


def get_due_query(Person, inactive_by):
	"""Query on *Person* for the living people Inactive since *inactive_by* or before whose data is still there.

	It selects nothing and reads every church: the caller picks the columns and the scope.
	"""
	return (
		frappe.qb.from_(Person)
		.where(
			(Person.membership_status == INACTIVE)
			& (Person.inactive_since <= inactive_by)
			& (Person.first_name != ANONYMIZED)
			& living_people_filter(Person)
		)
		.orderby(Person.inactive_since)
		.orderby(Person.name)
	)
