# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The personal details and preferences pages of the member app."""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from churchit.ai.opt_outs import get_member_ai_state
from churchit.church_communications.preferences import get_member_preferences
from churchit.church_communications.push import get_public_key
from churchit.church_foundations.doctype.church.church import address_line
from churchit.church_people.member_access import (
	PERSONAL_DETAILS,
	PERSONAL_DETAILS_EDITABLE,
	PERSONAL_DETAILS_READ_ONLY,
)
from churchit.church_scope import session_person
from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, search_holders
from churchit.portal.access import require_page, require_person

# The columns of each contact table a member fills in. Bounced and notification address are server state.
CONTACT_COLUMNS = {
	"emails": ("email_address", "email_type", "is_primary", "shared_from"),
	"phones": ("phone_number", "phone_type", "is_primary", "shared_from"),
}
HOLDER_TABLES = {"email": EMAIL_DOCTYPE, "phone": PHONE_DOCTYPE}


def get_form_fields() -> dict[str, bool]:
	"""{fieldname: is_editable} for the fields of the My Details page, the addresses table too."""
	return {
		**dict.fromkeys(PERSONAL_DETAILS_EDITABLE, True),
		**dict.fromkeys(PERSONAL_DETAILS_READ_ONLY, False),
	}


@frappe.whitelist(methods=["GET"])
def get_personal_details(person: str | None = None) -> dict:
	"""The fields of the Personal Details form for *person* (the member by default). Reads only.

	A member reads their own record and the Children of their household they may edit. Only the form's
	fields leave the server, never the whole Person.
	"""
	own = require_person()
	require_page(PERSONAL_DETAILS)
	person = person or own
	frappe.has_permission("Person", "read", doc=person, throw=True)

	doc = frappe.get_doc("Person", person)
	fields = get_form_fields()
	plain = [name for name in fields if name not in CONTACT_COLUMNS and name != "addresses"]
	return {
		"name": doc.name,
		"display_name": doc.display_name,
		"is_you": doc.name == own,
		"modified": str(doc.modified),
		"can_edit": bool(doc.has_permission("write")),
		"fields": [name for name in [*plain, *CONTACT_COLUMNS] if fields.get(name)],
		"values": {name: get_value(doc, name) for name in plain},
		"emails": [get_contact_row(row, "email_address") for row in doc.get("emails")]
		if "emails" in fields
		else [],
		"phones": [get_contact_row(row, "phone_number") for row in doc.get("phones")]
		if "phones" in fields
		else [],
		"addresses": get_address_rows(doc) if "addresses" in fields else [],
		"options": get_options(),
		"notes": {
			"ai_state": get_member_ai_state(doc.church),
			"directory_off": not cint(frappe.db.get_single_value("People Settings", "member_directory")),
		},
	}


def get_value(doc, fieldname: str):
	"""A field of *doc* as plain JSON. A birthday is read from the stored birth date, never the virtual field."""
	value = doc.birth_date if fieldname == "birthday" else doc.get(fieldname)
	return str(value) if hasattr(value, "isoformat") else value


def get_contact_row(row, value_field: str) -> dict:
	"""One email or phone row: its name, the form's columns, and who it is shared from."""
	result = {"name": row.name, "is_bounced": bool(row.get("is_bounced"))}
	for column in CONTACT_COLUMNS["emails" if value_field == "email_address" else "phones"]:
		result[column] = row.get(column)
	if row.shared_from:
		result["shared_from_title"] = frappe.db.get_value("Person", row.shared_from, "display_name")
	return result


def get_address_rows(doc) -> list[dict]:
	"""The member's addresses as text. They are read only: members cannot read Address themselves."""
	rows = []
	for row in doc.get("addresses"):
		address = frappe.db.get_value(
			"Address",
			row.address,
			["address_line1", "address_line2", "city", "state", "pincode"],
			as_dict=True,
		)
		rows.append(
			{
				"name": row.name,
				"text": address_line(address) if address else row.address,
				"address_type": row.address_type,
				"is_mailing_address": bool(row.is_mailing_address),
				"is_primary": bool(row.is_primary),
			}
		)
	return rows


def get_options() -> dict:
	"""The choices for the Select and Link fields: every type."""
	genders = frappe.get_meta("Person").get_field("gender").options.split("\n")
	return {
		"genders": [gender for gender in genders if gender],
		"email_types": frappe.get_all("Email Type", pluck="name", order_by="name"),
		"phone_types": frappe.get_all("Phone Type", pluck="name", order_by="name"),
		"marital_statuses": frappe.get_all("Marital Status", pluck="name", order_by="name"),
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=True)
def save_personal_details(
	person: str,
	modified: str,
	values: dict,
	emails: list | None = None,
	phones: list | None = None,
) -> dict:
	"""Save the form's editable fields of *person*, and return the record as get_personal_details does. Changes data.

	*modified* is the value get_personal_details sent: a record changed since then is refused, so a save
	never undoes an edit made elsewhere. Person.validate keeps its own guards.
	"""
	require_person()
	require_page(PERSONAL_DETAILS)
	doc = frappe.get_doc("Person", person)
	doc.check_permission("write")
	if str(doc.modified) != modified:
		frappe.throw(
			_("This record was changed while you had it open. Reload it, then make your change again."),
			frappe.TimestampMismatchError,
		)

	fields = get_form_fields()
	editable = {name for name, is_editable in fields.items() if is_editable and name not in CONTACT_COLUMNS}
	refused = set(values) - editable
	if refused:
		frappe.throw(
			_("You cannot change {0} here.").format(", ".join(sorted(refused))), frappe.PermissionError
		)

	doc.update(values)
	for fieldname, rows in (("emails", emails), ("phones", phones)):
		if rows is not None and fields.get(fieldname):
			set_contact_rows(doc, fieldname, rows)

	# Person.sync_anniversary_year reads this flag: an anniversary a member types has a known year.
	frappe.flags.in_web_form = True
	try:
		doc.save()
	finally:
		frappe.flags.in_web_form = False
	return get_personal_details(person)


def check_shared_from(target, shared_from: str | None) -> None:
	"""Refuse a new or changed Shared From that names a person the member may not read, as get_holders hides them."""
	if shared_from and shared_from != target.get("shared_from"):
		frappe.has_permission("Person", "read", doc=shared_from, throw=True)


def set_contact_rows(doc, fieldname: str, rows: list[dict]) -> None:
	"""Make *doc*'s email or phone table match *rows*: kept rows by name, new ones added, the rest removed."""
	columns = CONTACT_COLUMNS[fieldname]
	value_field = columns[0]
	existing = {row.name: row for row in doc.get(fieldname)}
	for row in rows:
		if not (row.get(value_field) or "").strip():
			continue

		target = existing.pop(row.get("name"), None) or doc.append(fieldname, {})
		check_shared_from(target, row.get("shared_from"))
		for column in columns:
			target.set(column, row.get(column) or None)
		target.shared_from_type = "Person" if target.shared_from else None
	for leftover in existing.values():
		doc.remove(leftover)


@frappe.whitelist(methods=["GET"])
def get_holders(kind: str, value: str, person: str) -> dict:
	"""The people who already hold the email or phone *value* and whom the member may read, for Shared From. Reads only.

	*kind* is "email" or "phone"; *person* is the record being edited.
	"""
	require_person()
	require_page(PERSONAL_DETAILS)
	frappe.has_permission("Person", "read", doc=person, throw=True)
	if kind not in HOLDER_TABLES:
		frappe.throw(_("Choose email or phone."))

	filters = {"child_doctype": HOLDER_TABLES[kind], "value": value, "parent": person}
	rows = search_holders("Person", "", "name", 0, 20, filters)
	return {"items": [{"name": name, "title": title} for name, title in rows]}


@frappe.whitelist(methods=["GET"])
def get_preferences() -> dict:
	"""How the member may be contacted and what they chose, with the push key for this device. Reads only."""
	require_person()
	require_page("preferences")

	preferences = get_member_preferences()
	return {
		"church_name": preferences.get("church_name"),
		"email": preferences.get("email"),
		"phone": preferences.get("phone"),
		"channels": preferences.get("channels", []),
		"purposes": [
			{"purpose": row.purpose, "description": row.description, "allowed": row.allowed}
			for row in preferences.get("purposes", [])
		],
		"is_globally_unsubscribed": bool(preferences.get("is_globally_unsubscribed")),
		"has_stopped_church_emails": bool(preferences.get("has_stopped_church_emails")),
		"push_public_key": get_public_key(),
		"person": session_person(),
	}
