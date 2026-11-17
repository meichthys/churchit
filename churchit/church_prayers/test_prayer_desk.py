# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, now_datetime

from churchit.church_people.report.pastoral_care_watch_list import pastoral_care_watch_list
from churchit.church_people.report.visitation_followups_needed import visitation_followups_needed
from churchit.church_people.summaries.test_care import make_visit
from churchit.church_prayers.report.active_prayer_list import active_prayer_list
from churchit.church_prayers.web_form.community_prayer_requests import community_prayer_requests
from churchit.patches.v1_0 import fill_prayer_request_answered_on
from churchit.tests.helpers import RollbackEachTest, ensure, force_single_church, make_person


def make_request(title, **values):
	request_type = ensure("Prayer Request Type", {"type": "_Test Desk Type"})
	return frappe.get_doc(
		{"doctype": "Prayer Request", "title": title, "type": request_type, "request": "_Test text", **values}
	).insert(ignore_permissions=True)


class TestPastoralReports(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def watched(self):
		_columns, rows = pastoral_care_watch_list.execute({"window_days": 30})
		return {row["person"]: row["reason"] for row in rows}

	def test_an_urgent_request_puts_the_person_prayed_for_on_the_watch_list(self):
		requester = make_person("_Test Desk", "Requester")
		patient = make_person("_Test Desk", "Patient")
		make_request(
			"_Test urgent",
			urgent=1,
			requestor=requester.name,
			recipient_type="Person",
			recipient=patient.name,
		)

		watched = self.watched()

		self.assertIn(patient.name, watched)
		self.assertNotIn(requester.name, watched)

	def test_an_urgent_general_request_puts_its_requester_on_the_watch_list(self):
		requester = make_person("_Test Desk", "General")
		make_request("_Test general", urgent=1, requestor=requester.name)

		self.assertIn(requester.name, self.watched())

	def test_a_scheduled_later_visit_takes_the_person_off_both_lists(self):
		stays = make_person("_Test Desk", "Stays")
		leaves = make_person("_Test Desk", "Leaves")
		for person in (stays, leaves):
			make_visit(person.name, -3).db_set("follow_up_needed", 1)
		make_visit(leaves.name, 0, status="Scheduled")

		_columns, rows = visitation_followups_needed.execute({})
		listed = {row["person"] for row in rows}

		self.assertIn(stays.name, listed)
		self.assertNotIn(leaves.name, listed)
		self.assertIn(stays.name, self.watched())
		self.assertNotIn(leaves.name, self.watched())

	def test_a_visit_already_on_the_calendar_counts_and_an_older_one_logged_later_does_not(self):
		booked = make_person("_Test Desk", "Booked")
		make_visit(booked.name, 5, status="Scheduled")
		make_visit(booked.name, -3).db_set("follow_up_needed", 1)
		backfilled = make_person("_Test Desk", "Backfilled")
		make_visit(backfilled.name, -3).db_set("follow_up_needed", 1)
		make_visit(backfilled.name, -10)

		_columns, rows = visitation_followups_needed.execute({})
		listed = {row["person"] for row in rows}

		self.assertNotIn(booked.name, listed)
		self.assertIn(backfilled.name, listed)

	def test_a_planned_later_visit_leaves_the_person_listed(self):
		person = make_person("_Test Desk", "Planned")
		make_visit(person.name, -3).db_set("follow_up_needed", 1)
		make_visit(person.name, 0, status="Planned")

		_columns, rows = visitation_followups_needed.execute({})

		self.assertIn(person.name, {row["person"] for row in rows})


class TestActivePrayerList(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def listed(self, **filters):
		_columns, rows = active_prayer_list.execute(filters)
		return {row["name"] for row in rows}

	def test_private_requests_and_ended_requests_stay_off_unless_asked_for(self):
		public = make_request("_Test public", visibility="Whole Church").name
		team = make_request("_Test team", visibility="Prayer Team").name
		private = make_request("_Test private", visibility="Private").name
		ended = make_request(
			"_Test ended", visibility="Whole Church", end_date=add_days(now_datetime(), -1)
		).name

		listed = self.listed()

		self.assertTrue({public, team} <= listed)
		self.assertFalse({private, ended} & listed)
		self.assertIn(private, self.listed(visibility="Private"))
		self.assertNotIn(public, self.listed(visibility="Private"))

	def test_the_list_shows_what_to_pray_for_and_who_may_see_it(self):
		make_request("_Test columns")
		columns, rows = active_prayer_list.execute({})

		fieldnames = {column["fieldname"] for column in columns}
		self.assertTrue({"recipient_name", "request", "visibility"} <= fieldnames)
		self.assertTrue(all("request" in row and "visibility" in row for row in rows))


class TestAnsweredOn(RollbackEachTest):
	def test_a_request_records_the_day_it_turns_answered_and_keeps_it(self):
		request = make_request("_Test answered")
		self.assertIsNone(request.answered_on)

		request.status = "Answered"
		request.save()
		first = request.answered_on
		frappe.db.set_value("Prayer Request", request.name, "answered_on", add_days(first, -40))
		request.reload()
		request.title = "_Test answered edited"
		request.save()

		self.assertEqual(str(request.answered_on), add_days(first, -40))

	def test_reopening_a_request_clears_the_day(self):
		request = make_request("_Test reopened", status="Answered")
		self.assertTrue(request.answered_on)

		request.status = "Requested"
		request.save()

		self.assertIsNone(request.answered_on)

	def test_the_patch_dates_old_answers_by_their_last_change_and_runs_twice(self):
		request = make_request("_Test old answer", status="Answered")
		frappe.db.set_value("Prayer Request", request.name, "answered_on", None)

		fill_prayer_request_answered_on.execute()
		fill_prayer_request_answered_on.execute()

		self.assertEqual(
			frappe.db.get_value("Prayer Request", request.name, "answered_on"),
			frappe.utils.getdate(frappe.db.get_value("Prayer Request", request.name, "modified")),
		)


class TestCommunityPrayerForm(RollbackEachTest):
	def test_the_list_puts_urgent_requests_first_and_shows_who_may_see_each(self):
		form = frappe.get_doc("Web Form", "community-prayer-requests")
		columns = [column.fieldname for column in form.list_columns]

		self.assertEqual(columns[:2], ["recipient_name", "request"])
		self.assertIn("visibility", columns)
		context = frappe._dict()
		community_prayer_requests.get_list_context(context)
		self.assertTrue(context.order_by.startswith("urgent desc"))
