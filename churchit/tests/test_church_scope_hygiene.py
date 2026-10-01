# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The two rules that keep one church's records out of another church's view.

Multi-church leaks quietly: nothing errors, a branch simply sees rows it should
not. These tests turn both ways that happens into a failing build.

1. Every doctype that stores records carries a `church` field, or says here why
   it is shared by every church.
2. Every read that carries no permission filter of its own applies the scope,
   or carries a `# church-scope: <reason>` comment saying why it cannot cross
   churches.

Both ways out take a reason, not just a name, so the next person can tell a
deliberate choice from an oversight.
"""

import ast
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_scope import SHAREABLE_DOCTYPES, scoped_doctypes

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Doctypes with no `church` field on purpose. Child tables (scoped by their
# parent) and Singles (one per site) are never listed: they are excluded below.
GLOBAL_DOCTYPES = {
	"the shared vocabulary every church picks from": {
		"Address Type",
		"Background Check Type",
		"Care Request Type",
		"Case Type",
		"Email Type",
		"Expense Type",
		"Function Attendance Type",
		"Function Type",
		"Group Role",
		"Group Status",
		"Life Event Type",
		"Member Status",
		"Missionary Support Frequency",
		"Payment Type",
		"Person Relation Type",
		"Phone Type",
		"Position Type",
		"Prayer Request Status",
		"Prayer Request Type",
		"Sign-Up Item",
		"Visit Type",
	},
	"reference data that reads the same in every church": {
		"Bible Translation",
		"Missionary Agency",
	},
	"belongs to one person rather than one church": {
		"Bible Memory Item",
		"Memory Session",
	},
	"the church tree itself": {"Church"},
}

# Reads that carry no permission filter of their own. frappe.get_list is left
# out on purpose: it applies user permissions, so it is scoped already.
UNFILTERED_READS = ("frappe.get_all", "frappe.db.count", "frappe.qb.DocType")
# Calling one of these is what proves a read stays inside the reader's churches.
SCOPE_HELPERS = ("scoped", "church_filters", "church_query_filters", "selected_church_filters")
NOT_APP_CODE = ("/tests/", "/report/", "/patches/", "/setup/", "test_", "church_scope.py")

# Written above a read that cannot cross churches, with the reason why.
PRAGMA = "# church-scope:"


def excused(lines, tree, node):
	"""True when a scope pragma sits in the function holding *node*.

	The function is the unit, the same as for applying the scope: a query builder
	read names its table several lines above the call that restricts it, so
	demanding the comment sit on one exact line only moved the argument to
	whitespace. A module-level read answers to the module.
	"""
	return any(
		any(PRAGMA in line for line in lines[scope.lineno - 1 : scope.end_lineno])
		for scope in enclosing_scopes(tree, node)
		if isinstance(scope, ast.FunctionDef | ast.AsyncFunctionDef)
	) or any(PRAGMA in line for line in lines[node.lineno - 1 : node.end_lineno])


def enclosing_scopes(tree, node):
	"""The function bodies containing *node*, innermost first, then the module itself."""
	scopes = [
		parent
		for parent in ast.walk(tree)
		if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef)
		and parent.lineno <= node.lineno <= (parent.end_lineno or parent.lineno)
	]
	scopes.sort(key=lambda parent: parent.lineno, reverse=True)
	# Only a read outside every function answers to the module; otherwise one
	# scoped function in the file would vouch for all the others.
	return scopes or [tree]


def applies_the_scope(tree, node):
	"""True when a function around *node* hands its query to churchit.church_scope.

	A query builder read names its table on one line and restricts it several
	lines later, so the whole function is the unit, not the call. A closure may
	lean on the scope its enclosing function applied, so any scope around the
	read counts.
	"""
	return any(
		any(
			called_name(call.func).split(".")[-1] in SCOPE_HELPERS
			for call in ast.walk(scope)
			if isinstance(call, ast.Call)
		)
		for scope in enclosing_scopes(tree, node)
	)


def called_name(func):
	"""Dotted name of the thing being called, e.g. "frappe.get_all"."""
	parts = []
	while isinstance(func, ast.Attribute):
		parts.append(func.attr)
		func = func.value
	if isinstance(func, ast.Name):
		parts.append(func.id)
	return ".".join(reversed(parts))


def global_doctypes():
	return {name for names in GLOBAL_DOCTYPES.values() for name in names}


def app_python_files():
	"""Every python module of the app that is shipped behaviour, not a test or a one-off."""
	for root, _dirs, files in os.walk(APP_DIR):
		for name in files:
			path = os.path.join(root, name)
			if name.endswith(".py") and not any(part in path for part in NOT_APP_CODE):
				yield path


class TestScopedDoctypes(FrappeTestCase):
	def record_doctypes(self):
		"""App doctypes that hold records of their own: not child tables, not Singles."""
		return frappe.get_all(
			"DocType",
			filters={"module": ("in", frappe.get_module_list("churchit")), "istable": 0, "issingle": 0},
			pluck="name",
		)

	def test_every_record_doctype_is_scoped_or_declared_global(self):
		undeclared = sorted(set(self.record_doctypes()) - set(scoped_doctypes()) - global_doctypes())
		assert not undeclared, (
			"These doctypes store records but carry no `church` field, so every church sees "
			"all of them. Add the field (see AGENTS.md), or add them to GLOBAL_DOCTYPES with "
			"the reason they are shared: " + ", ".join(undeclared)
		)

	def test_the_global_list_has_no_stale_entries(self):
		gone = sorted(global_doctypes() - set(self.record_doctypes()))
		self.assertEqual(gone, [], "Global doctypes that no longer exist; drop them from the list")

	def test_every_shareable_doctype_is_scoped(self):
		"""Sharing widens a scope, so a doctype with no church has nothing to widen."""
		stray = sorted(set(SHAREABLE_DOCTYPES) - set(scoped_doctypes()))
		self.assertEqual(stray, [], "SHAREABLE_DOCTYPES names doctypes that carry no church field")

	def test_every_shareable_doctype_offers_the_checkbox(self):
		"""Without the field the record can never be shared, however it is listed."""
		missing = [
			doctype for doctype in SHAREABLE_DOCTYPES if not frappe.get_meta(doctype).has_field("is_shared")
		]
		self.assertEqual(missing, [], "Shareable doctypes with no `is_shared` field")

	def test_no_doctype_is_both_scoped_and_declared_global(self):
		both = sorted(global_doctypes() & set(scoped_doctypes()))
		self.assertEqual(both, [], "These carry a church field, so drop them from GLOBAL_DOCTYPES")


class TestScopedReads(FrappeTestCase):
	def unscoped_reads(self, path):
		"""Reads of a scoped doctype in *path* that neither scope nor excuse themselves.

		Parsed rather than grepped: these calls run to several lines, and the
		doctype is rarely on the same line as the call.

		The unit of proof is the function holding the read, not the file. A
		module that scopes one read used to wave through every other read in it,
		which is how an unscoped Budget lookup sat next to a scoped one.
		"""
		source = open(path).read()
		scoped = set(scoped_doctypes())
		lines = source.splitlines()
		tree = ast.parse(source)
		offenders = []
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call) or called_name(node.func) not in UNFILTERED_READS:
				continue
			if not (node.args and isinstance(node.args[0], ast.Constant)):
				continue
			if node.args[0].value not in scoped:
				continue
			if applies_the_scope(tree, node) or excused(lines, tree, node):
				continue
			offenders.append(node.lineno)
		return sorted(offenders)

	def test_every_unfiltered_read_of_a_scoped_doctype_applies_the_scope(self):
		"""frappe.qb, get_all and db.count carry no permission filter of their own.

		A new one over a church-scoped doctype has to go through
		churchit.church_scope, or carry a `# church-scope: <reason>` comment
		saying why it cannot cross churches.
		"""
		unscoped = []
		for path in app_python_files():
			for line in self.unscoped_reads(path):
				unscoped.append(f"{os.path.relpath(path, APP_DIR)}:{line}")
		assert not unscoped, (
			"These reads of church-scoped doctypes apply no scope. Scope them with "
			"churchit.church_scope, or write `# church-scope: <why it is safe>` above "
			"the call: " + ", ".join(sorted(unscoped))
		)

	def test_every_pragma_gives_a_reason(self):
		"""A bare marker would wave a read through without saying why."""
		bare = []
		for path in app_python_files():
			for number, line in enumerate(open(path).read().splitlines(), start=1):
				if PRAGMA in line and len(line.split(PRAGMA, 1)[1].strip()) < 15:
					bare.append(f"{os.path.relpath(path, APP_DIR)}:{number}")
		self.assertEqual(bare, [], "Scope pragmas that do not explain themselves")
