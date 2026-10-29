# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.client import get as get_document
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as get_chart
from frappe.utils import add_days, get_first_day_of_week, getdate, today

from churchit.church_summary import metrics
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)

WEEK = get_first_day_of_week("2025-03-12")


def make_service(name, church, start_date=WEEK, headcount=10, **values):
	return make_function(name, church=church, start_date=start_date, headcount=headcount, **values)


def give(church, amount, date, person=None):
	fund = ensure("Fund", {"fund": "_Test Metrics Fund"}, {"fund": "_Test Metrics Fund", "is_shared": 1})
	collection = frappe.get_doc(
		{
			"doctype": "Collection",
			"date": date,
			"church": church,
			"expected_total": amount,
			"donations": [
				{
					"person": person,
					"fund": fund,
					"amount": amount,
					"payment_type": ensure("Payment Type", {"type": "Cash"}),
				}
			],
		}
	).insert(ignore_permissions=True)
	collection.submit()
	return collection


def make_member(first_name, church, **values):
	values.setdefault("membership", ensure("Membership Type", {"type": "Member"}))
	values.setdefault("membership_status", ensure("Member Status", {"status": "Active"}))
	return make_person(first_name, "_Test Metrics", church=church, **values).name


def get_row(church, week_start=WEEK):
	return frappe.get_doc("Weekly Metrics", {"church": church, "week_start": week_start})


class TestWeeklyMetrics(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = cls.make_user("manager_a", cls.branch_a, ("Church Manager",))
		cls.staff_a = cls.make_user("staff_a", cls.branch_a, ("Church Staff",))
		cls.finance_a = cls.make_user("finance_a", cls.branch_a, ("Church Staff", "Church Finance"))

	@classmethod
	def make_user(cls, key, church, roles):
		user = ensure_user(f"_test_metrics_{key}@example.com", key, roles=roles)
		make_person(key, "_Test Metrics", church=church, user=user)
		return user

	def test_a_second_run_updates_the_one_row_of_each_church(self):
		make_service("_Test Metrics Service A", self.branch_a, headcount=12)
		metrics.record_week(WEEK)
		make_service("_Test Metrics Late Service A", self.branch_a, headcount=3)
		metrics.record_week(add_days(WEEK, 3))

		for church in (self.branch_a, self.branch_b):
			self.assertEqual(
				frappe.db.count("Weekly Metrics", {"church": church, "week_start": WEEK}), 1, church
			)
		self.assertEqual(get_row(self.branch_a).attendance, 15)

	def test_each_row_counts_only_its_own_church(self):
		"""A shared service counts once, for the church that shared it, and a schedule template never."""
		make_service("_Test Metrics Service A", self.branch_a, headcount=40)
		make_service("_Test Metrics Joint Service", self.branch_a, headcount=100, is_shared=1)
		template = make_service("_Test Metrics Template A", self.branch_a, headcount=7)
		frappe.db.set_value("Function", template.name, "auto_repeat", 1)
		make_service("_Test Metrics Service B", self.branch_b, headcount=9)
		make_service("_Test Metrics Next Week", self.branch_a, start_date=add_days(WEEK, 7))
		giver = make_member("_Test Giver", self.branch_a)
		give(self.branch_a, 30, f"{WEEK} 09:00:00", giver)
		give(self.branch_a, 20, f"{add_days(WEEK, 6)} 23:59:00", giver)
		give(self.branch_a, 5, f"{add_days(WEEK, 2)} 10:00:00")
		give(self.branch_a, 1000, f"{add_days(WEEK, 7)} 00:00:00", giver)
		give(self.branch_b, 70, f"{add_days(WEEK, 1)} 10:00:00", make_member("_Test Giver B", self.branch_b))
		visitor = make_person("_Test Visitor", "_Test Metrics", church=self.branch_a).name
		frappe.db.set_value("Person", visitor, "first_attended_on", add_days(WEEK, 6))

		metrics.record_week(WEEK)

		row_a, row_b = get_row(self.branch_a), get_row(self.branch_b)
		self.assertEqual(
			(row_a.attendance, row_a.giving_total, row_a.givers, row_a.first_time_visitors), (140, 55, 1, 1)
		)
		self.assertEqual(
			(row_b.attendance, row_b.giving_total, row_b.givers, row_b.first_time_visitors), (9, 70, 1, 0)
		)

	def test_a_rerun_of_last_week_counts_a_late_check_in_but_keeps_its_people_counts(self):
		service = make_service("_Test Metrics Service A", self.branch_a, headcount=10)
		make_member("_Test Member One", self.branch_a)
		metrics.record_week(WEEK, include_people=True)
		self.assertEqual((get_row(self.branch_a).attendance, get_row(self.branch_a).active_members), (10, 1))

		make_member("_Test Member Two", self.branch_a)
		service.reload()
		service.headcount = 11
		service.save(ignore_permissions=True)
		metrics.record_week(WEEK)

		self.assertEqual((get_row(self.branch_a).attendance, get_row(self.branch_a).active_members), (11, 1))

	def test_people_counts_take_living_people_of_the_church(self):
		make_member("_Test Member", self.branch_a)
		inactive = make_member("_Test Inactive", self.branch_a, membership_status="Inactive")
		died = make_member("_Test Died", self.branch_a)
		frappe.db.set_value("Person", died, {"is_deceased": 1, "group_count": 2, "times_served_90d": 1})
		frappe.db.set_value("Person", inactive, {"group_count": 1, "times_served_90d": 3})
		make_member("_Test Member B", self.branch_b)

		metrics.record_week(WEEK, include_people=True)

		row = get_row(self.branch_a)
		self.assertEqual((row.active_members, row.people_in_groups, row.people_serving), (1, 1, 1))

	def test_the_daily_job_writes_people_counts_for_this_week_only(self):
		this_week = get_first_day_of_week(today())
		last_week = add_days(this_week, -7)
		make_member("_Test Member", self.branch_a)
		make_service("_Test Metrics Last Week", self.branch_a, start_date=last_week, headcount=8)

		metrics.record_recent_weeks()

		current, previous = get_row(self.branch_a, this_week), get_row(self.branch_a, last_week)
		self.assertEqual(current.active_members, 1)
		self.assertEqual((previous.attendance, previous.active_members), (8, 0))

	def test_a_manager_reads_only_their_churches_rows(self):
		metrics.record_week(WEEK)
		assert_scoped(
			self, "Weekly Metrics", self.manager_a, get_row(self.branch_a).name, get_row(self.branch_b).name
		)

	def test_staff_read_the_row_but_not_the_giving(self):
		give(self.branch_a, 25, f"{WEEK} 09:00:00")
		metrics.record_week(WEEK)
		name = get_row(self.branch_a).name

		frappe.set_user(self.staff_a)
		self.assertIn(name, frappe.get_list("Weekly Metrics", pluck="name"))
		self.assertFalse(get_document("Weekly Metrics", name).get("giving_total"))
		self.assertNotIn(
			"giving_total", frappe.get_list("Weekly Metrics", fields=["name", "giving_total"])[0]
		)
		self.assertRaises(
			frappe.PermissionError, frappe.get_list, "Weekly Metrics", fields=[{"SUM": "giving_total"}]
		)

		frappe.set_user(self.finance_a)
		rows = frappe.get_list("Weekly Metrics", filters={"name": name}, fields=["giving_total"])
		self.assertEqual(rows[0].giving_total, 25)

	def test_nobody_adds_or_changes_a_row_by_hand(self):
		metrics.record_week(WEEK)
		frappe.set_user(self.manager_a)
		self.assertFalse(frappe.has_permission("Weekly Metrics", "create"))
		self.assertFalse(frappe.has_permission("Weekly Metrics", "write", doc=get_row(self.branch_a).name))

	def test_the_giving_chart_is_only_for_finance_and_managers(self):
		metrics.record_week(get_first_day_of_week(today()))

		frappe.set_user(self.staff_a)
		get_chart(chart_name="Attendance by Week", refresh=1)
		self.assertFalse(frappe.has_permission("Dashboard Chart", doc="Giving by Week"))
		self.assertRaises(frappe.PermissionError, get_chart, chart_name="Giving by Week", refresh=1)

		frappe.set_user(self.finance_a)
		self.assertTrue(frappe.has_permission("Dashboard Chart", doc="Giving by Week"))
		get_chart(chart_name="Giving by Week", refresh=1)

	def test_backfill_is_a_managers_queued_job(self):
		frappe.set_user(self.staff_a)
		self.assertRaises(frappe.PermissionError, metrics.backfill)

		frappe.set_user(self.manager_a)
		with mock.patch("frappe.enqueue") as enqueue:
			metrics.backfill()
		enqueue.assert_called_once()
		self.assertEqual(enqueue.call_args.args, (metrics.backfill_weeks,))
		self.assertEqual(enqueue.call_args.kwargs["queue"], "long")
		self.assertEqual(enqueue.call_args.kwargs["job_id"], metrics.BACKFILL_JOB)
		self.assertTrue(enqueue.call_args.kwargs["deduplicate"])

	def test_the_backfill_writes_attendance_and_giving_for_the_weeks_before_last_week(self):
		this_week = get_first_day_of_week(today())
		make_service(
			"_Test Metrics Long Ago", self.branch_a, start_date=add_days(this_week, -7 * 52), headcount=6
		)

		with mock.patch("frappe.db.commit"):
			metrics.backfill_weeks()

		self.assertEqual(frappe.db.count("Weekly Metrics", {"church": self.branch_a}), 51)
		self.assertEqual(get_row(self.branch_a, add_days(this_week, -7 * 52)).attendance, 6)
		for daily_week in (this_week, add_days(this_week, -7)):
			self.assertFalse(
				frappe.db.exists("Weekly Metrics", {"church": self.branch_a, "week_start": daily_week})
			)


class TestWeeklyMetricsOneChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		force_single_church()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_single_church_site_writes_one_row_for_the_whole_site(self):
		metrics.record_week(WEEK)
		before = get_row(self.root).attendance
		make_function("_Test Metrics One Church", start_date=WEEK, headcount=13)

		metrics.record_week(WEEK)

		self.assertEqual(
			frappe.get_all("Weekly Metrics", filters={"week_start": WEEK}, pluck="church"), [self.root]
		)
		self.assertEqual(get_row(self.root).attendance, before + 13)
		self.assertEqual(getdate(get_row(self.root).week_start), WEEK)
