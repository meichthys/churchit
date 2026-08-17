# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

"""Shared helpers for the multi-value contact tables.

Person, Family and Missionary each carry the same three child tables:

    emails     -> Email Address    (email_address, email_type, is_primary)
    phones     -> Phone Number     (phone_number, phone_type, is_primary)
    addresses  -> Postal Address   (address, address_type, is_mailing_address, is_primary)

Nothing is copied back onto the parent, so "the" email / phone / address for a
record is always resolved through this module: from a loaded document
(:func:`pick`), with a lookup (:func:`get_primary_email` and friends), or
inside a report query (:func:`primary_email_sql` and friends).

The type of a contact row ("Home", "Work", ...) is a link to a user-editable
lookup doctype, so no code in this app may branch on a specific type name.
Which row the church actually uses is carried by the ``is_primary`` flag. For
addresses only, ``is_mailing_address`` says where paper mail goes.
"""

import frappe
from frappe import _

# Parent fieldname -> child doctype
EMAIL_FIELD = "emails"
PHONE_FIELD = "phones"
ADDRESS_FIELD = "addresses"

EMAIL_DOCTYPE = "Email Address"
PHONE_DOCTYPE = "Phone Number"
ADDRESS_DOCTYPE = "Postal Address"

# Doctypes that carry the contact tables. Used to bound the parenttype that can
# reach the SQL builders below.
CONTACT_PARENTS = ("Person", "Family", "Missionary")

# (parent fieldname, child doctype, value fieldname, label) for the three tables
CONTACT_TABLES = (
	(EMAIL_FIELD, EMAIL_DOCTYPE, "email_address", "email address"),
	(PHONE_FIELD, PHONE_DOCTYPE, "phone_number", "phone number"),
	(ADDRESS_FIELD, ADDRESS_DOCTYPE, "address", "address"),
)


# Sane starting points for the three type lookups. Churches are free to rename,
# delete or add to these, because nothing in this app matches on a type name.
DEFAULT_EMAIL_TYPES = ("Home", "Work", "Other")
DEFAULT_PHONE_TYPES = ("Mobile", "Home", "Work", "Other")
DEFAULT_ADDRESS_TYPES = ("Home", "Work", "Other")

# Types the field defaults point at. Kept in sync with the ``default`` on the
# child doctypes, and used by the migration patch to classify existing data.
DEFAULT_EMAIL_TYPE = "Home"
DEFAULT_PHONE_TYPE = "Mobile"
DEFAULT_ADDRESS_TYPE = "Home"
OTHER_ADDRESS_TYPE = "Other"


def create_default_contact_types():
	"""Seed the Email / Phone / Address Type lookups. Safe to re-run."""
	for doctype, defaults in (
		("Email Type", DEFAULT_EMAIL_TYPES),
		("Phone Type", DEFAULT_PHONE_TYPES),
		("Address Type", DEFAULT_ADDRESS_TYPES),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		for type_name in defaults:
			if not frappe.db.exists(doctype, type_name):
				frappe.get_doc({"doctype": doctype, "type": type_name}).insert(
					ignore_permissions=True
				)


# ---------------------------------------------------------------------------
# Reading from a loaded document
# ---------------------------------------------------------------------------


def pick(rows, fieldname, flag="is_primary"):
	"""Return *fieldname* from the row flagged *flag*, falling back to the first row.

	The fallback matters: a record whose rows were created outside the form (a
	data import, a patch) may have no flag set at all, and callers still want
	the one address on file rather than nothing.
	"""
	if not rows:
		return None
	row = next((r for r in rows if r.get(flag)), rows[0])
	return row.get(fieldname)


def primary_email(doc):
	"""Primary email address of a loaded Person / Family / Missionary."""
	return pick(doc.get(EMAIL_FIELD), "email_address")


def primary_phone(doc):
	"""Primary phone number of a loaded Person / Family / Missionary."""
	return pick(doc.get(PHONE_FIELD), "phone_number")


def primary_address(doc):
	"""Name of the primary Address of a loaded Person / Family / Missionary."""
	return pick(doc.get(ADDRESS_FIELD), "address")


def mailing_address(doc):
	"""Name of the Address paper mail should go to.

	Falls back to the primary address when no row is flagged as a mailing
	address, so a record with a single address always has somewhere to mail to.
	"""
	rows = doc.get(ADDRESS_FIELD)
	if not rows:
		return None
	row = next((r for r in rows if r.get("is_mailing_address")), None)
	return row.address if row else primary_address(doc)


# ---------------------------------------------------------------------------
# Lookups by name
# ---------------------------------------------------------------------------


def _lookup(child_doctype, value_field, parenttype, parent, flag="is_primary"):
	if not parent:
		return None
	rows = frappe.get_all(
		child_doctype,
		filters={"parenttype": parenttype, "parent": parent},
		fields=[value_field, flag, "idx"],
		order_by=f"{flag} desc, idx asc",
		limit=1,
	)
	return rows[0].get(value_field) if rows else None


def get_primary_email(parenttype, parent):
	"""Primary email address of *parent*, or ``None``."""
	return _lookup(EMAIL_DOCTYPE, "email_address", parenttype, parent)


def get_primary_phone(parenttype, parent):
	"""Primary phone number of *parent*, or ``None``."""
	return _lookup(PHONE_DOCTYPE, "phone_number", parenttype, parent)


def get_primary_address(parenttype, parent):
	"""Name of the primary Address of *parent*, or ``None``."""
	return _lookup(ADDRESS_DOCTYPE, "address", parenttype, parent)


def get_mailing_address(parenttype, parent):
	"""Name of the Address paper mail for *parent* should go to, or ``None``."""
	return _lookup(ADDRESS_DOCTYPE, "address", parenttype, parent, flag="is_mailing_address") or (
		get_primary_address(parenttype, parent)
	)


def get_primary_emails(parenttype, parents):
	"""Map ``{parent: primary email}`` for many records in one query.

	Records with no email on file are absent from the map. Rows are ordered so
	the primary one is written last and therefore wins.
	"""
	parents = [p for p in (parents or []) if p]
	if not parents:
		return {}
	rows = frappe.get_all(
		EMAIL_DOCTYPE,
		filters={"parenttype": parenttype, "parent": ("in", parents)},
		fields=["parent", "email_address"],
		order_by="is_primary asc, idx desc",
	)
	return {r.parent: r.email_address for r in rows if r.email_address}


# ---------------------------------------------------------------------------
# SQL fragments for reports
# ---------------------------------------------------------------------------


def _subquery(child_doctype, value_field, parent_alias, parenttype, flag="is_primary"):
	"""Correlated subquery returning one contact value per parent row.

	*parenttype* is checked against :data:`CONTACT_PARENTS` and *parent_alias*
	against a strict pattern because both are interpolated into SQL; every
	caller passes a literal from this app, never user input.
	"""
	if parenttype not in CONTACT_PARENTS:
		frappe.throw(_("{0} does not carry contact tables").format(parenttype))
	if not parent_alias.isidentifier():
		frappe.throw(_("Invalid SQL alias: {0}").format(parent_alias))

	return (
		f"(SELECT c.`{value_field}` FROM `tab{child_doctype}` c "
		f"WHERE c.parenttype = '{parenttype}' AND c.parent = {parent_alias}.name "
		f"ORDER BY c.`{flag}` DESC, c.idx ASC LIMIT 1)"
	)


def primary_email_sql(parent_alias, parenttype="Person"):
	"""SQL expression for the primary email of the row aliased *parent_alias*."""
	return _subquery(EMAIL_DOCTYPE, "email_address", parent_alias, parenttype)


def primary_phone_sql(parent_alias, parenttype="Person"):
	"""SQL expression for the primary phone of the row aliased *parent_alias*."""
	return _subquery(PHONE_DOCTYPE, "phone_number", parent_alias, parenttype)


def primary_address_sql(parent_alias, parenttype="Person"):
	"""SQL expression for the primary Address name of the row aliased *parent_alias*."""
	return _subquery(ADDRESS_DOCTYPE, "address", parent_alias, parenttype)


def mailing_address_sql(parent_alias, parenttype="Person"):
	"""SQL expression for the mailing Address name of the row aliased *parent_alias*.

	Mirrors :func:`mailing_address`: a record with addresses but none flagged
	for mail falls back to its primary address.
	"""
	mailing = _subquery(
		ADDRESS_DOCTYPE, "address", parent_alias, parenttype, flag="is_mailing_address"
	)
	return f"COALESCE({mailing}, {primary_address_sql(parent_alias, parenttype)})"


# ---------------------------------------------------------------------------
# Validation, shared by every doctype that carries the contact tables
# ---------------------------------------------------------------------------


def validate_contact_tables(doc):
	"""Keep the three contact tables internally consistent.

	Trims values, rejects duplicates within a record, and makes sure each table
	has exactly one primary row (and, for addresses, at most one mailing row).
	Flags are corrected rather than rejected so that data imports and the sample
	data loader never fail on a missing checkbox.
	"""
	before = doc.get_doc_before_save()

	for fieldname, _child_doctype, value_field, label in CONTACT_TABLES:
		rows = doc.get(fieldname) or []
		_trim_values(rows, value_field)
		_reject_duplicates(rows, value_field, label)
		_ensure_single_flag(
			rows,
			"is_primary",
			_flagged_before(before, fieldname, "is_primary"),
			default_to_first=True,
		)

	_ensure_single_flag(
		doc.get(ADDRESS_FIELD) or [],
		"is_mailing_address",
		_flagged_before(before, ADDRESS_FIELD, "is_mailing_address"),
		default_to_first=False,
	)
	sync_notification_addresses(doc.get(EMAIL_FIELD) or [])


def _flagged_before(before, fieldname, flag):
	"""Names of the rows that already carried *flag* at the last save."""
	if not before:
		return frozenset()
	return frozenset(row.name for row in (before.get(fieldname) or []) if row.get(flag))


def sync_notification_addresses(rows):
	"""Mirror the primary address into ``notification_address``, blanking the rest.

	A Frappe Notification can aim at a child table field ("field,table"), but it
	walks every row of that table and cannot filter them, so pointing it at
	``email_address`` would mail a member at all their addresses at once.
	Pointing it at ``notification_address`` instead walks the same rows and finds
	a value on the primary one only, because Frappe skips rows whose value is not
	a valid email. The result is a single recipient, in To: rather than Cc:.
	"""
	for row in rows:
		row.set("notification_address", row.get("email_address") if row.get("is_primary") else None)


def _trim_values(rows, value_field):
	for row in rows:
		value = row.get(value_field)
		if isinstance(value, str):
			row.set(value_field, value.strip())


def _reject_duplicates(rows, value_field, label):
	seen = set()
	for row in rows:
		value = row.get(value_field)
		if not value:
			continue
		key = value.lower() if isinstance(value, str) else value
		if key in seen:
			frappe.throw(
				_("{0} is listed twice. Please remove the duplicate {1}.").format(
					frappe.bold(value), label
				),
				title=_("Duplicate {0}").format(label.title()),
			)
		seen.add(key)


def _ensure_single_flag(rows, flag, flagged_before, default_to_first):
	"""Leave exactly one row flagged, namely the one just ticked.

	When a save arrives with two rows flagged, the winner is whichever was not
	flagged at the last save, so ticking a box takes effect wherever the row sits
	in the grid. Picking by position instead would silently revert anyone who
	ticked a row above the current one. The desk grid hides that, because its JS
	unticks siblings on the spot, but the portal web form and data imports do not.

	When there is no previous state to compare against, such as a new record or
	an import, the last flagged row wins, which at least stays deterministic.
	"""
	if not rows:
		return

	flagged = [row for row in rows if row.get(flag)]
	if not flagged:
		if default_to_first:
			rows[0].set(flag, 1)
		return

	newly_flagged = [row for row in flagged if row.name not in flagged_before]
	keep = newly_flagged[-1] if newly_flagged else flagged[-1]
	for row in flagged:
		if row is not keep:
			row.set(flag, 0)


# ---------------------------------------------------------------------------
# Desk / portal helpers
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_emails_for(parenttype, parents):
	"""Return ``{"emails": [...], "missing": [...]}`` for a set of records.

	Used by the Group form's "Email Members" action, which needs a mailto list
	plus the names of anyone it had to leave out.
	"""
	if parenttype not in CONTACT_PARENTS:
		frappe.throw(_("{0} does not carry contact tables").format(parenttype))

	if isinstance(parents, str):
		parents = frappe.parse_json(parents)
	parents = [p for p in (parents or []) if p]

	for parent in parents:
		frappe.has_permission(parenttype, doc=parent, throw=True)

	by_parent = get_primary_emails(parenttype, parents)
	return {
		"emails": [by_parent[p] for p in parents if by_parent.get(p)],
		"missing": [p for p in parents if not by_parent.get(p)],
	}
