# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Permission rules that fail silently, checked from the source and the metadata.

1. A doctype with a `has_permission` hook has a `permission_query_conditions` hook, and the reverse.
2. Person Note is read only through `frappe.get_list`, or `get_doc` plus a permission check.
3. Person Note grants no share right and does not track changes.

Whitelisted Document methods are checked in test_doc_method_hygiene.py. Every way out takes a
reason, so the next person can tell a deliberate choice from an oversight.
"""

import ast
import json
import os
from collections import defaultdict
from functools import cached_property

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit import hooks
from churchit.tests.test_doc_method_hygiene import (
	APP_DIR,
	RAW_SQL,
	AppIndex,
	Function,
	Module,
	app_index,
	argument,
	calls,
	dotted,
	keyword,
	last_name,
	overrides_checks,
	parameter_names,
	passed_argument,
)

NOTE = "Person Note"

# Doctypes that carry one of the two permission hooks on purpose, and why the other is not needed.
ONE_SIDED_PERMISSION_HOOKS: dict[str, str] = {}

# Functions that read Person Note past its hooks, and why nobody sees a note through them.
RAW_NOTE_READS = {
	"church_people/privacy.py:forget_records_about": (
		"deletes every note about a person whose data is removed, for a manager who may change them "
		"or the retention job; it returns nothing"
	),
	"setup/sample_data.py:_delete_docs": "deletes the demo data, for a System Manager",
	"setup/sample_data.py:_delete_submittable_docs": "deletes the demo data, for a System Manager",
	"setup/sample_data.py:_insert_if_missing": "makes the demo data once, for a System Manager",
	"setup/sample_data.py:delete_sample_data": "counts the rows a delete empties, for a System Manager; it returns no note",
}

# Reads of Person Note that apply neither of its permission hooks.
RAW_NOTE_CALLS = (
	"frappe.get_all",
	"frappe.db.get_all",
	"frappe.db.get_list",
	"frappe.db.get_value",
	"frappe.db.get_values",
	"frappe.get_cached_value",
	"frappe.db.exists",
	"frappe.db.count",
	"frappe.qb.DocType",
	"frappe.qb.from_",
	"frappe.qb.get_query",
	"DocType",
)
DOCUMENT_READS = ("frappe.get_doc", "frappe.get_cached_doc", "frappe.get_last_doc")


def target_names(node) -> set[str]:
	return {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}


class TestPermissionHookPairs(FrappeTestCase):
	"""`has_permission` decides opening a record, `permission_query_conditions` listing it.

	A doctype with one and not the other lists records that refuse to open, or opens records by
	name that no list shows.
	"""

	def test_every_has_permission_hook_has_a_list_condition(self):
		missing = sorted(set(hooks.has_permission) - set(hooks.permission_query_conditions))
		missing = [doctype for doctype in missing if doctype not in ONE_SIDED_PERMISSION_HOOKS]
		self.assertEqual(missing, [], "These doctypes have has_permission but no permission_query_conditions")

	def test_every_list_condition_has_a_has_permission_hook(self):
		missing = sorted(set(hooks.permission_query_conditions) - set(hooks.has_permission))
		missing = [doctype for doctype in missing if doctype not in ONE_SIDED_PERMISSION_HOOKS]
		self.assertEqual(missing, [], "These doctypes have permission_query_conditions but no has_permission")

	def test_every_one_sided_entry_is_still_one_sided(self):
		paired = set(hooks.has_permission) & set(hooks.permission_query_conditions)
		self.assertEqual(sorted(paired & set(ONE_SIDED_PERMISSION_HOOKS)), [])


class NoteReads:
	"""Reads of Person Note that skip its hooks, following the doctype through constants, loops and calls."""

	def __init__(self, index: AppIndex):
		self.index = index

	@cached_property
	def calls_to(self) -> dict[Function, list[tuple[Function, ast.Call]]]:
		found = defaultdict(list)
		for caller in self.index.functions():
			for call in calls(caller.node):
				if callee := self.index.resolve(caller, call):
					found[callee].append((caller, call))
		return found

	def offenders(self):
		"""(function, call) for each read of Person Note in the app that applies neither hook."""
		for function in self.index.functions():
			for call in calls(function.node):
				if self.reads_past_hooks(function, call):
					yield function, call

	def reads_past_hooks(self, function: Function, call: ast.Call) -> bool:
		name = dotted(call.func) or ""
		if name in RAW_SQL:
			return any(isinstance(node, ast.Constant) and NOTE in str(node.value) for node in ast.walk(call))
		doctype = argument(call, 0, "doctype") or keyword(call, "table")
		if name in RAW_NOTE_CALLS or (name == "frappe.get_list" and overrides_checks(call)):
			return self.names_note(function, doctype)
		if name in DOCUMENT_READS and not isinstance(doctype, ast.Dict):
			checked = any(
				last_name(inner.func) in ("check_permission", "has_permission")
				for inner in calls(function.node)
			)
			return not checked and self.names_note(function, doctype)
		return False

	def names_note(self, function: Function, node, depth: int = 0) -> bool:
		"""True when *node*, as it stands in *function*, can hold "Person Note"."""
		if node is None or depth > 3:
			return False
		if isinstance(node, ast.Constant):
			return node.value == NOTE
		if not isinstance(node, ast.Name):
			return False
		for bound in ast.walk(function.node):
			if isinstance(bound, ast.For | ast.comprehension) and node.id in target_names(bound.target):
				if self.mentions_note(function.module, bound.iter):
					return True
			if isinstance(bound, ast.Assign) and any(
				node.id in target_names(target) for target in bound.targets
			):
				if self.names_note(function, bound.value, depth + 1) or self.mentions_note(
					function.module, bound.value
				):
					return True
		if node.id in parameter_names(function.node):
			return any(
				self.names_note(caller, passed, depth + 1)
				for caller, passed in self.passed_as(function, node.id)
			)
		return self.mentions_note(function.module, node)

	def passed_as(self, function: Function, parameter: str):
		"""(caller, argument) for each call in the app that passes *parameter* to *function*."""
		for caller, call in self.calls_to.get(function, []):
			yield caller, passed_argument(function, call, parameter)

	def mentions_note(self, module: Module, node, depth: int = 0) -> bool:
		"""True when "Person Note" appears in *node*, or in a module constant it names."""
		for inner in ast.walk(node):
			if isinstance(inner, ast.Constant) and inner.value == NOTE:
				return True
			if isinstance(inner, ast.Name) and depth < 3:
				owner, value = self.index.constant(module, inner.id)
				if owner and self.mentions_note(owner, value, depth + 1):
					return True
		return False


def query_reports_reading_notes():
	"""Query Reports whose SQL names Person Note: a report runs raw, past every hook."""
	for root, _dirs, files in os.walk(APP_DIR):
		if not root.endswith("/report") and "/report/" not in root:
			continue
		for name in files:
			if name.endswith(".json"):
				with open(os.path.join(root, name)) as file:
					report = json.load(file)
				if report.get("report_type") == "Query Report" and NOTE in (report.get("query") or ""):
					yield os.path.relpath(os.path.join(root, name), APP_DIR)


class TestPersonNoteReads(FrappeTestCase):
	"""Person Note is read through `frappe.get_list`, or `get_doc` and a permission check.

	A note's category decides who reads it, through both permission hooks, and church scoping
	does not cover categories. `frappe.get_all`, `db.get_value`, `get_cached_value`, `db.exists`,
	`db.count`, raw SQL, `frappe.qb` and `get_list(ignore_permissions=True)` apply neither hook,
	so such a read shows a confidential note to anyone who reaches the code. The doctype is
	followed through module constants, loops over them, assignments, and the arguments of a
	function that takes it. Reads driven by field metadata (`person_data_map`) are not seen.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		reads = NoteReads(app_index())
		cls.found = {}
		for function, call in reads.offenders():
			cls.found.setdefault(
				f"{function.module.relative}:{function.name}", f"{function.module.relative}:{call.lineno}"
			)

	def test_person_note_is_read_only_through_its_hooks(self):
		unexplained = sorted(
			[line for key, line in self.found.items() if key not in RAW_NOTE_READS]
			+ list(query_reports_reading_notes())
		)
		assert not unexplained, (
			"These read Person Note past its permission hooks, so a reader sees notes in categories "
			"they may not read. Use frappe.get_list, or get_doc and check_permission, or add the "
			"function to RAW_NOTE_READS with the reason nobody sees a note through it: "
			+ ", ".join(unexplained)
		)

	def test_every_raw_note_read_is_still_there(self):
		self.assertEqual(sorted(set(RAW_NOTE_READS) - set(self.found)), [], "Stale RAW_NOTE_READS entries")


class TestPersonNoteMeta(FrappeTestCase):
	"""A share opens a note past both hooks, and every System Manager reads Version records.

	AGENTS.md "Person Notes" explains both.
	"""

	def shipped(self) -> dict:
		with open(os.path.join(APP_DIR, "church_people/doctype/person_note/person_note.json")) as file:
			return json.load(file)

	def test_no_role_may_share_a_note(self):
		sharing = [
			f"DocPerm {perm['role']} (shipped)" for perm in self.shipped()["permissions"] if perm.get("share")
		]
		for doctype in ("DocPerm", "Custom DocPerm"):
			roles = frappe.get_all(doctype, filters={"parent": NOTE, "share": 1}, pluck="role")
			sharing += [f"{doctype} {role}" for role in roles]
		sharing += [f"{perm.role} (meta)" for perm in frappe.get_meta(NOTE).permissions if perm.share]
		self.assertEqual(sharing, [], "Person Note must not grant the share right")

	def test_notes_do_not_track_changes(self):
		self.assertFalse(self.shipped().get("track_changes"), "person_note.json turns on Track Changes")
		self.assertFalse(frappe.get_meta(NOTE).track_changes, "A Property Setter turns on Track Changes")
