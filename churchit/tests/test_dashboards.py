# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Number cards and dashboard chart sources."""

from datetime import date

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, getdate, now

from churchit.church_finances.dashboard_chart_source.finance_summary import finance_summary
from churchit.church_finances.dashboard_chart_source.fund_goal_progress import fund_goal_progress
from churchit.church_finances.dashboard_chart_source.giving_by_fund import giving_by_fund
from churchit.church_people.number_card.anniversaries_this_week import anniversaries_this_week
from churchit.church_people.number_card.birthdays_this_week import birthdays_this_week
from churchit.dashboard import count_weekly_attendance
from churchit.tests.helpers import ensure, make_function, make_person


class TestWeeklyAttendanceCard(FrappeTestCase):
	def test_counts_attendance_rows_on_recent_functions(self):
		before = count_weekly_attendance()["value"]

		recent = make_function("_Test Recent Service", start_date=getdate())
		for first_name in ("_Test Attendee One", "_Test Attendee Two"):
			recent.append(
				"attendance", {"person": make_person(first_name).name, "attendance_type": "Confirmed"}
			)
		recent.save(ignore_permissions=True)

		stale = make_function("_Test Old Service", start_date=add_days(getdate(), -30))
		stale.append(
			"attendance", {"person": make_person("_Test Attendee Old").name, "attendance_type": "Confirmed"}
		)
		stale.save(ignore_permissions=True)

		result = count_weekly_attendance()
		self.assertEqual(result["value"], before + 2)
		self.assertEqual(result["route"], ["List", "Function"])


class TestPeopleNumberCards(FrappeTestCase):
	def setUp(self):
		ensure("Life Event Type", {"type": "Birth"})

	def test_birthdays_this_week_counts_birth_events_in_the_current_week(self):
		before = birthdays_this_week.get_count()
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Birthday Person"})
		person.append("life_events", {"event_type": "Birth", "date": add_years(getdate(), -20)})
		person.insert(ignore_permissions=True)
		self.assertEqual(birthdays_this_week.get_count(), before + 1)

	def test_anniversaries_this_week_counts_heads_of_household_only(self):
		before = anniversaries_this_week.get_count()
		anniversary = add_years(getdate(), -5)
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Anniversary Family"}).insert(
			ignore_permissions=True
		)
		make_person(
			"_Test Anniversary Head", anniversary=anniversary, family=family.name, is_head_of_household=1
		)
		make_person("_Test Anniversary Spouse", anniversary=anniversary, family=family.name)
		self.assertEqual(anniversaries_this_week.get_count(), before + 1)


class TestFinanceChartSources(FrappeTestCase):
	def _fund(self, name, **values):
		return frappe.get_doc({"doctype": "Fund", "fund": name, **values}).insert(ignore_permissions=True)

	def test_fund_goal_progress_lists_goal_bearing_funds_with_balance_and_goal(self):
		goal_fund = self._fund("_Test Goal Chart Fund", goal_amount=400)
		goal_fund.append("transactions", {"amount": 100, "source_type": "Donation", "source": "TEST"})
		goal_fund.flags.ignore_links = True
		goal_fund.save(ignore_permissions=True)
		self._fund("_Test No Goal Fund")

		chart = fund_goal_progress.get()
		self.assertIn("_Test Goal Chart Fund", chart["labels"])
		self.assertNotIn("_Test No Goal Fund", chart["labels"])
		index = chart["labels"].index("_Test Goal Chart Fund")
		self.assertEqual(chart["datasets"][0]["values"][index], 100.0)
		self.assertEqual(chart["datasets"][1]["values"][index], 400.0)

	def test_giving_by_fund_sums_submitted_collections_only(self):
		fund = self._fund("_Test Giving Chart Fund")
		payment_type = ensure("Payment Type", {"type": "Cash"})
		for amount, submit in ((30, True), (20, True), (500, False)):
			collection = frappe.get_doc({"doctype": "Collection", "date": now(), "expected_total": amount})
			collection.append(
				"donations", {"payment_type": payment_type, "fund": fund.name, "amount": amount}
			)
			collection.insert(ignore_permissions=True)
			if submit:
				collection.submit()

		chart = giving_by_fund.get()
		totals = dict(zip(chart["labels"], chart["datasets"][0]["values"], strict=True))
		self.assertEqual(totals.get("_Test Giving Chart Fund"), 50.0)

	def test_finance_summary_buckets_and_labels(self):
		buckets = finance_summary._buckets("Select Date Range", "Monthly", "2030-01-15", "2030-03-10")
		self.assertEqual(
			buckets,
			[
				(date(2030, 1, 1), date(2030, 1, 31)),
				(date(2030, 2, 1), date(2030, 2, 28)),
				(date(2030, 3, 1), date(2030, 3, 31)),
			],
		)

		self.assertEqual(finance_summary._label(date(2030, 4, 1), "Quarterly"), "Q2 2030")
		self.assertEqual(finance_summary._label(date(2030, 4, 1), "Yearly"), "2030")
		self.assertEqual(finance_summary._label(date(2030, 4, 1), "Monthly"), "Apr 2030")

	def test_finance_summary_returns_aligned_series(self):
		chart = finance_summary.get(timespan="Last Quarter", time_interval="Monthly")
		self.assertEqual([d["name"] for d in chart["datasets"]], ["Collections", "Expenses"])
		for dataset in chart["datasets"]:
			self.assertEqual(len(dataset["values"]), len(chart["labels"]))
