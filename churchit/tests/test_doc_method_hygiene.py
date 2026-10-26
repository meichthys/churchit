# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Whitelisted Document methods check the stored record before they write.

The source index here (`AppIndex`) is shared with test_permission_hygiene.py, which follows the
Person Note doctype through the same calls, and with test_http_method_hygiene.py, which uses its
write detection.
"""

import ast
import os
import tempfile
from dataclasses import dataclass, field
from functools import cache, cached_property

import frappe
from frappe.tests.utils import FrappeTestCase

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FUNCTIONS = ast.FunctionDef | ast.AsyncFunctionDef

# Whitelisted Document methods in which no write is found, and why they need no check. Calls on
# objects other than `self` and documents loaded by a written-out doctype are not followed, so a
# person confirms each one here.
READ_ONLY_METHODS = {
	"Budget.add_all_expense_types": "adds lines to the browser's copy; the user saves the form",
	"Budget.get_progress": "totals the expenses the budget tracks",
	"ChurchEmail.get_preview": "renders one copy of the message for the reader to look at",
	"ChurchEmail.get_recipient_count": "counts the people the message would go to",
	"Missionary.add_family": "adds rows to the browser's copy; the user saves the form",
}

UNCHECKED, CHECKED = "unchecked", "checked"
# Rights that only read. A check for one of these does not cover a write.
READ_RIGHTS = ("read", "select")
READ = ast.Constant("read")
# frappe.only_for checks roles, which no field of the browser's copy can change.
ROLE_CHECK = ast.Constant("roles")
# Writes Frappe checks itself, against the document being written, as it does a REST update.
CHECKED_WRITES = ("save", "insert", "submit", "cancel", "delete", "delete_doc", "rename_doc")
# Calls that change or send with no check of their own, by the last part of their name.
UNCHECKED_CALLS = (
	"db_set",
	"db_insert",
	"db_update",
	"add_comment",
	"sendmail",
	"send_sms",
	"enqueue",
	"enqueue_doc",
	"set_user_default",
	"clear_user_default",
	"update_password",
	"make_access_log",
)
# The same for frappe.db and frappe.qb, by the end of the dotted name.
UNCHECKED_DB = (
	"db.set_value",
	"db.set_single_value",
	"db.delete",
	"db.truncate",
	"db.bulk_insert",
	"db.bulk_update",
	"qb.update",
	"qb.into",
)
QB_WRITES = ("update", "into", "insert", "delete")
RAW_SQL = ("frappe.db.sql", "frappe.db.multisql", "frappe.db.sql_list")
SQL_WRITES = ("insert", "update", "delete", "replace", "truncate", "alter", "drop")
# Calls that take ignore_permissions and still only read.
READ_CALLS = (
	"get_list",
	"get_all",
	"get_value",
	"get_values",
	"get_doc",
	"get_cached_doc",
	"get_count",
	"count",
	"exists",
	"has_permission",
)
# Flags that switch Frappe's own checks off for every later save of a document.
OVERRIDE_FLAGS = ("ignore_permissions", "ignore_share_permission")
# Calls that load a document of the doctype they are given first.
DOCUMENT_LOADERS = ("frappe.get_doc", "frappe.get_cached_doc", "frappe.get_single", "frappe.new_doc")


def dotted(node) -> str | None:
	"""`a.b.c` for a name or an attribute chain on a name, else None (a chain hanging off a call)."""
	parts = []
	while isinstance(node, ast.Attribute):
		parts.append(node.attr)
		node = node.value
	if not isinstance(node, ast.Name):
		return None
	parts.append(node.id)
	return ".".join(reversed(parts))


def last_name(node) -> str:
	return node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")


def is_truthy(node) -> bool:
	"""False only for a literal False, 0 or None: a value worked out at run time may be on."""
	return not (isinstance(node, ast.Constant) and not node.value)


def is_self(node) -> bool:
	return isinstance(node, ast.Name) and node.id == "self"


def keyword(call: ast.Call, name: str):
	return next((item.value for item in call.keywords if item.arg == name), None)


def argument(call: ast.Call, position: int, name: str):
	return call.args[position] if len(call.args) > position else keyword(call, name)


def calls(node):
	return (inner for inner in ast.walk(node) if isinstance(inner, ast.Call))


def shipped_python_files():
	"""Every python module of the app except its tests."""
	for root, _dirs, files in os.walk(APP_DIR):
		if "/tests" in root[len(APP_DIR) :]:
			continue
		for name in files:
			if name.endswith(".py") and not name.startswith("test_"):
				yield os.path.join(root, name)


def is_whitelisted(node) -> bool:
	return any(
		last_name(decorator.func if isinstance(decorator, ast.Call) else decorator) == "whitelist"
		for decorator in node.decorator_list
	)


def overrides_checks(call: ast.Call) -> bool:
	"""True when *call* passes ignore_permissions, or flags that switch a check off."""
	if is_truthy(keyword(call, "ignore_permissions") or ast.Constant(None)):
		return True
	flags = keyword(call, "flags")
	return isinstance(flags, ast.Dict) and any(
		isinstance(key, ast.Constant) and key.value in OVERRIDE_FLAGS and is_truthy(value)
		for key, value in zip(flags.keys, flags.values, strict=True)
	)


def switches_checks_off(node) -> bool:
	"""True for `doc.flags.ignore_permissions = True` and the like."""
	return (
		isinstance(node, ast.Assign)
		and any(
			isinstance(target, ast.Attribute) and target.attr in OVERRIDE_FLAGS for target in node.targets
		)
		and is_truthy(node.value)
	)


def changes_rows(call: ast.Call) -> bool:
	"""True for raw SQL written out as a statement that changes rows."""
	statement = call.args[0] if call.args else None
	if isinstance(statement, ast.JoinedStr):
		text = "".join(part.value for part in statement.values if isinstance(part, ast.Constant))
	else:
		text = statement.value if isinstance(statement, ast.Constant) else ""
	return str(text).lstrip().lower().startswith(SQL_WRITES)


def grants_write(right) -> bool:
	"""True for a right other than read; a right worked out at run time is given the benefit of the doubt."""
	if right is None:
		return False
	if isinstance(right, ast.Constant):
		return isinstance(right.value, str) and right.value not in READ_RIGHTS
	return True


def stored_check_right(call: ast.Call, reloads: list[int]):
	"""The right *call* checks on a record loaded from the database, or None when it checks no stored record.

	`self` is the browser's copy unless `self.reload()` or `self.load_from_db()` ran first.
	"""
	name = last_name(call.func)
	if dotted(call.func) == "frappe.only_for":
		return ROLE_CHECK
	if name == "get_doc":
		return keyword(call, "check_permission")
	if name not in ("check_permission", "has_permission"):
		return None
	receiver = call.func.value if isinstance(call.func, ast.Attribute) else None
	if receiver is None or (dotted(receiver) or "").startswith("frappe"):
		document = argument(call, 2, "doc")
		return argument(call, 1, "ptype") or READ if document is not None and not is_self(document) else None
	if is_self(receiver) and not any(line < call.lineno for line in reloads):
		return None
	return argument(call, 0, "permtype") or READ


def parameter_names(node) -> list[str]:
	return [arg.arg for arg in (*node.args.args, *node.args.kwonlyargs)]


def passed_argument(function: "Function", call: ast.Call, parameter: str):
	"""What *call* passes to *function* as *parameter*, or None."""
	positional = [arg.arg for arg in function.node.args.args]
	passed = keyword(call, parameter)
	if passed is None and parameter in positional:
		position = positional.index(parameter) - bool(function.owner)
		passed = call.args[position] if 0 <= position < len(call.args) else None
	return passed


class Module:
	"""One python file of the app: its imports, functions, classes and module constants."""

	def __init__(self, path: str):
		self.relative = os.path.relpath(path, APP_DIR)
		self.name = ".".join(["churchit", *self.relative[:-3].split(os.sep)]).removesuffix(".__init__")
		self.package = self.name.split(".") if path.endswith("__init__.py") else self.name.split(".")[:-1]
		with open(path) as source:
			self.tree = ast.parse(source.read())
		self.functions = {node.name: node for node in self.tree.body if isinstance(node, FUNCTIONS)}
		self.classes = {node.name: node for node in self.tree.body if isinstance(node, ast.ClassDef)}
		self.constants = {
			target.id: node.value
			for node in self.tree.body
			if isinstance(node, ast.Assign)
			for target in node.targets
			if isinstance(target, ast.Name)
		}
		self.imports = dict(self.read_imports())

	def read_imports(self):
		"""(local name, dotted target) for each import, relative ones made absolute."""
		for node in ast.walk(self.tree):
			if isinstance(node, ast.Import):
				for alias in node.names:
					yield (alias.asname, alias.name) if alias.asname else (alias.name.split(".")[0],) * 2
			elif isinstance(node, ast.ImportFrom):
				base = node.module or ""
				if node.level:
					base = ".".join(filter(None, [*self.package[: len(self.package) - node.level + 1], base]))
				for alias in node.names:
					yield alias.asname or alias.name, f"{base}.{alias.name}"

	def expand(self, name: str) -> str:
		"""*name* as written here, with its first part replaced by what it was imported as."""
		head, _, rest = name.partition(".")
		target = self.imports.get(head, head)
		return f"{target}.{rest}" if rest else target


@dataclass(frozen=True)
class Function:
	module: Module
	node: ast.FunctionDef
	owner: ast.ClassDef | None = None

	@property
	def name(self) -> str:
		return f"{self.owner.name}.{self.node.name}" if self.owner else self.node.name

	@property
	def location(self) -> str:
		return f"{self.module.relative}:{self.node.lineno}"


@dataclass
class Summary:
	"""What a function does, counting the app functions it calls."""

	exposed: list[str] = field(default_factory=list)
	writes: bool = False
	# It checks a writing right on the stored record, or the right its caller passes in these parameters.
	checks: bool = False
	checks_parameters: set[str] = field(default_factory=set)


class AppIndex:
	"""The app's shipped modules, and the calls between their functions that resolve by name."""

	def __init__(self):
		self.modules = {module.name: module for module in map(Module, shipped_python_files())}
		self.summaries: dict[Function, Summary] = {}
		self.documents: dict[Function, dict[str, tuple[Module, ast.ClassDef]]] = {}

	def functions(self):
		for module in self.modules.values():
			for node in module.functions.values():
				yield Function(module, node)
			for owner in module.classes.values():
				for node in owner.body:
					if isinstance(node, FUNCTIONS):
						yield Function(module, node, owner)

	def find_class(self, module: Module, node) -> tuple[Module, ast.ClassDef] | None:
		name = dotted(node)
		if not name:
			return None
		if name in module.classes:
			return module, module.classes[name]
		owner_name, _, class_name = module.expand(name).rpartition(".")
		owner = self.modules.get(owner_name)
		return (owner, owner.classes[class_name]) if owner and class_name in owner.classes else None

	def method(self, owner: tuple[Module, ast.ClassDef], name: str) -> Function | None:
		module, classdef = owner
		for node in classdef.body:
			if isinstance(node, FUNCTIONS) and node.name == name:
				return Function(module, node, classdef)
		for base in classdef.bases:
			parent = self.find_class(module, base)
			if parent and (found := self.method(parent, name)):
				return found
		return None

	@cached_property
	def controllers(self) -> dict[str, Module]:
		"""Each doctype's controller module, `doctype/<name>/<name>.py`, by its scrubbed doctype name."""
		found = {}
		for module in self.modules.values():
			parts = module.name.split(".")
			if len(parts) > 3 and parts[-3] == "doctype" and parts[-2] == parts[-1]:
				found[parts[-1]] = module
		return found

	def constant(self, module: Module, name: str) -> tuple[Module | None, ast.expr | None]:
		"""(module, value) of the module constant *name* stands for in *module*, or (None, None)."""
		if name in module.constants:
			return module, module.constants[name]
		owner_name, _, constant = module.imports.get(name, "").rpartition(".")
		owner = self.modules.get(owner_name)
		return (owner, owner.constants[constant]) if owner and constant in owner.constants else (None, None)

	def controller(self, module: Module, call: ast.Call) -> tuple[Module, ast.ClassDef] | None:
		"""The controller class of the document *call* loads, as `frappe.get_doc("Group", name)` does."""
		if module.expand(dotted(call.func) or "") not in DOCUMENT_LOADERS:
			return None
		doctype = argument(call, 0, "doctype")
		if isinstance(doctype, ast.Name):
			doctype = self.constant(module, doctype.id)[1]
		if not (isinstance(doctype, ast.Constant) and isinstance(doctype.value, str)):
			return None
		owner = self.controllers.get(frappe.scrub(doctype.value))
		class_name = doctype.value.replace(" ", "").replace("-", "")
		return (owner, owner.classes[class_name]) if owner and class_name in owner.classes else None

	def loaded_documents(self, function: Function) -> dict[str, tuple[Module, ast.ClassDef]]:
		"""Names *function* binds to a loaded document, as `doc = frappe.get_doc("Group", name)`, with its class."""
		if function not in self.documents:
			found = {}
			for node in ast.walk(function.node):
				if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
					continue
				owner = self.controller(function.module, node.value)
				for target in node.targets:
					if owner and isinstance(target, ast.Name):
						found[target.id] = owner
			self.documents[function] = found
		return self.documents[function]

	def receiver_class(self, caller: Function, node) -> tuple[Module, ast.ClassDef] | None:
		"""The app class of the object a method is called on: `self`, `Class(...)` or a loaded document."""
		if is_self(node):
			return (caller.module, caller.owner) if caller.owner else None
		if isinstance(node, ast.Call):
			return self.find_class(caller.module, node.func) or self.controller(caller.module, node)
		return self.loaded_documents(caller).get(node.id) if isinstance(node, ast.Name) else None

	def resolve(self, caller: Function, call: ast.Call) -> Function | None:
		"""The app function *call* runs: `self.x()`, `f()`, `module.f()`, `Class.x()`, `Class(...).x()`, or
		`doc.x()` on a document loaded by a written-out doctype."""
		func, module = call.func, caller.module
		if isinstance(func, ast.Attribute) and (owner := self.receiver_class(caller, func.value)):
			return self.method(owner, func.attr)
		name = dotted(func)
		if not name:
			return None
		head, _, rest = name.partition(".")
		if not rest and head in module.functions:
			return Function(module, module.functions[head])
		owner_name, _, function_name = module.expand(name).rpartition(".")
		if owner := self.modules.get(owner_name):
			return (
				Function(owner, owner.functions[function_name]) if function_name in owner.functions else None
			)
		owner_module, _, class_name = owner_name.rpartition(".")
		classes = getattr(self.modules.get(owner_module), "classes", {})
		if class_name in classes:
			return self.method((self.modules[owner_module], classes[class_name]), function_name)
		if head in module.classes and "." not in rest:
			return self.method((module, module.classes[head]), rest)
		return None

	def write_kind(self, function: Function, call: ast.Call, switched_off: bool) -> str | None:
		"""UNCHECKED for a call that writes or sends unchecked, CHECKED for a write Frappe checks itself."""
		name = last_name(call.func)
		target = function.module.expand(dotted(call.func) or "")
		if overrides_checks(call):
			return None if name in READ_CALLS else UNCHECKED
		if name in UNCHECKED_CALLS or target.endswith(UNCHECKED_DB):
			return UNCHECKED
		if name in QB_WRITES and "qb." in ast.unparse(call.func):
			return UNCHECKED
		if target in RAW_SQL:
			return UNCHECKED if changes_rows(call) else None
		if name == "insert" and len(call.args) == 2:
			return None  # list.insert(index, item)
		if name in CHECKED_WRITES:
			return UNCHECKED if switched_off else CHECKED
		return None

	def summary(self, function: Function, trail: tuple = ()) -> Summary:
		"""The unchecked writes *function* makes before it checks the stored record, and whether it writes."""
		if function in self.summaries:
			return self.summaries[function]
		if function in trail:
			return Summary()
		node = function.node
		switched_off = any(switches_checks_off(inner) for inner in ast.walk(node))
		reloads = [
			call.lineno for call in calls(node) if dotted(call.func) in ("self.reload", "self.load_from_db")
		]
		result, unchecked, checks = Summary(), [], []
		for call in calls(node):
			kind = self.write_kind(function, call, switched_off)
			result.writes = result.writes or bool(kind)
			if kind == UNCHECKED:
				unchecked.append((call.lineno, f"{ast.unparse(call.func)} (line {call.lineno})"))
			right = stored_check_right(call, reloads)
			if isinstance(right, ast.Name) and right.id in parameter_names(node):
				result.checks_parameters.add(right.id)
				checks.append(call.lineno)
			elif grants_write(right):
				result.checks = True
				checks.append(call.lineno)
			callee = self.resolve(function, call)
			if not callee or callee == function:
				continue
			inner = self.summary(callee, (*trail, function))
			result.writes = result.writes or inner.writes
			if inner.exposed:
				unchecked.append((call.lineno, f"{callee.name} ({callee.location}) {inner.exposed[0]}"))
			passed = [passed_argument(callee, call, parameter) for parameter in inner.checks_parameters]
			if inner.checks or any(grants_write(right) for right in passed):
				result.checks = True
				checks.append(call.lineno)
		first_check = min(checks, default=None)
		result.exposed = [
			text for line, text in sorted(unchecked) if first_check is None or line < first_check
		]
		self.summaries[function] = result
		return result


@cache
def app_index() -> AppIndex:
	return AppIndex()


class TestWhitelistedDocumentMethods(FrappeTestCase):
	"""A whitelisted Document method that writes checks the right on the stored record first.

	Frappe's `run_doc_method` checks only read before it runs the method, and with `docs=` it
	builds the document from the browser's JSON: `name`, `church`, `owner` and `user` included,
	and `__islocal` skips the timestamp check. So `self.check_permission("write")` checks a copy
	the caller filled in to pass it, and a `has_permission` hook that reads a field of it says yes.

	How the test decides, per method, following the app functions it calls by name (`self.x()`,
	`f()`, `module.f()`, `Class(...).x()`, and `doc.x()` where `doc = frappe.get_doc("Group", ...)`
	names its doctype; calls on other objects are not followed, which is why a method with no
	write found must be listed in READ_ONLY_METHODS):

	- An unchecked write changes or sends with no check of its own: `db_set`, `db_insert`,
	  `db_update`, `frappe.db.set_value`, `db.delete` and the other `frappe.db` writers, raw SQL
	  that starts with a writing statement, `frappe.qb` updates, inserts and deletes,
	  `add_comment`, `sendmail`, `send_sms`, `enqueue`, `enqueue_doc`, `set_user_default`,
	  `update_password`, `make_access_log`, and any call given `ignore_permissions` (or ignore
	  flags) that is not a read.
	- `save`, `insert`, `submit`, `cancel`, `delete`, `delete_doc` and `rename_doc` are checked
	  by Frappe against the document they write, as a REST update is, so they need nothing more,
	  unless the function sets `flags.ignore_permissions`. `items.insert(index, item)` on a list
	  is no write.
	- A check is `frappe.only_for`, or `check_permission`/`has_permission` for a right other than
	  read on a record loaded from the database: `frappe.get_doc(self.doctype, self.name)`,
	  `has_permission(..., doc=self.name)`, or `self` after `self.reload()`. A call to an app
	  helper that makes such a check counts too, with the right the caller passes it. Only
	  unchecked writes before the first check count.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.index = app_index()
		cls.methods = [
			function for function in cls.index.functions() if function.owner and is_whitelisted(function.node)
		]

	def test_a_method_that_writes_checks_the_stored_record_first(self):
		unchecked = [
			f"{method.location} {method.name}: {'; '.join(summary.exposed)}"
			for method in self.methods
			if (summary := self.index.summary(method)).exposed
		]
		assert not unchecked, (
			"These whitelisted Document methods write without checking the stored record first. "
			"Frappe checked only read, on the browser's copy. Start them with "
			'`frappe.get_doc(self.doctype, self.name).check_permission("write")` (or the right they '
			"need): " + " | ".join(sorted(unchecked))
		)

	def test_a_method_that_writes_nothing_is_declared_read_only(self):
		undeclared = [
			f"{method.location} {method.name}"
			for method in self.methods
			if not self.index.summary(method).writes and method.name not in READ_ONLY_METHODS
		]
		assert not undeclared, (
			"No write was found in these whitelisted Document methods. If they only read, add them "
			"to READ_ONLY_METHODS with the reason; if they write, check the stored record first: "
			+ ", ".join(sorted(undeclared))
		)

	def test_every_read_only_method_exists_and_writes_nothing(self):
		methods = {method.name: method for method in self.methods}
		stale = [
			name
			for name in READ_ONLY_METHODS
			if name not in methods or self.index.summary(methods[name]).writes
		]
		self.assertEqual(stale, [], "READ_ONLY_METHODS lists methods that are gone or now write")


# Calls that read or write the record their second argument names, with that argument's keyword.
NAME_READERS = {
	"frappe.get_doc": "name",
	"frappe.get_cached_doc": "name",
	"frappe.db.get_value": "filters",
	"frappe.db.set_value": "dn",
	"frappe.db.exists": "dn",
}
LIST_READERS = ("frappe.get_list",)

# Whitelisted functions that take a record name and check no permission on that record, and why they
# need none. Keyed by the dotted path a client calls.
SIGNED_LINK = "a signed email link: verify_request checks the signature over every parameter first"
TRANSLATION = "scripture.is_readable is the read rule for a Bible Translation: Free Use text is public"
OWN_RECORD = "a portal member holds no right on it; it refuses a record that is not the session's own"
NAME_CHECK_EXEMPT = {
	"churchit.church_communications.consent.renew_consent": SIGNED_LINK,
	"churchit.church_communications.newsletter.unsubscribe": SIGNED_LINK,
	"churchit.church_communications.doctype.bulletin.bulletin.download_pdf": (
		"Frappe's download_pdf checks print permission on the bulletin before the date is read"
	),
	"churchit.church_communications.preferences.set_preference": (
		"Communication Purpose is a global lookup; only its existence is read"
	),
	"churchit.church_ministries.member_attendance.change_own_attendance": (
		"it loads only a function on the session member's own Attendance page"
	),
	"churchit.church_ministries.member_ministry_team.answer_own_assignment": OWN_RECORD,
	"churchit.church_ministries.member_ministry_team.remove_own_block": OWN_RECORD,
	"churchit.church_ministries.page.check_in.check_in.add_visitor": (
		"Check-In reads every family; it refuses a family whose church the user cannot see (has_church_access)"
	),
	"churchit.church_ministries.pre_check_in.get_pre_check_in_code": (
		"a member signs only an open self check-in Function of their church (get_functions on session_church), "
		"for people they may write"
	),
	"churchit.church_missions.doctype.missionary.missionary.get_country_coordinates": (
		"Country is Frappe's global reference data"
	),
	"churchit.church_people.group_api.join_group": (
		"a member joins only a public portal group of their church (church_filters on session_church)"
	),
	"churchit.church_people.group_api.message_group": (
		"a portal leader holds no right on the Group; require_leader refuses anyone who does not lead it"
	),
	"churchit.church_people.group_meetings.record_group_attendance": (
		"it reads the Function only for its group; require_leader refuses anyone who does not lead that "
		"group, and only that group's people are written"
	),
	"churchit.church_people.list_actions.mark_inactive": (
		"Inactive Reason is a global lookup; each Person is checked for write"
	),
	"churchit.church_setup.doctype.form_response.form_response.pay": (
		"the response name is a random hash that only its sender's page holds, and it gives only a checkout of "
		"the set's own price"
	),
	"churchit.church_setup.doctype.form_response.form_response.get_form": (
		"a guest read; refuse_a_closed_form gives the questions only of a set published as a form, and "
		"refuses a guest a members-only set"
	),
	"churchit.church_study.doctype.bible_memory_item.bible_memory_item.assign_memory": TRANSLATION,
	"churchit.church_study.doctype.bible_memory_item.bible_memory_item.record_mistake": OWN_RECORD,
	"churchit.church_study.doctype.bible_memory_item.bible_memory_item.complete_session": OWN_RECORD,
	"churchit.ics.get_public_calendar": (
		"a guest feed; it lists a ministry's Functions only when the Ministry is published"
	),
	"churchit.scripture.get_books": TRANSLATION,
	"churchit.scripture.get_chapter": TRANSLATION,
	"churchit.scripture.get_passage": TRANSLATION,
	"churchit.scripture.get_reference_preview": TRANSLATION,
	"churchit.www.give.start_donation": "a guest may give to any fund with Allow Giving; the gift takes the fund's church",
	"churchit.www.register.pay": SIGNED_LINK,
	"churchit.www.register.get_questions": (
		"a guest read; it gives the questions only of a published Function of the selected church with guest "
		"sign-ups open now (get_open_functions)"
	),
	"churchit.www.register.sign_up": (
		"a guest registers only for a published Function of the selected church with guest sign-ups open now "
		"(get_open_functions); the sign-up takes the function's church"
	),
	"churchit.www.register.get_event_calendar": (
		"a guest feed; it gives the calendar only of a function /register offers (get_open_functions)"
	),
}


def named_parameter(node) -> str | None:
	"""The variable a name argument is: `name`, or `{"name": name}`."""
	if isinstance(node, ast.Dict):
		node = next(
			(
				value
				for key, value in zip(node.keys, node.values, strict=True)
				if isinstance(key, ast.Constant) and key.value == "name"
			),
			None,
		)
	return node.id if isinstance(node, ast.Name) else None


@dataclass
class NameUse:
	"""Per parameter, the first line it names a record unchecked, and the first line it is checked."""

	used: dict[str, int] = field(default_factory=dict)
	checked: dict[str, int] = field(default_factory=dict)

	def note(self, lines: dict[str, int], parameter: str | None, line: int):
		if parameter:
			lines[parameter] = min(line, lines.get(parameter, line))

	def is_unchecked(self, parameter: str) -> bool:
		used = self.used.get(parameter)
		return used is not None and used < self.checked.get(parameter, used + 1)

	def is_checked(self, parameter: str) -> bool:
		checked = self.checked.get(parameter)
		return checked is not None and checked <= self.used.get(parameter, checked)


class RecordNames:
	"""Follows the parameters of app functions into the record names they read and the checks they make."""

	def __init__(self, index: AppIndex):
		self.index = index
		self.uses: dict[Function, NameUse] = {}

	def loads(self, function: Function) -> dict[str, tuple[str, int]]:
		"""`doc = frappe.get_doc("X", name)`: the variable, with the parameter and the line it loads."""
		found = {}
		for node in ast.walk(function.node):
			if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
				parameter = self.named(function.module, node.value)
				for target in node.targets:
					if parameter and isinstance(target, ast.Name):
						found[target.id] = (parameter, node.lineno)
		return found

	def named(self, module: Module, call: ast.Call) -> str | None:
		"""The variable *call* passes as a record name to one of NAME_READERS."""
		keyword_name = NAME_READERS.get(module.expand(dotted(call.func) or ""))
		return named_parameter(argument(call, 1, keyword_name)) if keyword_name else None

	def checked_variable(self, module: Module, call: ast.Call) -> str | None:
		"""The record variable a permission check is on, or None for a call that checks no record."""
		name, receiver = last_name(call.func), getattr(call.func, "value", None)
		if name not in ("check_permission", "has_permission"):
			return None
		if receiver is None or (dotted(receiver) or "").startswith("frappe"):
			return named_parameter(argument(call, 2, "doc"))
		if isinstance(receiver, ast.Call):
			return self.named(module, receiver)
		return receiver.id if isinstance(receiver, ast.Name) else None

	def use(self, function: Function, trail: tuple = ()) -> NameUse:
		if function in self.uses:
			return self.uses[function]
		if function in trail:
			return NameUse()
		result, module, loads = NameUse(), function.module, self.loads(function)
		checks = [(self.checked_variable(module, call), call) for call in calls(function.node)]
		checked_loads = {variable for variable, _call in checks if variable in loads}
		load_calls = {id(node.value) for node in ast.walk(function.node) if isinstance(node, ast.Assign)}
		for variable, call in checks:
			result.note(result.checked, loads.get(variable, (variable,))[0], call.lineno)
			if module.expand(dotted(call.func) or "") in LIST_READERS:
				for inner in ast.walk(call):
					result.note(result.checked, getattr(inner, "id", None), call.lineno)
			parameter = self.named(module, call)
			if parameter and id(call) not in load_calls and not self.is_checked_receiver(call, checks):
				result.note(result.used, parameter, call.lineno)
			self.follow(function, call, result, (*trail, function))
		for variable, (parameter, line) in loads.items():
			if variable not in checked_loads:
				result.note(result.used, parameter, line)
		self.uses[function] = result
		return result

	def is_checked_receiver(self, call: ast.Call, checks) -> bool:
		"""True for the `frappe.get_doc(...)` of `frappe.get_doc(...).check_permission(...)`."""
		return any(getattr(check.func, "value", None) is call for _variable, check in checks)

	def follow(self, function: Function, call: ast.Call, result: NameUse, trail: tuple):
		"""Count what an app function called here does with the names passed to it."""
		callee = self.index.resolve(function, call)
		if not callee or callee == function:
			return
		inner = self.use(callee, trail)
		for parameter in parameter_names(callee.node):
			passed = named_parameter(passed_argument(callee, call, parameter))
			if inner.is_checked(parameter):
				result.note(result.checked, passed, call.lineno)
			elif inner.is_unchecked(parameter):
				result.note(result.used, passed, call.lineno)


class TestWhitelistedFunctionsCheckTheNamedRecord(FrappeTestCase):
	"""A module-level whitelisted function checks permission on a record the caller names.

	Frappe checks nothing before such a function runs, and `frappe.get_doc`, `frappe.db.get_value`
	and the like check nothing either. So a parameter that becomes the record name of
	`frappe.get_doc`, `get_cached_doc`, `db.get_value`, `db.set_value` or `db.exists` (as the name or
	as `{"name": ...}`) is first checked: `has_permission(..., doc=name)`,
	`has_permission(doctype, ptype, name)`, `check_permission(...)` on the document it loads
	(`doc = frappe.get_doc("X", name)` and then `doc.check_permission(...)`), or `frappe.get_list`.
	App functions it is passed to are followed by name, with the checks and the reads they make.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.index = app_index()
		cls.names = RecordNames(cls.index)
		cls.functions = {
			f"{function.module.name}.{function.name}": function
			for function in cls.index.functions()
			if not function.owner and is_whitelisted(function.node)
		}

	def unchecked(self, function: Function) -> list[str]:
		use = self.names.use(function)
		return [parameter for parameter in parameter_names(function.node) if use.is_unchecked(parameter)]

	def test_a_function_checks_the_record_it_is_given(self):
		unchecked = [
			f"{function.location} {path}({', '.join(parameters)})"
			for path, function in self.functions.items()
			if path not in NAME_CHECK_EXEMPT and (parameters := self.unchecked(function))
		]
		assert not unchecked, (
			"These whitelisted functions read or change a record whose name the caller sent, without "
			'checking it first. Add `frappe.has_permission("<DocType>", doc=name, throw=True)`, or add '
			"them to NAME_CHECK_EXEMPT with the reason: " + " | ".join(sorted(unchecked))
		)

	def test_every_exemption_names_a_function_that_still_needs_it(self):
		stale = [
			path
			for path in NAME_CHECK_EXEMPT
			if path not in self.functions or not self.unchecked(self.functions[path])
		]
		self.assertEqual(stale, [], "NAME_CHECK_EXEMPT lists functions that are gone or now check")

	def test_an_unchecked_record_name_is_found(self):
		source = (
			"import frappe\n"
			"@frappe.whitelist()\n"
			"def unchecked(function):\n"
			'	return frappe.get_doc("Function", function).title\n'
			"@frappe.whitelist()\n"
			"def checked(function):\n"
			'	frappe.has_permission("Function", doc=function, throw=True)\n'
			'	return frappe.db.get_value("Function", function, "title")\n'
		)
		with tempfile.NamedTemporaryFile("w", suffix=".py") as file:
			file.write(source)
			file.flush()
			module = Module(file.name)
		names = RecordNames(self.index)

		unchecked = names.use(Function(module, module.functions["unchecked"]))
		checked = names.use(Function(module, module.functions["checked"]))

		self.assertTrue(unchecked.is_unchecked("function"))
		self.assertFalse(checked.is_unchecked("function"))
