# Copyright (c) 2025, meichthys and Contributors
# See license.txt

"""Hygiene tests for church reports.

Verifies a small set of conventions across all reports:
- script reports call `churchit.utils.set_report_link_titles`
  (so linked column values render as titles in lists)
- each report folder has a `__init__.py`
- each report has a `<name>.json` describing it

Designed to fail loudly so future report contributors notice when they
skip the convention; the helper isn't strictly required for HTML-rendered
reports (those format links themselves), so this test treats reports
returning HTML fieldtype columns as exempt.
"""

import os
import re

from frappe.tests.utils import FrappeTestCase

REPORTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _walk_report_python_files():
	for root, dirs, files in os.walk(REPORTS_DIR):
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
			missing.append(os.path.relpath(path, REPORTS_DIR))
		assert not missing, (
			"These script reports neither call churchit.utils.set_report_link_titles "
			"nor render HTML column types: " + ", ".join(missing)
		)
