# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""AI code cannot skip the switch, the POST rule, rate limits, the Guest refusal or the read rules.

The rules read the source of churchit/ai/ and of every churchit/<module>/ai.py and ai_actions.py, the
places AI code lives. They follow direct calls only, so a person still reads what an AI function calls.
"""

import ast
import os
import tempfile

from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_doc_method_hygiene import (
	AppIndex,
	Function,
	Module,
	app_index,
	calls,
	dotted,
	is_truthy,
	is_whitelisted,
	keyword,
	last_name,
)
from churchit.tests.test_http_method_hygiene import accepted_verbs

SWITCH_CALLS = ("require_ai", "is_ai_on")
# Calls that start a model run or queue work. The function is a write and takes a rate limit.
RUN_CALLS = ("enqueue", "enqueue_doc", "run_agent", "start_run", "run_flow", "run_model", "ask_model")
# Calls that check the right to use the AI function or the record it names.
ROLE_CHECKS = ("only_for",)
RECORD_CHECKS = ("has_permission", "check_permission")
# Parameters that name a record.
RECORD_PARAMETERS = ("name", "docname", "doctype", "doc", "person", "church", "family", "record")
FORBIDDEN_CALLS = ("frappe.get_all", "frappe.db.get_all", "frappe.db.count", "frappe.db.sql", "frappe.qb")
LOG_METHODS = ("debug", "info", "warning", "error", "exception", "critical", "log_error")
SECRET_WORDS = ("prompt", "output", "completion", "response", "reply")

# (function, rule) that an AI function may break, and why.
EXEMPT = {
	("churchit.ai.exposure.get_exposure", "switch"): (
		"shows the AI switch itself, so it must work while AI is off; it asks for System Manager or "
		"Church Manager first"
	),
	("churchit.ai.flow_switch.use_recommended_knowledge_doctypes", "switch"): (
		"blocks doctypes from Flow knowledge, a protection that must work while AI is off; it asks for "
		"System Manager or Church Manager first"
	),
	("churchit.ai.flow_switch.use_recommended_knowledge_doctypes", "calls"): (
		"reads the doctype definitions (DocType, DocField and Custom Field) and never a record, to find "
		"the doctypes that hold data about people; a Church Manager cannot read DocType"
	),
	("churchit.church_people.ai.get_person_briefing", "post"): (
		"a read that writes only its Access Log row (AGENTS.md, Office reads); Frappe inserts it "
		"deferred, so a GET and MCP's rollback keep it"
	),
	("churchit.church_people.ai.get_group_briefing", "post"): (
		"a read that writes only its Access Log row (AGENTS.md, Office reads); Frappe inserts it "
		"deferred, so a GET and MCP's rollback keep it"
	),
}


def is_ai_module(module: Module) -> bool:
	"""True for churchit/ai/<file>.py, churchit/<module>/ai.py and churchit/<module>/ai_actions.py."""
	parts = module.name.split(".")
	if parts[:2] == ["churchit", "ai"]:
		return len(parts) > 2
	return len(parts) == 3 and parts[2] in ("ai", "ai_actions")


def whitelist_call(function: Function) -> ast.Call | None:
	return next(
		(
			decorator
			for decorator in function.node.decorator_list
			if isinstance(decorator, ast.Call) and last_name(decorator.func) == "whitelist"
		),
		None,
	)


def body_without_docstring(function: Function) -> list[ast.stmt]:
	body = function.node.body
	has_docstring = isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
	return body[1:] if has_docstring else body


def call_names(node) -> set[str]:
	return {last_name(call.func) for call in calls(node)}


def has_switch_first(function: Function) -> bool:
	"""The first statement after the docstring (and any role check) calls require_ai or is_ai_on."""
	for statement in body_without_docstring(function):
		if isinstance(statement, ast.Expr) and call_names(statement) <= set(ROLE_CHECKS):
			continue
		return bool(call_names(statement) & set(SWITCH_CALLS))
	return False


def refuses_website_users(function: Function) -> bool:
	"""It asks for roles (frappe.only_for) or reads the user type."""
	return bool(call_names(function.node) & set(ROLE_CHECKS)) or any(
		(isinstance(node, ast.Attribute) and node.attr == "user_type")
		or (isinstance(node, ast.Constant) and node.value == "user_type")
		for node in ast.walk(function.node)
	)


def checks_named_record(function: Function) -> bool:
	"""True when it names no record, or checks a right on one."""
	arguments = function.node.args
	named = {item.arg for item in [*arguments.args, *arguments.kwonlyargs]}
	if not named & set(RECORD_PARAMETERS):
		return True
	return bool(call_names(function.node) & set(RECORD_CHECKS)) or any(
		last_name(call.func) == "get_doc" and keyword(call, "check_permission") is not None
		for call in calls(function.node)
	)


def starts_work(function: Function) -> bool:
	return bool(call_names(function.node) & set(RUN_CALLS))


def has_rate_limit(function: Function) -> bool:
	return any(
		last_name(decorator.func if isinstance(decorator, ast.Call) else decorator) == "rate_limit"
		for decorator in function.node.decorator_list
	)


def function_problems(index: AppIndex, function: Function) -> set[str]:
	"""The rules of a whitelisted AI function that it breaks."""
	found = set()
	whitelist = whitelist_call(function)
	if whitelist is not None and is_truthy(keyword(whitelist, "allow_guest") or ast.Constant(False)):
		found.add("guest")
	if not has_switch_first(function):
		found.add("switch")
	if (index.summary(function).writes or starts_work(function)) and "GET" in accepted_verbs(function):
		found.add("post")
	if starts_work(function) and not has_rate_limit(function):
		found.add("rate_limit")
	if not refuses_website_users(function):
		found.add("user")
	if not checks_named_record(function):
		found.add("record")
	return found


def is_secret(node) -> bool:
	return isinstance(node, ast.Name) and any(word in node.id.lower() for word in SECRET_WORDS)


def is_log_call(call: ast.Call) -> bool:
	"""True for logger.info(...), frappe.logger().info(...) and frappe.log_error(...)."""
	name = last_name(call.func)
	if name == "log_error":
		return True
	receiver = call.func.value if isinstance(call.func, ast.Attribute) else None
	is_logger = isinstance(receiver, ast.Call) and last_name(receiver.func) == "logger"
	return name in LOG_METHODS and (is_logger or "log" in (dotted(call.func) or "").lower())


def breaks_read_rules(call: ast.Call) -> bool:
	name = dotted(call.func) or ""
	return name.startswith(FORBIDDEN_CALLS) or is_truthy(
		keyword(call, "ignore_permissions") or ast.Constant(0)
	)


def reachable(index: AppIndex, function: Function) -> list[Function]:
	"""The function and the AI functions it calls directly, however deep."""
	found, queue = [], [function]
	while queue:
		current = queue.pop()
		if current in found:
			continue
		found.append(current)
		queue += [
			target
			for call in calls(current.node)
			if (target := index.resolve(current, call)) is not None and is_ai_module(target.module)
		]
	return found


def code_problems(index: AppIndex, function: Function) -> set[str]:
	"""The read and logging rules that the function, or an AI function it calls, breaks."""
	found = set()
	for current in reachable(index, function):
		for call in calls(current.node):
			if breaks_read_rules(call):
				found.add("calls")
			if is_log_call(call) and any(is_secret(node) for item in call.args for node in ast.walk(item)):
				found.add("logging")
	return found


def ai_problems(index: AppIndex) -> dict[tuple[str, str], str]:
	"""Each broken (function, rule) of a whitelisted AI function, with where it is."""
	found = {}
	for function in index.functions():
		if is_ai_module(function.module) and is_whitelisted(function.node):
			for rule in function_problems(index, function) | code_problems(index, function):
				found[(f"{function.module.name}.{function.name}", rule)] = function.location
	return found


class TestAiFunctionsFollowTheRules(FrappeTestCase):
	"""Each whitelisted function in the AI code:

	- calls require_ai or is_ai_on first, so an AI function does nothing while AI is off;
	- takes methods=["POST"] when it writes, queues work or starts a model run, and carries
	  @rate_limit when it queues work or starts a run;
	- is no allow_guest and refuses Website Users (frappe.only_for or a user_type check);
	- checks permission on the record it names.

	It and the AI functions it calls read with no frappe.get_all, frappe.db.get_all, frappe.db.count,
	frappe.db.sql or frappe.qb and pass no ignore_permissions=True, and no logger call receives a
	prompt or output.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.problems = ai_problems(app_index())

	def test_the_ai_code_follows_the_rules(self):
		broken = sorted(
			f"{name} breaks {rule} ({where})"
			for (name, rule), where in self.problems.items()
			if (name, rule) not in EXEMPT
		)
		assert not broken, "AI code that breaks a rule, or add it to EXEMPT with the reason: " + "; ".join(
			broken
		)

	def test_every_exemption_is_still_needed(self):
		stale = [key for key in EXEMPT if key not in self.problems]
		self.assertEqual(stale, [], "EXEMPT lists a function or rule that no longer breaks the rule")


PLANTED_BAD = '''
import frappe


@frappe.whitelist(allow_guest=True)
def draft_letter(person, prompt):
	"""Reads only."""
	rows = frappe.get_all("Person")
	frappe.logger().info(prompt)
	frappe.enqueue("churchit.ai.letters.write")
	frappe.get_doc("Person", person).save(ignore_permissions=True)
'''

PLANTED_GOOD = '''
import frappe
from frappe.rate_limiter import rate_limit

from churchit.ai.switch import require_ai


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=5, seconds=60)
def draft_letter(person: str) -> None:
	"""Queues a draft. Changes data."""
	frappe.only_for(("Church Manager",))
	require_ai()
	frappe.get_doc("Person", person, check_permission="read")
	frappe.enqueue("churchit.ai.letters.write", person=person)
'''


class TestTheRulesFindABadFunction(FrappeTestCase):
	"""The rules fail on a planted bad function and pass on a good one."""

	def plant(self, source: str, name: str) -> tuple[AppIndex, Module]:
		with tempfile.TemporaryDirectory() as folder:
			path = os.path.join(folder, f"{name}.py")
			with open(path, "w") as file:
				file.write(source)
			module = Module(path)
		module.name = f"churchit.ai.{name}"
		index = AppIndex()
		index.modules[module.name] = module
		return index, module

	def found(self, source: str, name: str) -> set[str]:
		index, module = self.plant(source, name)
		return {rule for (item, rule) in ai_problems(index) if item.startswith(module.name)}

	def test_a_bad_function_breaks_every_rule(self):
		self.assertEqual(
			self.found(PLANTED_BAD, "planted_bad"),
			{"guest", "switch", "post", "rate_limit", "user", "record", "calls", "logging"},
		)

	def test_a_good_function_breaks_none(self):
		self.assertEqual(self.found(PLANTED_GOOD, "planted_good"), set())
