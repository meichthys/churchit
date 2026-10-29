# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from churchit.church_ministries.report.church_attendance.test_church_attendance import GroupMeetings
from churchit.church_ministries.report.function_attendance_by_person.function_attendance_by_person import (
	execute,
)
from churchit.tests.helpers import RollbackEachTest


class TestFunctionAttendanceByPerson(GroupMeetings, RollbackEachTest):
	function_field = "function"

	def rows(self, **filters):
		return execute(filters)[1]
