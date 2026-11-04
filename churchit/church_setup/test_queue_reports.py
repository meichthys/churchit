# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Report Builder queues that the module workspaces and sidebars open.

A queue whose list has no default filter is a standard Report Builder report, because a filtered
link saves its filters onto the plain list. Each report must run, and each must list the records
that wait and nothing else.
"""

import json

import frappe
from frappe.utils import add_days, cint, now_datetime

from churchit.tests.helpers import RollbackEachTest, ensure, make_person
from churchit.tests.test_desk_ui_hygiene import assert_list_ratchet
from churchit.tests.test_workspace_hygiene import shipped_workspaces

# Reports whose saved filters the Report view puts in another order, so they open as 'Not Saved'.
REPORTS_OUT_OF_ORDER = {}


def listed(report_name: str) -> list[str]:
	"""The names a saved report shows, in its own order."""
	_columns, rows = frappe.get_doc("Report", report_name).get_data(as_dict=True)
	return [row.name for row in rows]


def get_report_builder_reports() -> list[str]:
	return frappe.get_all(
		"Report",
		filters={
			"report_type": "Report Builder",
			"is_standard": "Yes",
			"module": ("in", frappe.get_module_list("churchit")),
		},
		pluck="name",
	)


def get_report_view_order(doctype: str, filters: list[list]) -> list[list]:
	"""The order the Report view returns *filters* in: the others first, then the standard filters.

	A condition fills a standard filter box when its field is the title or an `in_standard_filter`
	field and it is `=`, or `like` on a field that is not a Link. `= 0` on a Check is no such condition.
	The boxes come in field order.
	"""
	meta = frappe.get_meta(doctype)
	boxes = [df for df in meta.fields if df.in_standard_filter or df.fieldname == meta.title_field]
	fieldnames = [df.fieldname for df in boxes]

	def fills_a_box(condition: list) -> bool:
		_doctype, fieldname, operator, value = condition
		if fieldname not in fieldnames:
			return False
		fieldtype = boxes[fieldnames.index(fieldname)].fieldtype
		if fieldtype == "Check" and not cint(value):
			return False
		return operator == "=" or (operator == "like" and fieldtype != "Link")

	others = [condition for condition in filters if not fills_a_box(condition)]
	standard = [condition for condition in filters if fills_a_box(condition)]
	return others + sorted(standard, key=lambda condition: fieldnames.index(condition[1]))


def make_request(title: str, **values) -> str:
	request_type = ensure("Prayer Request Type", {"type": "_Test Queue"})
	return (
		frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": title,
				"type": request_type,
				"visibility": "Whole Church",
				"approved_for_list": 0,
				**values,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def make_booking(room: str, requester: str, days: int, status: str) -> str:
	start = add_days(now_datetime().replace(hour=9, minute=0, second=0, microsecond=0), days)
	booking = frappe.get_doc(
		{
			"doctype": "Room Booking",
			"room": room,
			"requester": requester,
			"purpose": "_Test queue",
			"start_datetime": start,
			"end_datetime": start.replace(hour=10),
		}
	).insert(ignore_permissions=True)
	frappe.db.set_value("Room Booking", booking.name, "status", status)
	return booking.name


class TestQueueReports(RollbackEachTest):
	def test_every_shipped_report_builder_report_runs(self):
		reports = get_report_builder_reports()
		self.assertIn("Booking Requests", reports)

		for name in reports:
			with self.subTest(report=name):
				listed(name)

	def test_saved_filters_come_in_the_order_the_report_view_returns_them(self):
		"""The Report view shows 'Not Saved' when its order differs from the saved one."""
		found = {}
		for name in get_report_builder_reports():
			report = frappe.get_doc("Report", name)
			saved = json.loads(report.json)["filters"]
			if (order := get_report_view_order(report.ref_doctype, saved)) != saved:
				found[name] = [condition[1] for condition in order]
		assert_list_ratchet(self, found, REPORTS_OUT_OF_ORDER, "A report saves its filters out of order")

	def test_a_docstatus_filter_is_saved_as_text(self):
		"""The filter box drops `docstatus = 0` as a number, so the report would list every record."""
		numbers = []
		for name in get_report_builder_reports():
			for condition in json.loads(frappe.db.get_value("Report", name, "json"))["filters"]:
				if condition[1] == "docstatus" and not isinstance(condition[3], str):
					numbers.append(name)
		self.assertEqual(numbers, [])

	def test_each_report_builder_shortcut_names_the_doctype_of_its_report(self):
		"""The desk builds a Report Builder route from the shortcut's doctype, not from the report."""
		wrong = []
		for workspace in shipped_workspaces():
			for row in workspace.get("shortcuts", []):
				if row.get("type") != "Report":
					continue
				report = frappe.db.get_value(
					"Report", row["link_to"], ["report_type", "ref_doctype"], as_dict=True
				)
				if not report or (
					report.report_type == "Report Builder"
					and report.ref_doctype != row.get("report_ref_doctype")
				):
					wrong.append((workspace["name"], row["label"]))
		self.assertEqual(wrong, [])

	def test_awaiting_approval_lists_open_shared_requests_that_are_not_approved(self):
		waiting = make_request("_Test Waiting")
		approved = make_request("_Test Approved", approved_for_list=1)
		private = make_request("_Test Private", visibility="Private")
		answered = make_request("_Test Answered", status="Answered")

		shown = listed("Prayer Requests Awaiting Approval")
		self.assertIn(waiting, shown)
		self.assertEqual({approved, private, answered} & set(shown), set())

	def test_ending_this_week_lists_open_requests_that_end_soonest_first(self):
		later = make_request("_Test Ends Later", end_date=add_days(now_datetime(), 5))
		sooner = make_request("_Test Ends Sooner", end_date=add_days(now_datetime(), 1))
		next_month = make_request("_Test Ends Next Month", end_date=add_days(now_datetime(), 30))
		answered = make_request(
			"_Test Ends Answered", end_date=add_days(now_datetime(), 2), status="Answered"
		)

		mine = (later, sooner, next_month, answered)
		shown = [name for name in listed("Prayer Requests Ending This Week") if name in mine]
		self.assertEqual(shown, [sooner, later])

	def test_booking_requests_lists_waiting_bookings_soonest_first(self):
		room = frappe.get_doc(
			{"doctype": "Room", "room_name": "_Test Queue Room", "is_bookable": 1, "requires_approval": 1}
		).insert(ignore_permissions=True)
		requester = make_person("_Test Queue", "Booker").name
		later = make_booking(room.name, requester, 3, "Requested")
		sooner = make_booking(room.name, requester, 1, "Conflict")
		approved = make_booking(room.name, requester, 2, "Approved")

		mine = (later, sooner, approved)
		shown = [name for name in listed("Booking Requests") if name in mine]
		self.assertEqual(shown, [sooner, later])
