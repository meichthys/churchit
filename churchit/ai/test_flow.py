# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit runs on a Frappe with Flow, Frappe's AI agents, and on one without it (Frappe 16).

churchit/ai/flow.py is the only module that uses frappe.flow, so Flow's API (0.1.x, and it changes
often) is used in one file. Only Flow's own hooks, which a Frappe without Flow never reads, and code
that has checked switch.has_flow() load that file, so a Frappe without Flow never imports frappe.flow.
"""

import ast
import importlib
import importlib.util
import re
from functools import cache
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

import churchit
from churchit.ai.flow_models import is_flow_ready
from churchit.ai.switch import has_flow
from churchit.tests.helpers import RollbackEachTest

PACKAGE = Path(churchit.__file__).parent
FLOW_MODULE = "churchit.ai.flow"
FLOW_FILE = PACKAGE / "ai" / "flow.py"
# The hooks that only Flow reads (frappe/flow/lib/agent.py and trigger.py on Frappe develop).
FLOW_HOOKS = ("flow_agents", "flow_tools", "flow_triggers")
IMPORT_CALLS = ("import_module", "__import__", "get_attr")
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


class TestChurchitWithOrWithoutFlow(FrappeTestCase):
	def test_only_the_flow_module_uses_frappe_flow(self):
		users = [
			module
			for module, path in get_modules()
			if path != FLOW_FILE and any(is_within(name, "frappe.flow") for name, _ in get_references(path))
		]

		self.assertEqual(users, [], "Use frappe.flow only in churchit/ai/flow.py.")

	def test_no_module_loads_the_flow_module_when_it_loads(self):
		loaders = [
			module
			for module, path in get_modules()
			if any(is_within(name, FLOW_MODULE) and at_load for name, at_load in get_references(path))
		]

		self.assertEqual(loaders, [], "Load churchit.ai.flow inside a function, after switch.has_flow().")

	def test_only_flows_own_hooks_name_the_flow_module(self):
		flow_module = re.compile(rf"\b{re.escape(FLOW_MODULE)}\b")
		hooks = frappe.get_hooks(app_name="churchit")

		named = [
			hook
			for hook, value in hooks.items()
			if hook not in FLOW_HOOKS and flow_module.search(repr(value))
		]

		self.assertEqual(named, [], "A Frappe without Flow would load churchit.ai.flow through these hooks.")

	def test_every_module_loads_on_this_frappe(self):
		failures = []
		for module, _path in get_modules():
			if module == FLOW_MODULE and not has_flow():
				continue
			try:
				importlib.import_module(module)
			except Exception as error:
				failures.append(f"{module}: {error!r}")

		self.assertEqual(failures, [])

	def test_has_flow_tells_whether_this_frappe_ships_flow(self):
		self.assertEqual(has_flow(), importlib.util.find_spec("frappe.flow") is not None)

	def test_flow_reads_churchits_agents_from_the_hook(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")

		self.assertIn(f"{FLOW_MODULE}.agents", frappe.get_hooks("flow_agents"))
		self.assertIsInstance(frappe.get_attr(f"{FLOW_MODULE}.agents")(), list)


class TestFlowReady(RollbackEachTest):
	"""test_flow_agents shows that Flow is ready once its sync writes the agents."""

	def setUp(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")
		super().setUp()
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)

	def test_flow_is_not_ready_without_an_enabled_chat_model(self):
		self.assertFalse(is_flow_ready())

		# db_insert: a saved model sets up Flow's Assistant and may ask its provider about itself.
		model = {"doctype": "Flow Model", "title": "_Test Flow Model", "model_id": "_test", "enabled": 1}
		frappe.get_doc({**model, "embedding": 1}).db_insert()
		self.assertFalse(is_flow_ready())


def get_modules() -> list[tuple[str, Path]]:
	"""Every module in the churchit package, www pages included (www has no __init__.py)."""
	modules = []
	for path in sorted(PACKAGE.rglob("*.py")):
		parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
		modules.append((".".join(parts[:-1] if parts[-1] == "__init__" else parts), path))
	return modules


@cache
def get_references(path: Path) -> tuple[tuple[str, bool], ...]:
	"""Each module that the file at *path* imports or names as frappe.<module>, with whether that
	happens when the module loads (outside every function)."""
	parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
	package = ".".join(parts[:-1])
	return tuple(walk(ast.parse(path.read_text()), package, at_load=True))


def walk(node: ast.AST, package: str, at_load: bool):
	for child in ast.iter_child_nodes(node):
		child_at_load = at_load and not isinstance(child, FUNCTIONS)
		for name in get_names(child, package):
			yield name, child_at_load
		yield from walk(child, package, child_at_load)


def get_names(node: ast.AST, package: str) -> list[str]:
	"""The modules one node refers to: an import, an import call with a literal name, or frappe.<x>."""
	if isinstance(node, ast.Import):
		return [alias.name for alias in node.names]
	if isinstance(node, ast.ImportFrom):
		base = node.module or ""
		if node.level:
			base = ".".join(filter(None, [package.rsplit(".", node.level - 1)[0], node.module]))
		return [base, *(f"{base}.{alias.name}" for alias in node.names)]
	if isinstance(node, ast.Call) and is_import_call(node):
		return [node.args[0].value]
	if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "frappe":
		return [f"frappe.{node.attr}"]
	return []


def is_import_call(node: ast.Call) -> bool:
	"""True for importlib.import_module, __import__ or frappe.get_attr with a literal name."""
	name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
	literal = node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
	return name in IMPORT_CALLS and bool(literal)


def is_within(name: str, module: str) -> bool:
	return name == module or name.startswith(f"{module}.")
