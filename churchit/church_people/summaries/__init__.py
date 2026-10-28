# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Person summary fields: figures about a person worked out from records kept elsewhere.

They make a saved Person report a smart list: "attended in the last 90 days", "in no group" and "gave last year"
become plain Person filters. Each module in this package is one area, found by `areas()`, and declares:

- ``FIELDS``: the read-only Person fields it owns.
- ``SOURCES``: ``{doctype: function(doc) -> people}``, the people whose summaries a saved or deleted record of that
  doctype changes. Include the people the record pointed at before the save, so someone taken off is refreshed too.
- ``compute(people) -> {person: {field: value}}``: the area's fields for each of *people*. A person it leaves out, or
  a field it leaves out, gets the field's empty value. A Table MultiSelect field takes a list of the linked names.

An area counts only records of the person's own church and shared records, through `same_church`, so a directory
row every church reads never shows another church's activity.
"""

import importlib
import pkgutil
from functools import cache

import frappe
from frappe.query_builder.functions import Coalesce
from pypika.terms import EmptyCriterion

from churchit.church_scope import is_multi_church

BATCH = 500


@cache
def areas() -> tuple:
	"""Every area module in this package; its tests sit beside it as ``test_<area>``."""
	return tuple(
		importlib.import_module(f"{__name__}.{module.name}")
		for module in pkgutil.iter_modules(__path__)
		if not module.name.startswith("test_")
	)


@cache
def sources() -> dict[str, tuple]:
	"""{doctype: (area, ...)} for the doctypes some area reads."""
	by_doctype = {}
	for area in areas():
		for doctype in area.SOURCES:
			by_doctype.setdefault(doctype, []).append(area)
	return {doctype: tuple(found) for doctype, found in by_doctype.items()}


def on_change(doc, method=None) -> None:
	"""doc_events for every doctype: add the people whose summaries a save, cancel or delete changes to the refresh.

	A person who moves church is refreshed too, because `same_church` counts their new church's records. A deleted
	record's summary rows go at once.
	"""
	if frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate:
		return
	if method == "on_trash":
		delete_rows_naming(doc)
	people = set()
	for area in sources().get(doc.doctype, ()):
		people.update(area.SOURCES[doc.doctype](doc))
	if doc.doctype == "Person" and method == "on_update" and doc.has_value_changed("church"):
		people.add(doc.name)
	people.discard(None)
	queue_refresh(people)


def queue_refresh(people: set[str]) -> None:
	"""Refresh *people* after the commit, in one job with everyone else this transaction changes.

	A rollback drops them, because the changes that named them are gone.
	"""
	if not people:
		return
	if not frappe.flags.summary_people:
		frappe.flags.summary_people = set()
		frappe.db.after_commit.add(enqueue_queued)
		frappe.db.after_rollback.add(lambda: frappe.flags.pop("summary_people", None))
	frappe.flags.summary_people.update(people)


def enqueue_queued() -> None:
	"""After the commit: queue one refresh of the people this transaction changed."""
	if people := frappe.flags.pop("summary_people", None):
		frappe.enqueue(refresh, queue="short", people=sorted(people))


def delete_rows_naming(doc) -> None:
	"""Delete the summary table rows that name *doc*, which is being deleted, in the same transaction.

	`ignore_links_on_delete` lets the delete through, and a row left until the queued refresh would fail every save
	of its person on Frappe's link check.
	"""
	meta = frappe.get_meta("Person")
	for area in sources().get(doc.doctype, ()):
		for df in filter(is_table, map(meta.get_field, area.FIELDS)):
			link = table_link_field(df)
			if frappe.get_meta(df.options).get_field(link).options == doc.doctype:
				frappe.db.delete(
					df.options, {"parenttype": "Person", "parentfield": df.fieldname, link: doc.name}
				)


def refresh_daily() -> None:
	"""Daily scheduler: recompute everyone, since a rolling window such as the last 90 days moves every day."""
	refresh()


def refresh(people: list[str] | None = None) -> None:
	"""Recompute every summary field of *people*, or of everyone, and store the values that changed."""
	# church-scope: stores figures on each person and shows nobody anything
	names = frappe.get_all(
		"Person", filters={"name": ("in", people)} if people is not None else None, pluck="name"
	)
	for start in range(0, len(names), BATCH):
		refresh_batch(names[start : start + BATCH])


def refresh_batch(people: list[str]) -> None:
	meta = frappe.get_meta("Person")
	for area in areas():
		fields = [meta.get_field(fieldname) for fieldname in area.FIELDS]
		stored = get_stored_values(people, fields)
		computed = area.compute(people)
		for person in people:
			values = computed.get(person, {})
			current = {df.fieldname: values.get(df.fieldname, empty_value(df)) for df in fields}
			store_changes(person, fields, stored[person], current)


def get_stored_values(people: list[str], fields: list) -> dict[str, dict]:
	"""{person: {field: value}} as stored now, tables as lists of linked names in row order."""
	# church-scope: reads back the figures this module stores, to write only what changed
	scalars = [df.fieldname for df in fields if not is_table(df)]
	stored = {
		row.name: row
		for row in frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", *scalars])
	}
	for df in filter(is_table, fields):
		for row in stored.values():
			row[df.fieldname] = []
		link = table_link_field(df)
		rows = frappe.get_all(
			df.options,
			filters={"parenttype": "Person", "parentfield": df.fieldname, "parent": ("in", people)},
			fields=["parent", link],
			order_by="idx asc",
		)
		for row in rows:
			stored[row.parent][df.fieldname].append(row[link])
	return stored


def store_changes(person: str, fields: list, stored: dict, current: dict) -> None:
	"""Write each of *current* that differs from *stored*, leaving `modified` alone."""
	changed = {
		df.fieldname: current[df.fieldname]
		for df in fields
		if not is_table(df) and (stored[df.fieldname] or None) != (current[df.fieldname] or None)
	}
	if changed:
		frappe.db.set_value("Person", person, changed, update_modified=False)
	for df in filter(is_table, fields):
		if stored[df.fieldname] != current[df.fieldname]:
			store_table(person, df, current[df.fieldname])


def store_table(person: str, df, names: list[str]) -> None:
	"""Replace *person*'s rows in the Table MultiSelect *df* with one row per linked name."""
	frappe.db.delete(df.options, {"parenttype": "Person", "parentfield": df.fieldname, "parent": person})
	link = table_link_field(df)
	for idx, name in enumerate(names, start=1):
		row = frappe.get_doc(
			{
				"doctype": df.options,
				"parenttype": "Person",
				"parentfield": df.fieldname,
				"parent": person,
				"idx": idx,
				link: name,
			}
		)
		row.set_new_name()
		row.db_insert()


def keep_stored_values(person) -> None:
	"""Person `_validate_links`: give a saved Person its stored summary fields back, and keep the save off their tables.

	This module is their only writer. A refresh leaves `modified` alone, so a form opened before it passes
	Frappe's check for a stale copy and would write the old figures and rows back. It runs before Frappe's link
	check, so a form opened before a record it names was deleted still saves.
	"""
	before = person.get_doc_before_save()
	if not before:
		return
	meta = frappe.get_meta("Person")
	tables = []
	for df in (meta.get_field(fieldname) for area in areas() for fieldname in area.FIELDS):
		if is_table(df):
			person.set(df.fieldname, [row.as_dict() for row in before.get(df.fieldname)])
			tables.append(df.options)
		else:
			person.set(df.fieldname, before.get(df.fieldname))
	person.flags.ignore_children_type = tables


def table_link_field(df) -> str:
	"""The Link field of a Table MultiSelect's child doctype."""
	return next(field.fieldname for field in frappe.get_meta(df.options).fields if field.fieldtype == "Link")


def is_table(df) -> bool:
	return df.fieldtype == "Table MultiSelect"


def empty_value(df):
	"""What a field holds when an area has nothing for the person."""
	if is_table(df):
		return []
	if df.fieldtype in ("Int", "Float", "Currency", "Check"):
		return 0
	return None


def same_church(Record, Person):
	"""Query criterion: *Record* belongs to the person's own church or is shared; no limit on a single-church site."""
	if not is_multi_church():
		return EmptyCriterion()
	return (Record.church == Person.church) | (Coalesce(Record.church, "") == "")
