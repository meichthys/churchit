# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Hygiene tests for church reports.

Verifies a small set of conventions across all reports:
- script reports call `churchit.utils.set_report_link_titles`
  (so linked column values render as titles in lists)
- each report folder has a `__init__.py`
- each report has a `<name>.json` describing it
- script reports over church-scoped doctypes go through `churchit.church_scope`
  and offer the shared church filter (branch users must never see another
  church's rows, and raw query builder bypasses user permissions)

Designed to fail loudly so future report contributors notice when they
skip the convention. Two kinds of report are exempt: HTML-rendered reports
format their own clickable cells, and reports with no Link or Dynamic Link
columns have nothing for the helper to resolve.
"""

import ast
import glob
import os
import re

from frappe.tests.utils import FrappeTestCase

from churchit.church_scope import scoped_doctypes

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUERIED_DOCTYPE = re.compile(r'(?:DocType|get_all|get_list|db\.count)\(\s*"([^"]+)"')
# Lists churches themselves through frappe.get_list, so it is scoped by user permissions.
SCOPE_EXEMPT_REPORTS = {"church_foundations/report/churches/churches.py"}
COUNTED_TYPES_OWNER = "church_ministries/attendance.py"
# Every role profile that holds these also holds Church Staff (AGENTS.md "Roles").
ADD_ON_ROLES = {"Church Pastoral Care", "Church Finance", "Church People Editor"}


def _walk_report_python_files():
	for root, _dirs, files in os.walk(REPORTS_DIR):
		if not root.endswith("/report") and "/report/" not in root:
			continue
		for f in files:
			if f.endswith(".py") and f not in ("__init__.py",) and not f.startswith("test_"):
				yield os.path.join(root, f)


class TestReportsHygiene(FrappeTestCase):
	def test_each_report_uses_link_title_helper_or_returns_html(self):
		missing = []
		for path in _walk_report_python_files():
			with open(path) as fh:
				body = fh.read()
			if "set_report_link_titles" in body:
				continue
			# HTML-rendered reports format their own clickable cells, so are exempt
			if re.search(r'"fieldtype":\s*"HTML"', body):
				continue
			# Nothing to resolve without a Link column
			if not re.search(r'"fieldtype":\s*"(Dynamic )?Link"', body):
				continue
			missing.append(os.path.relpath(path, REPORTS_DIR))
		assert not missing, (
			"These script reports have Link columns but do not call "
			"churchit.utils.set_report_link_titles: " + ", ".join(missing)
		)

	def scoped_reports(self):
		"""Report modules that query a church-scoped doctype."""
		scoped = set(scoped_doctypes())
		for path in _walk_report_python_files():
			relative = os.path.relpath(path, REPORTS_DIR)
			if relative in SCOPE_EXEMPT_REPORTS:
				continue
			with open(path) as fh:
				body = fh.read()
			if scoped & set(QUERIED_DOCTYPE.findall(body)):
				yield relative, body

	def test_reports_over_scoped_doctypes_apply_the_church_scope(self):
		"""A report runs raw, so without this it shows every church's rows to everyone."""
		leaking = [name for name, body in self.scoped_reports() if "church_scope" not in body]
		assert not leaking, (
			"These reports query church-scoped doctypes without churchit.church_scope, so they "
			"show one church's records to another: " + ", ".join(sorted(leaking))
		)

	def test_reports_over_scoped_doctypes_offer_the_church_filter(self):
		"""Not a leak, the server already scopes them: the reader just cannot narrow by church."""
		missing = []
		for name, _body in self.scoped_reports():
			with open(os.path.join(REPORTS_DIR, name[:-3] + ".js")) as fh:
				if "church.report_filters()" not in fh.read():
					missing.append(name)
		assert not missing, (
			"These reports are scoped but offer no Church filter. Spread it into their filters: "
			"`filters: [...church.report_filters(), ...]` in " + ", ".join(sorted(missing))
		)

	def test_only_attendance_py_lists_the_counted_attendance_types(self):
		"""Every reader of attendance takes COUNTED_TYPES from church_ministries/attendance.py."""
		copies = []
		for path in glob.glob(os.path.join(REPORTS_DIR, "**", "*.py"), recursive=True):
			relative = os.path.relpath(path, REPORTS_DIR)
			name = os.path.basename(path)
			if (
				relative in (COUNTED_TYPES_OWNER, "hooks.py")
				or name.startswith("test_")
				or "tests/" in relative
			):
				continue
			with open(path) as fh:
				tree = ast.parse(fh.read())
			for node in ast.walk(tree):
				if isinstance(node, ast.List | ast.Tuple | ast.Set):
					values = {element.value for element in node.elts if isinstance(element, ast.Constant)}
					if {"Assumed", "Checked-In"} <= values:
						copies.append(f"{relative}:{node.lineno}")
		assert not copies, (
			"These files list the counted attendance types themselves. Import COUNTED_TYPES from "
			"churchit.church_ministries.attendance instead: " + ", ".join(sorted(copies))
		)

	def test_each_report_role_may_open_it(self):
		"""Frappe opens a report only for a role with report permission on its reference doctype.

		A role listed on the report without it sees the report in the sidebar and gets
		"You don't have permission to get a report on" when it opens.
		"""
		import json

		import frappe

		closed = []
		for path in glob.glob(os.path.join(REPORTS_DIR, "*", "report", "*", "*.json")):
			with open(path) as fh:
				report = json.load(fh)
			if report.get("report_type") not in ("Script Report", "Query Report"):
				continue
			meta = frappe.get_meta(report["ref_doctype"])
			reporting = {
				perm.role
				for perm in meta.permissions
				if perm.report and not perm.permlevel and not perm.if_owner and not meta.istable
			}
			for role in {row["role"] for row in report.get("roles", [])} - reporting:
				if role in ADD_ON_ROLES and "Church Staff" in reporting:
					continue
				closed.append(f"{report['name']} ({report['ref_doctype']}): {role}")
		assert not closed, (
			"These report roles cannot open the report. Give the role report permission on the "
			"reference doctype, point the report at a parent doctype, or drop the role: "
			+ ", ".join(sorted(closed))
		)
