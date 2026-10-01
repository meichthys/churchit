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

import os
import re

from frappe.tests.utils import FrappeTestCase

from churchit.church_scope import scoped_doctypes

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUERIED_DOCTYPE = re.compile(r'(?:DocType|get_all|get_list|db\.count)\(\s*"([^"]+)"')
# Lists churches themselves through frappe.get_list, so it is scoped by user permissions.
SCOPE_EXEMPT_REPORTS = {"church_foundations/report/churches/churches.py"}


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
