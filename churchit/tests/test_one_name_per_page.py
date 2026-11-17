# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

APP_PATH = Path(frappe.get_app_path("churchit"))

# Report -> the title its script sets, which its sidebar label must repeat.
RETITLED_REPORTS = {
	"Visitation Followups Needed": "Follow-ups Needed",
	"New Members Last 90 Days": "New Members",
	"Person Positions Ending This Month": "Positions Ending",
	"Function Attendance by Type": "Check-Ins by Function",
}

# Reports whose page title is longer than the 24 characters a sidebar label keeps. A Report
# Builder report cannot set its own title, so the rename needs a patch or a longer label.
LONG_TITLE_REPORTS = {"People with Open Care Requests"}


def get_sidebar_items(sidebar: str) -> list[frappe._dict]:
	return frappe.get_doc("Sidebar", sidebar).items


class TestOneNamePerPage(FrappeTestCase):
	def test_a_report_with_its_own_title_sets_it_and_its_sidebar_label_matches(self):
		for report, title in RETITLED_REPORTS.items():
			module = frappe.db.get_value("Report", report, "module")
			script = next((APP_PATH / frappe.scrub(module) / "report" / frappe.scrub(report)).glob("*.js"))
			self.assertIn(f'__("{title}")', script.read_text(), report)

			labels = [
				item.label
				for sidebar in frappe.get_all("Sidebar", pluck="name")
				for item in get_sidebar_items(sidebar)
				if item.link_type == "Report" and item.link_to == report
			]
			self.assertTrue(labels, report)
			for label in labels:
				self.assertEqual(label, title, report)

	def test_a_report_label_is_the_report_name_less_a_repeated_module_word(self):
		"""A report that sets no title opens under its own name, so its label is that name."""
		for sidebar in frappe.get_all("Sidebar", filters={"module": ("like", "Church %")}, pluck="name"):
			for item in get_sidebar_items(sidebar):
				if item.link_type != "Report" or item.link_to in set(RETITLED_REPORTS) | LONG_TITLE_REPORTS:
					continue
				name = item.link_to.removesuffix(" Report").lower()
				label = item.label.removesuffix(" Report").lower()
				self.assertTrue(
					name.endswith(label) or label.endswith(name),
					f"{sidebar}: label {item.label!r} opens {item.link_to!r}",
				)

	def test_the_people_sidebar_leads_with_people_families_and_groups(self):
		labels = [item.label for item in get_sidebar_items("People") if not item.child]

		self.assertEqual(labels[:4], ["Home", "People", "Families", "Groups"])

	def test_follow_up_cards_come_first_in_visitors_and_follow_up(self):
		labels = [item.label for item in get_sidebar_items("People")]

		self.assertEqual(labels[labels.index("Visitors & Follow-up") + 1], "Follow-up Cards")

	def test_the_badge_popover_opens_above_the_badge_on_a_phone(self):
		script = (APP_PATH / "public" / "js" / "published_fields_indicator.js").read_text()

		self.assertRegex(script, r'placement:\s*"top"')
		self.assertIsNone(re.search(r'placement:\s*"bottom"', script))
