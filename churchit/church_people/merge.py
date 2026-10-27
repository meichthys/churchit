# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Merge two records of one person, or of one household, into the record to keep.

A merge is Frappe's own: `frappe.rename_doc(doctype, remove, keep, merge=True)`, the Rename dialog's "Merge with
existing". Frappe points every Link and Dynamic Link at the kept record, runs the removed record's
`before_rename` and the kept record's `after_rename`, and then deletes the removed record into Deleted Documents.
The controllers decide what else moves: the kept record's values win, and its blank fields and missing child
rows come from the removed one. `merge_people` and `merge_families` go the same way as the Rename dialog, so both
follow one set of rules, and either the whole merge happens or none of it. Both also lose the removed record's
copy in Deleted Documents (`drop_deleted_document`). They can also give the kept record the removed one's value
of each field the user chooses (`take_from_removed`), before the rename.
"""

from collections.abc import Callable

import frappe
from frappe import _
from frappe.desk.search import get_link_title
from frappe.model import data_fieldtypes
from frappe.model.document import Document
from frappe.utils import strip_html

from churchit.church_people.person_data_map import ROSTERS, linked_records
from churchit.church_scope import CHURCH_FIELD, is_multi_church
from churchit.contacts import CONTACT_TABLES, UNIQUE_VALUE_FIELDS, contact_key

# Contact child doctype -> the field holding its value
CONTACT_VALUE_FIELDS = {child_doctype: value_field for _f, child_doctype, value_field, _l in CONTACT_TABLES}


@frappe.whitelist(methods=["POST"])
def merge_people(keep: str, remove: str, take_from_removed: str | list[str] | None = None) -> str:
	"""Merge the person *remove* into the person *keep*, and return *keep*."""
	return merge("Person", keep, remove, frappe.parse_json(take_from_removed))


@frappe.whitelist(methods=["POST"])
def merge_families(keep: str, remove: str, take_from_removed: str | list[str] | None = None) -> str:
	"""Merge the family *remove* into the family *keep*, and return *keep*."""
	return merge("Family", keep, remove, frappe.parse_json(take_from_removed))


def merge(doctype: str, keep: str, remove: str, take_from_removed: list[str] | None = None) -> str:
	"""Merge *remove* into *keep*, undoing all of it when any part fails, even for a caller that goes on.

	*keep* first takes the value *remove* has in each of *take_from_removed*.
	"""
	savepoint = f"merge_{frappe.generate_hash(length=8)}"
	frappe.db.savepoint(savepoint)
	try:
		if take_from_removed:
			take_chosen_values(doctype, keep, remove, take_from_removed)
		# The kept record's save and the delete keep global search current, so skip the whole-doctype rebuild.
		return frappe.rename_doc(doctype, remove, keep, merge=True, show_alert=False, rebuild_search=False)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise


def take_chosen_values(doctype: str, keep: str, remove: str, fieldnames: list[str]) -> None:
	"""Save *keep* with the value *remove* has in each of *fieldnames*, which must be fields the user may choose."""
	kept = frappe.get_doc(doctype, keep)
	kept.check_permission("write")
	removed = frappe.get_doc(doctype, remove)
	removed.check_permission("read")
	refused = set(fieldnames) - set(choosable_fields(kept))
	if refused:
		frappe.throw(
			_("You cannot choose {0} in a merge.").format(", ".join(map(frappe.bold, sorted(refused)))),
			frappe.PermissionError,
		)
	for fieldname in fieldnames:
		kept.set(fieldname, removed.get(fieldname))
	kept.save()


def choosable_fields(doc: Document) -> list[str]:
	"""The typed fields of *doc* that a merge lets the user take from the removed record: those they may write.

	The church is never one: a merge does not move a record to another church (`refuse_all_but_a_merge`).
	"""
	writable = doc.meta.get_permitted_fieldnames(permission_type="write", with_virtual_fields=False)
	return [
		fieldname for fieldname in typed_fields(doc) if fieldname in writable and fieldname != CHURCH_FIELD
	]


@frappe.whitelist()
def get_merge_choices(keep: str, remove: str) -> dict:
	"""The fields where the people *keep* and *remove* both have a value and the values differ.

	Each field the user may choose comes with its label and each person's value as the form shows it.
	"""
	kept = frappe.get_doc("Person", keep)
	kept.check_permission("read")
	removed = frappe.get_doc("Person", remove)
	removed.check_permission("read")
	return {
		"keep": kept.full_name,
		"remove": removed.full_name,
		"fields": [
			{
				"fieldname": fieldname,
				"label": _(kept.meta.get_label(fieldname)),
				"keep": get_display_value(kept, fieldname),
				"remove": get_display_value(removed, fieldname),
			}
			for fieldname in choosable_fields(kept)
			if kept.get(fieldname)
			and removed.get(fieldname)
			and kept.get(fieldname) != removed.get(fieldname)
		],
	}


def get_display_value(doc: Document, fieldname: str) -> str:
	"""The value of *fieldname* as plain text, as the form shows it: a linked record by its title when it has one."""
	df = doc.meta.get_field(fieldname)
	value = doc.get(fieldname)
	if df.fieldtype == "Link":
		return get_link_title(df.options, value)
	if df.fieldtype == "Text Editor":
		return strip_html(value)
	# format_value gives these as HTML.
	if df.fieldtype in ("Text", "Small Text", "Long Text", "Markdown Editor"):
		return value
	return frappe.format_value(value, df)


def drop_deleted_document(doctype: str, name: str) -> None:
	"""after_rename of a merge: delete the copy of the removed record *name* that the merge leaves in Deleted Documents.

	The copy still holds the record's personal data, and restoring it would bring back a record nothing links to.
	Frappe deletes the removed record after every hook has run, so the copy goes when the merge commits. Only a
	copy made since this call goes: a merge undone before the commit leaves none, and older copies of a reused
	name stay.
	"""
	since = frappe.utils.now()
	frappe.db.before_commit.add(
		lambda: frappe.db.delete(
			"Deleted Document", {"deleted_doctype": doctype, "deleted_name": name, "creation": (">=", since)}
		)
	)


def refuse_all_but_a_merge(doc: Document, kept: Document | None) -> None:
	"""before_rename: let *doc*'s ID change only by a merge into *kept*, of its own church, by someone who may delete it."""
	if not kept:
		frappe.throw(
			_("A {0} keeps its ID. To combine two records of one {0}, merge one into the other.").format(
				_(doc.doctype)
			),
			title=_("Not Renamed"),
		)
	if is_multi_church() and doc.church != kept.church:
		frappe.throw(
			_("{0} and {1} belong to different churches, so they cannot be merged.").format(
				frappe.bold(doc.get_title()), frappe.bold(kept.get_title())
			),
			title=_("Not Merged"),
		)
	if not frappe.has_permission(doc.doctype, "delete", doc=doc):
		frappe.throw(
			_("A merge deletes {0}, and you may not delete it.").format(frappe.bold(doc.get_title())),
			frappe.PermissionError,
		)


def fill_blanks(doc: Document, other: Document, fieldnames) -> None:
	"""Give each of *fieldnames* that is blank on *doc* the value it has on *other*."""
	for fieldname in fieldnames:
		if not doc.get(fieldname) and other.get(fieldname):
			doc.set(fieldname, other.get(fieldname))


def take_import_id(doc: Document, other: Document) -> None:
	"""Give *doc* the Imported ID of *other* when it has none. When it has its own, say which one is not kept.

	An import finds a record by its one Imported ID, so the next import from that system adds the record of
	the ID not kept again. A comment on *doc* keeps the ID in sight.
	"""
	if not other.legacy_id or (other.legacy_system, other.legacy_id) == (doc.legacy_system, doc.legacy_id):
		return
	if not doc.legacy_id:
		doc.legacy_system, doc.legacy_id = other.legacy_system, other.legacy_id
		return
	message = _(
		"{0} keeps its own Imported ID. Imported ID {1} from {2} was not kept, so the next import from {2} "
		"adds that record again. Merge the two records in {2} too."
	).format(frappe.bold(doc.get_title()), frappe.bold(other.legacy_id), frappe.bold(other.legacy_system))
	doc.add_comment("Info", message)
	frappe.msgprint(message, title=_("Imported ID Not Kept"), indicator="orange")


def typed_fields(doc: Document) -> list[str]:
	"""The fields of *doc* someone types in: not tables, and not the read-only ones a save works out."""
	return [df.fieldname for df in doc.meta.fields if df.fieldtype in data_fieldtypes and not df.read_only]


def adopt_rows(doc: Document, other: Document, fieldname: str, key: Callable) -> list[str]:
	"""Move *other*'s rows of the table *fieldname* onto *doc*, deleting those *doc* has already, by *key*.

	It writes to the database, so reload *doc* to see the rows. A row moved onto a table that has rows already
	loses its primary and mailing flags, so *doc*'s choice stands. Returns the names of the rows moved.
	"""
	rows = doc.get(fieldname)
	have = {key(row) for row in rows}
	moved = []
	for row in other.get(fieldname):
		if key(row) in have:
			frappe.db.delete(row.doctype, row.name)
			continue
		have.add(key(row))
		values = {"parent": doc.name, "idx": len(rows) + len(moved) + 1}
		if rows:
			values.update(
				{flag: 0 for flag in ("is_primary", "is_mailing_address") if row.meta.has_field(flag)}
			)
		frappe.db.set_value(row.doctype, row.name, values, update_modified=False)
		moved.append(row.name)
	return moved


def contact_row_key(row: Document) -> str:
	"""Two contact rows are the same when their values are: a phone number by its digits, the rest by their text."""
	return contact_key(row.doctype, row.get(CONTACT_VALUE_FIELDS[row.doctype]) or "")


def adopt_contact_rows(doc: Document, other: Document) -> None:
	"""Move *other*'s emails, phones and addresses onto *doc*, leaving out the ones *doc* has.

	A row *doc* shared from *other* now names *doc* itself, which holds the value from here on.
	"""
	for fieldname, child_doctype, *_rest in CONTACT_TABLES:
		adopt_rows(doc, other, fieldname, contact_row_key)
		if child_doctype in UNIQUE_VALUE_FIELDS:
			frappe.db.set_value(
				child_doctype,
				{"parenttype": doc.doctype, "parent": doc.name, "shared_from": doc.name},
				"shared_from",
				None,
				update_modified=False,
			)


def remove_repeated_roster_rows(person: str, family: str | None) -> None:
	"""Leave *person* once on each roster, and on no family's roster but *family*'s.

	The first row stays and takes the blank fields of the rows removed, such as a group role.
	"""
	parents = {(row.parenttype, row.parent) for row in linked_records(person) if row.doctype in ROSTERS}
	for parenttype, parent in sorted(parents):
		doc = frappe.get_doc(parenttype, parent)
		rows = [
			row
			for row in doc.get_all_children()
			if row.doctype in ROSTERS and row.get(ROSTERS[row.doctype]) == person
		]
		if parenttype == "Family" and parent != family:
			removed = rows
			if doc.primary_contact == person:
				doc.primary_contact = None
		else:
			removed = rows[1:]
			for row in removed:
				fill_blanks(rows[0], row, typed_fields(row))
		if removed:
			for row in removed:
				doc.remove(row)
			doc.save(ignore_permissions=True)
