# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the multi-church switch does to existing records and to the desk."""

import frappe
from frappe.custom.doctype.property_setter.property_setter import (
	bulk_delete_property_setters,
	delete_property_setter,
	make_property_setter,
)

from churchit.church_scope import (
	CHURCH_FIELD,
	PEOPLE_DOCTYPES,
	SHAREABLE_DOCTYPES,
	SHARED,
	SHARED_BY_FIELD,
	SHARED_FIELD,
	scoped_doctypes,
)

# Property Setters that reveal the fields once branches exist. They are
# site-local: hooks.py only exports setters on the Frappe doctypes it lists.
REVEALED_PROPERTIES = {"hidden": "0", "in_standard_filter": "1"}
# Every field this module ever reveals, so a setter can be found again and pruned
# after its doctype stops offering the field.
MANAGED_FIELDS = (CHURCH_FIELD, SHARED_FIELD, SHARED_BY_FIELD)


def revealed_fields():
	"""Which field to reveal on which doctype: the church everywhere, sharing where it is offered.

	`shared_by_church` is revealed with the checkbox, so a shared record says which
	church it came from. Without it a record shared by the main church looked
	exactly like one the branch shared itself.
	"""
	shareable = set(SHAREABLE_DOCTYPES)
	for doctype in scoped_doctypes():
		yield doctype, CHURCH_FIELD
		if doctype in shareable:
			yield doctype, SHARED_FIELD
			yield doctype, SHARED_BY_FIELD


def apply_field_visibility(enabled):
	"""Reveal the fields the switch calls for, and drop every setter it does not.

	One set drives both directions. Switching off asks for nothing, and a doctype
	that leaves SHAREABLE_DOCTYPES asks for less than it did before: without the
	pruning its setters outlived the field they revealed.
	"""
	wanted = set(revealed_fields()) if enabled else set()
	current = get_managed_setters()
	remove_unwanted_setters(current, wanted)
	add_missing_setters(current, wanted)


def get_managed_setters():
	"""Map (doctype, fieldname, property) to value for every setter this app owns."""
	setters = frappe.get_all(
		"Property Setter",
		filters={
			"doc_type": ("in", scoped_doctypes()),
			"field_name": ("in", list(MANAGED_FIELDS)),
			"property": ("in", list(REVEALED_PROPERTIES)),
		},
		fields=["doc_type", "field_name", "property", "value"],
	)
	return {(setter.doc_type, setter.field_name, setter.property): setter.value for setter in setters}


def remove_unwanted_setters(current, wanted):
	"""Delete the setters in *current* that *wanted* no longer asks for."""
	unwanted = [
		{"doctype": doctype, "fieldname": fieldname, "property": prop}
		for doctype, fieldname, prop in current
		if (doctype, fieldname) not in wanted
	]
	if unwanted:
		# bypass_hooks: a raw delete per row, and the doctype caches cleared once
		# each, instead of a document delete and a feed entry for every setter.
		bulk_delete_property_setters(unwanted, bypass_hooks=True)


def add_missing_setters(current, wanted):
	"""Insert the setters *wanted* asks for that *current* lacks or holds a stale value for."""
	missing = [
		(doctype, fieldname, prop, value)
		for doctype, fieldname in sorted(wanted)
		for prop, value in REVEALED_PROPERTIES.items()
		if current.get((doctype, fieldname, prop)) != value
	]
	stale = [
		{"doctype": doctype, "fieldname": fieldname, "property": prop}
		for doctype, fieldname, prop, _value in missing
		if (doctype, fieldname, prop) in current
	]
	if stale:
		bulk_delete_property_setters(stale, bypass_hooks=True)
	# A raw insert per row and one cache clear per doctype: a setter's own
	# validate clears the doctype cache every time, which made switching on take seconds.
	for doctype, fieldname, prop, value in missing:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": doctype,
				"field_name": fieldname,
				"property": prop,
				"value": value,
				"property_type": "Check",
				"is_system_generated": 1,
			}
		).db_insert()
	for doctype in {doctype for doctype, *_rest in missing}:
		frappe.clear_cache(doctype=doctype)


def apply_people_privacy(private):
	"""Scope Person and Family by church like every other record, or let every church read them.

	Their `church` Link ships with ignore_user_permissions set, which is what opens
	the directory. Keeping people private overrides that with a site-local setter.
	"""
	for doctype in PEOPLE_DOCTYPES:
		if private:
			make_property_setter(
				doctype,
				CHURCH_FIELD,
				"ignore_user_permissions",
				"0",
				"Check",
				validate_fields_for_doctype=False,
			)
		else:
			delete_property_setter(doctype, "ignore_user_permissions", CHURCH_FIELD)
		frappe.clear_cache(doctype=doctype)


def backfill_root_church(root):
	"""Stamp the root church on every scoped record that has none, submitted ones included.

	A record someone deliberately shared keeps its empty church: "not set" matches
	the empty string too, so sharing has to be excluded by hand.
	"""
	shareable = set(SHAREABLE_DOCTYPES)
	for doctype in scoped_doctypes():
		filters = {CHURCH_FIELD: ("is", "not set")}
		if doctype in shareable:
			filters[SHARED_FIELD] = 0
		frappe.db.set_value(doctype, filters, CHURCH_FIELD, root, update_modified=False)
	normalise_shared_church()


def normalise_shared_church():
	"""Give every shared record the empty string the rest of the app compares against.

	A record shared before the switch holds NULL, which Frappe's permission
	clause reads as shared but ``church == SHARED`` does not, so sharing stopped
	propagating to the records that derive their church from it.
	"""
	for doctype in SHAREABLE_DOCTYPES:
		frappe.db.set_value(
			doctype,
			{SHARED_FIELD: 1, CHURCH_FIELD: ("is", "not set")},
			CHURCH_FIELD,
			SHARED,
			update_modified=False,
		)
