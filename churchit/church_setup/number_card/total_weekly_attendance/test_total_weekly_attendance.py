# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, get_first_day_of_week, getdate

from churchit.dashboard import count_weekly_attendance
from churchit.tests.helpers import RollbackEachTest, make_function, make_person


class TestWeeklyAttendanceCard(RollbackEachTest):
	"""The Summary's Weekly Attendance card sums what the Attendance by Week chart counts for this week."""

	def test_sums_the_attendance_totals_of_this_weeks_functions(self):
		today = getdate()
		week_start = get_first_day_of_week(today)
		before = count_weekly_attendance()["value"]

		service = make_function("_Test Weekly Card Service", start_date=today, headcount=120)
		service.append(
			"attendance", {"person": make_person("_Test Weekly Card").name, "attendance_type": "Confirmed"}
		)
		service.save(ignore_permissions=True)
		make_function("_Test Weekly Card Last Week", start_date=add_days(week_start, -1), headcount=100)
		template = make_function("_Test Weekly Card Template", start_date=today, headcount=50)
		frappe.db.set_value("Function", template.name, "auto_repeat", 1)

		self.assertEqual(service.attendance_total, 120)
		self.assertEqual(count_weekly_attendance()["value"], before + 120)

	def test_opens_the_functions_of_this_week_so_far(self):
		today = getdate()
		route_options = count_weekly_attendance()["route_options"]

		self.assertEqual(
			route_options,
			{"start_date": ["between", [str(get_first_day_of_week(today)), str(today)]], "auto_repeat": 0},
		)
