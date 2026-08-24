"""Move the single-value contact fields onto the new contact tables.

Person, Family, Missionary and Missionary Agency used to carry one email, one
phone and one or two Link fields to Address. Those fields are gone; each record
now has ``emails``, ``phones`` and ``addresses`` child tables (see
``churchit.contacts``).

Frappe leaves removed columns in place rather than dropping them, so the old
values are still readable here even though the doctypes no longer declare the
fields. Anything that has already been migrated is skipped, so this
is safe to re-run; once every site has migrated the leftover columns can be
cleared out with ``bench --site <site> trim-tables``.
"""

import frappe
from pypika import Case

from churchit.contacts import (
	DEFAULT_ADDRESS_TYPE,
	DEFAULT_EMAIL_TYPE,
	DEFAULT_PHONE_TYPE,
	OTHER_ADDRESS_TYPE,
	create_default_contact_types,
)


def execute():
	create_default_contact_types()

	_migrate_person()
	_migrate_family()
	_migrate_missionary()
	_migrate_missionary_agency()

	_backfill_notification_addresses()


# ---------------------------------------------------------------------------
# Per-doctype migrations
# ---------------------------------------------------------------------------


def _migrate_person():
	rows = _read_legacy(
		"Person", ["email", "primary_phone", "home_address", "mailing_address", "different_mailing_address"]
	)

	for row in rows:
		if row.get("email"):
			_add_email("Person", row.name, row["email"])
		if row.get("primary_phone"):
			_add_phone("Person", row.name, row["primary_phone"])

		_add_addresses("Person", row.name, _person_address_rows(row))


def _person_address_rows(row):
	"""Work out the address rows for one Person from the old fields.

	The old model had a home address plus a "Different Mailing Address" flag
	gating a second Link. Unchecked meant mail went to the home address, which
	is now expressed as the mailing flag on that single row.
	"""
	home = row.get("home_address")
	mailing = row.get("mailing_address")
	separate = row.get("different_mailing_address") and mailing and mailing != home

	if home and separate:
		return [
			(home, DEFAULT_ADDRESS_TYPE, 0, 1),
			(mailing, OTHER_ADDRESS_TYPE, 1, 0),
		]
	if home:
		return [(home, DEFAULT_ADDRESS_TYPE, 1, 1)]
	if mailing:
		# No home address on file, so the mailing address is all there is.
		return [(mailing, OTHER_ADDRESS_TYPE, 1, 1)]
	return []


def _migrate_family():
	for row in _read_legacy("Family", ["home_address"]):
		if row.get("home_address"):
			_add_addresses("Family", row.name, [(row["home_address"], DEFAULT_ADDRESS_TYPE, 1, 1)])


def _migrate_missionary():
	for row in _read_legacy("Missionary", ["email", "mailing_address", "physical_address"]):
		if row.get("email"):
			_add_email("Missionary", row.name, row["email"])

		physical = row.get("physical_address")
		mailing = row.get("mailing_address")

		if physical and mailing and physical != mailing:
			addresses = [
				(physical, DEFAULT_ADDRESS_TYPE, 0, 1),
				(mailing, OTHER_ADDRESS_TYPE, 1, 0),
			]
		elif physical:
			addresses = [(physical, DEFAULT_ADDRESS_TYPE, 1, 1)]
		elif mailing:
			addresses = [(mailing, OTHER_ADDRESS_TYPE, 1, 1)]
		else:
			addresses = []

		_add_addresses("Missionary", row.name, addresses)


def _migrate_missionary_agency():
	for row in _read_legacy("Missionary Agency", ["email", "phone", "mailing_address"]):
		if row.get("email"):
			_add_email("Missionary Agency", row.name, row["email"])
		if row.get("phone"):
			_add_phone("Missionary Agency", row.name, row["phone"])
		if row.get("mailing_address"):
			_add_addresses(
				"Missionary Agency",
				row.name,
				[(row["mailing_address"], OTHER_ADDRESS_TYPE, 1, 1)],
			)


def _backfill_notification_addresses():
	"""Populate the derived ``notification_address`` on every email row.

	The rows written above are inserted directly rather than through a parent
	save, so the parent's validate hook never runs over them. Setting the column
	here keeps Notifications aiming at exactly one address per record.
	"""
	Email = frappe.qb.DocType("Email Address")
	frappe.qb.update(Email).set(
		Email.notification_address,
		Case().when(Email.is_primary == 1, Email.email_address).else_(None),
	).run()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_legacy(doctype, columns):
	"""Read the old columns straight from the table, skipping any already dropped.

	Returns ``[]`` when none of the columns survive, which is the normal state
	on a site that has already migrated and been trimmed.
	"""
	if not frappe.db.table_exists(doctype):
		return []

	available = [c for c in columns if frappe.db.has_column(doctype, c)]
	if not available:
		return []

	# The columns are gone from the doctype meta but still present on the table,
	# so they are addressed positionally rather than through a DocType field.
	table = frappe.qb.DocType(doctype)
	return frappe.qb.from_(table).select(table.name, *(table[c] for c in available)).run(as_dict=True)


def _add_email(parenttype, parent, email):
	_append(
		parenttype,
		parent,
		"emails",
		"Email Address",
		[{"email_address": email, "email_type": DEFAULT_EMAIL_TYPE, "is_primary": 1}],
	)


def _add_phone(parenttype, parent, phone):
	_append(
		parenttype,
		parent,
		"phones",
		"Phone Number",
		[{"phone_number": phone, "phone_type": DEFAULT_PHONE_TYPE, "is_primary": 1}],
	)


def _add_addresses(parenttype, parent, addresses):
	"""Append ``(address, type, is_mailing_address, is_primary)`` tuples."""
	values = [
		{
			"address": address,
			"address_type": address_type,
			"is_mailing_address": is_mailing,
			"is_primary": is_primary,
		}
		# A Link may point at an Address that has since been deleted.
		for address, address_type, is_mailing, is_primary in addresses
		if frappe.db.exists("Address", address)
	]
	_append(parenttype, parent, "addresses", "Postal Address", values)


def _append(parenttype, parent, parentfield, child_doctype, rows):
	"""Insert *rows* into a child table, unless the record already has some.

	The check is made once for the whole table rather than per row, so a record
	that migrates to two addresses gets both. That is also what makes the patch
	re-runnable: a table already populated by an earlier run, or edited by hand
	after upgrading, is left exactly as it is.
	"""
	if not rows:
		return

	if frappe.db.exists(
		child_doctype, {"parenttype": parenttype, "parent": parent, "parentfield": parentfield}
	):
		return

	for idx, values in enumerate(rows, start=1):
		child = frappe.new_doc(child_doctype)
		child.update(values)
		child.parenttype = parenttype
		child.parent = parent
		child.parentfield = parentfield
		child.idx = idx
		child.insert(ignore_permissions=True)
