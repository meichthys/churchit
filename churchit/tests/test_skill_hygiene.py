# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The churchit skill for AI apps stays true: front matter, links, named methods, doctypes and reports."""

import ast
import re
from importlib.util import find_spec
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_doc_method_hygiene import is_whitelisted

SKILL_FOLDER = Path(__file__).resolve().parents[2] / "skills" / "churchit"
METHOD_PATTERN = re.compile(r"`(churchit(?:\.\w+)+)`")
TABLE_ROW = re.compile(r"^\| (?P<first>[^|]+?) \| (?P<second>[^|]+?) \|", re.MULTILINE)
REPORT_KINDS = {"Script": "Script Report", "Saved list": "Report Builder"}


def skill_files() -> list[Path]:
	return [SKILL_FOLDER / "SKILL.md", *sorted((SKILL_FOLDER / "reference").glob("*.md"))]


def find_function(dotted_name: str) -> ast.FunctionDef | None:
	module_name, _, function_name = dotted_name.rpartition(".")
	spec = find_spec(module_name)
	if not spec or not spec.origin:
		return None

	tree = ast.parse(Path(spec.origin).read_text())
	return next(
		(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function_name),
		None,
	)


class TestSkillHygiene(FrappeTestCase):
	def test_front_matter_names_the_skill(self):
		text = (SKILL_FOLDER / "SKILL.md").read_text()
		self.assertTrue(text.startswith("---\n"))

		front_matter = dict(
			line.split(": ", 1) for line in text.split("---\n")[1].splitlines() if ": " in line
		)
		self.assertEqual(front_matter["name"], "churchit")
		self.assertTrue(front_matter["description"].strip())

	def test_every_linked_reference_exists(self):
		for path in skill_files():
			for target in re.findall(r"\]\(((?:reference/)?[\w-]+\.md)\)", path.read_text()):
				self.assertTrue((path.parent / target).exists(), f"{path.name} links to missing {target}")

	def test_every_named_method_is_whitelisted(self):
		named = {name for path in skill_files() for name in METHOD_PATTERN.findall(path.read_text())}
		self.assertTrue(named)

		for name in sorted(named):
			function = find_function(name)
			self.assertIsNotNone(function, f"the skill names {name}, which does not exist")
			self.assertTrue(is_whitelisted(function), f"the skill names {name}, which is not whitelisted")

	def test_every_church_word_record_exists(self):
		text = (SKILL_FOLDER / "SKILL.md").read_text()
		section = text.split("## Church words", 1)[1].split("\n## ", 1)[0]

		for row in TABLE_ROW.finditer(section):
			if row["second"] in ("Record", "---"):
				continue
			self.assertTrue(frappe.db.exists("DocType", row["second"]), f"no doctype {row['second']}")

	def test_every_sensitive_record_exists(self):
		text = (SKILL_FOLDER / "SKILL.md").read_text()
		section = text.split("## Sensitive records", 1)[1].split("\n## ", 1)[0]
		doctypes = re.findall(r"\*\*([\w -]+)\*\*", section)
		self.assertTrue(doctypes)

		for doctype in doctypes:
			self.assertTrue(frappe.db.exists("DocType", doctype), f"no doctype {doctype}")

	def test_reports_exist_with_the_kind_the_skill_gives(self):
		text = (SKILL_FOLDER / "reference" / "reports.md").read_text()
		rows = [
			row
			for row in TABLE_ROW.finditer(text.split("## Common reports", 1)[1])
			if row["first"] != "Report" and not row["second"].startswith("---")
		]
		self.assertTrue(rows)

		for row in rows:
			report_type = frappe.db.get_value("Report", row["first"], "report_type")
			self.assertTrue(report_type, f"no report {row['first']}")
			self.assertEqual(report_type, REPORT_KINDS.get(row["second"]), row["first"])
