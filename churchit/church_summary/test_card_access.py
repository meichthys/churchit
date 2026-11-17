# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.desk.desktop import get_desktop_page
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure_user

PRAYER_CARDS = ("Active Prayer Requests", "Answered Prayers This Month")
PRAYER_CHART = "Active Prayer Requests by Type"
CARE_SHORTCUT = "Open Care Requests"


class TestQueueWidgets(FrappeTestCase):
	"""Staff, Office and Treasurer read only the prayer and care requests they made, so the queues stay with care roles."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.own_only = {
			"staff": ensure_user("_test_queue_staff@example.com", "QueueStaff", ["Church Staff"]),
			"office": ensure_user(
				"_test_queue_office@example.com", "QueueOffice", ["Church Staff", "Church People Editor"]
			),
			"treasurer": ensure_user(
				"_test_queue_treasurer@example.com", "QueueTreasurer", ["Church Staff", "Church Finance"]
			),
		}
		cls.care_roles = {
			"care team": ensure_user(
				"_test_queue_care@example.com", "QueueCare", ["Church Staff", "Church Pastoral Care"]
			),
			"manager": ensure_user("_test_queue_manager@example.com", "QueueManager", ["Church Manager"]),
		}

	def tearDown(self):
		frappe.set_user("Administrator")

	def summary_as(self, user):
		"""The widget names that the Summary workspace shows *user*."""
		frappe.set_user(user)
		page = get_desktop_page(json.dumps({"name": "Summary", "title": "Summary"}))
		frappe.set_user("Administrator")
		return {
			"cards": {row.number_card_name for row in page["number_cards"]["items"]},
			"charts": {row.chart_name for row in page["charts"]["items"]},
			"shortcuts": {row["label"] for row in page["shortcuts"]["items"]},
		}

	def test_staff_office_and_treasurer_get_no_whole_church_queue(self):
		for profile, user in self.own_only.items():
			with self.subTest(profile):
				for card in PRAYER_CARDS:
					self.assertFalse(frappe.has_permission("Number Card", doc=card, user=user), card)
				self.assertFalse(frappe.has_permission("Dashboard Chart", doc=PRAYER_CHART, user=user))

				summary = self.summary_as(user)
				self.assertFalse(summary["cards"] & set(PRAYER_CARDS), summary["cards"])
				self.assertNotIn(PRAYER_CHART, summary["charts"])
				self.assertNotIn(CARE_SHORTCUT, summary["shortcuts"])
				self.assertIn("Total Members", summary["cards"])

	def test_the_care_roles_keep_the_queues(self):
		for profile, user in self.care_roles.items():
			with self.subTest(profile):
				summary = self.summary_as(user)
				self.assertLessEqual(set(PRAYER_CARDS), summary["cards"])
				self.assertIn(PRAYER_CHART, summary["charts"])
				self.assertIn(CARE_SHORTCUT, summary["shortcuts"])

	def test_the_number_card_list_leaves_out_the_same_cards(self):
		frappe.set_user(self.own_only["staff"])

		listed = set(frappe.get_list("Number Card", filters={"name": ("in", PRAYER_CARDS)}, pluck="name"))

		self.assertFalse(listed)

	def test_other_cards_are_left_alone(self):
		staff = self.own_only["staff"]

		self.assertTrue(frappe.has_permission("Number Card", doc="Total Members", user=staff))
