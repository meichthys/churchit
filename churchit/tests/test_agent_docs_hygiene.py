# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every whitelisted function tells an AI app what it does, in the first line of its docstring."""

import ast

from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_doc_method_hygiene import Function, app_index, is_whitelisted

KINDS = ("Reads only.", "Changes data.", "Sends messages.")
READS = KINDS[0]
RECEIVERS = ("self", "cls")


def first_line(function: Function) -> str:
	docstring = ast.get_docstring(function.node) or ""
	return docstring.splitlines()[0] if docstring else ""


def unhinted_parameters(function: Function) -> list[str]:
	arguments = function.node.args
	# *args and **kwargs carry a signed link's or Frappe's own arguments; they take no hint.
	named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
	return [item.arg for item in named if item.annotation is None and item.arg not in RECEIVERS]


class TestWhitelistedFunctionsAreDocumentedForAgents(FrappeTestCase):
	"""Frappe's discovery lists a method with the first line of its docstring and its type hints.

	An AI app, over MCP or in Flow, picks a method from that line and fills its arguments from the
	hints, so the line ends with what the method does to the site and every parameter has a type.
	A method that only reads also names what it returns, so the app can use the answer.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.functions = [function for function in app_index().functions() if is_whitelisted(function.node)]

	def names(self, found: list[Function]) -> str:
		return ", ".join(sorted(f"{function.location} {function.name}" for function in found))

	def test_the_first_docstring_line_says_what_the_method_does_to_the_site(self):
		missing = [function for function in self.functions if not first_line(function).endswith(KINDS)]
		assert not missing, (
			f"These whitelisted functions need a docstring whose first line ends with {' or '.join(KINDS)} "
			"(discovery shows only that line): " + self.names(missing)
		)

	def test_every_parameter_has_a_type_hint(self):
		missing = [function for function in self.functions if unhinted_parameters(function)]
		assert not missing, "These whitelisted functions have a parameter with no type hint: " + self.names(
			missing
		)

	def test_a_method_that_only_reads_says_what_it_returns(self):
		missing = [
			function
			for function in self.functions
			if first_line(function).endswith(READS) and function.node.returns is None
		]
		assert not missing, (
			"These whitelisted functions that only read have no return annotation: " + self.names(missing)
		)
