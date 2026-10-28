# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate, today

from churchit.church_people.summaries import care, refresh
from churchit.church_people.summaries.test_serving import queued_people
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches


def make_care_request(person, status="Requested"):
	category = ensure("Care Request Type", {"type": "_Test Need"})
	return frappe.get_doc(
		{
			"doctype": "Care Request",
			"person": person,
			"category": category,
			"description": "_Test summary",
			"status": status,
		}
	).insert(ignore_permissions=True)


def make_visit(person, days_from_today, status="Completed"):
	visit_type = ensure("Visit Type", {"type": "_Test Home Visit"})
	return frappe.get_doc(
		{
			"doctype": "Visitation Log",
			"person": person,
			"visit_type": visit_type,
			"visit_date": add_days(today(), days_from_today),
			"status": status,
		}
	).insert(ignore_permissions=True)


def make_background_check(person, requested_days_ago, status="Requested", **values):
	check_type = ensure(
		"Background Check Type", {"type": "_Test Criminal"}, {"type": "_Test Criminal", "valid_for_years": 3}
	)
	return frappe.get_doc(
		{
			"doctype": "Background Check",
			"person": person,
			"check_type": check_type,
			"requested_on": add_days(today(), -requested_days_ago),
			"status": status,
			**values,
		}
	).insert(ignore_permissions=True)


def summary(person):
	refresh([person])
	return frappe.db.get_value("Person", person, care.FIELDS, as_dict=True)


class TestCareSummary(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Cared For", "Summary").name

	def test_requests_count_until_they_are_resolved_or_closed(self):
		for status in ("Requested", "Triaged", "In Progress", "Resolved", "Closed"):
			make_care_request(self.person, status)

		self.assertEqual(summary(self.person).open_care_requests, 3)

	def test_last_visit_is_the_latest_completed_one_up_to_today(self):
		make_visit(self.person, -30)
		make_visit(self.person, -5)
		make_visit(self.person, -1, status="Planned")
		make_visit(self.person, -1, status="Scheduled")
		make_visit(self.person, 3)

		self.assertEqual(summary(self.person).last_visited_on, getdate(add_days(today(), -5)))

	def test_the_latest_requested_background_check_wins(self):
		make_background_check(
			self.person, 400, status="Cleared", completed_on=add_days(today(), -390), expires_on="2099-01-01"
		)
		make_background_check(self.person, 10, status="Pending")
		make_background_check(self.person, 200, status="Not Cleared", completed_on=add_days(today(), -190))

		result = summary(self.person)

		self.assertEqual(
			(result.background_check_status, result.background_check_expires_on), ("Pending", None)
		)

	def test_two_checks_requested_on_one_day_go_to_the_one_entered_last(self):
		make_background_check(self.person, 10, status="Pending")
		make_background_check(self.person, 10, status="Requested")

		self.assertEqual(summary(self.person).background_check_status, "Requested")

	def test_an_expired_check_shows_as_expired_with_its_expiry(self):
		expires_on = add_days(today(), -1)
		make_background_check(
			self.person, 1200, status="Cleared", completed_on=add_days(today(), -1190), expires_on=expires_on
		)

		result = summary(self.person)

		self.assertEqual(result.background_check_status, "Expired")
		self.assertEqual(result.background_check_expires_on, getdate(expires_on))

	def test_a_cleared_check_reads_expired_before_the_daily_job_marks_it(self):
		"""The scheduler runs the daily jobs in random order, so the summary cannot wait for expire_background_checks."""
		check = make_background_check(self.person, 30, status="Cleared", completed_on=add_days(today(), -20))
		frappe.db.set_value("Background Check", check.name, "expires_on", add_days(today(), -1))

		self.assertEqual(summary(self.person).background_check_status, "Expired")
		self.assertEqual(frappe.db.get_value("Background Check", check.name, "status"), "Cleared")

	def test_nothing_on_file_leaves_the_fields_empty(self):
		self.assertFalse(any(summary(self.person).values()))

	def test_saving_a_record_queues_the_person_it_had_and_has(self):
		other = make_person("_Test Cared For", "Other").name
		for record in (
			make_care_request(self.person),
			make_visit(self.person, -1),
			make_background_check(self.person, 1),
		):
			with self.subTest(record.doctype):
				record.person = other
				queued = queued_people(lambda: record.save(ignore_permissions=True))

				self.assertEqual(queued, [sorted([self.person, other])])


class TestCareFieldsArePastoral(RollbackEachTest):
	"""The care fields sit at permlevel 3: the Church Care Team profile reads and filters on them, other staff never do."""

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Pastoral", "Summary").name
		make_care_request(self.person)
		refresh([self.person])

	def as_user(self, key, roles):
		frappe.set_user(ensure_user(f"_test_care_summary_{key}@example.com", key, roles=roles))

	def test_pastoral_care_reads_and_filters_on_the_care_fields(self):
		self.as_user("care_team", ("Church Staff", "Church Pastoral Care"))

		rows = frappe.get_list(
			"Person",
			filters={"name": self.person, "open_care_requests": (">", 0)},
			fields=["name", *care.FIELDS],
		)

		self.assertEqual([row.open_care_requests for row in rows], [1])
		self.assertEqual(set(rows[0]), {"name", *care.FIELDS})

	def test_other_staff_neither_read_nor_filter_on_the_care_fields(self):
		self.as_user("staff", ("Church Staff",))

		rows = frappe.get_list("Person", filters={"name": self.person}, fields=["name", *care.FIELDS])
		self.assertEqual(rows, [{"name": self.person}])
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Person", filters={"open_care_requests": (">", 0)})


class TestCareStaysInItsChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_records_kept_at_a_former_church_do_not_count(self):
		"""Each record takes the person's church when it is made, and stays there when the person moves."""
		person = make_person("_Test Moved", "Care", church=self.branch_b)
		make_care_request(person.name)
		make_visit(person.name, -3)
		make_background_check(person.name, 3)
		person.church = self.branch_a
		person.save(ignore_permissions=True)

		self.assertFalse(any(summary(person.name).values()))

		make_care_request(person.name)
		make_visit(person.name, -2)
		make_background_check(person.name, 2, status="Pending")

		result = summary(person.name)
		self.assertEqual(result.open_care_requests, 1)
		self.assertEqual(result.last_visited_on, getdate(add_days(today(), -2)))
		self.assertEqual(result.background_check_status, "Pending")
