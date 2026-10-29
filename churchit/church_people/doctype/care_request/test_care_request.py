# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.form import assign_to
from frappe.email.doctype.notification.notification import get_context
from frappe.utils import add_days, getdate, nowdate

from churchit.patches.v1_0.rename_care_request_assigned_to import execute as rename_assigned_to
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches
from churchit.tests.test_notification_templates import shipped_templates


class CareRequestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.category = ensure("Care Request Type", {"type": "_Test Need"})
		cls.person = make_person("_Test Care", "Requester").name

	def request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": self.person,
				"category": self.category,
				"description": "Needs a hand",
				**values,
			}
		).insert(ignore_permissions=True)

	@classmethod
	def make_caregiver(cls, first_name, roles=("Church Pastoral Care",), **values):
		"""A Person with a desk login holding *roles*; returns (person, user)."""
		user = ensure_user(f"_test_care_{frappe.scrub(first_name)}@example.com", first_name, roles=roles)
		return make_person(first_name, "Caregiver", user=user, **values).name, user

	def todos(self, request, status="Open"):
		return frappe.get_all(
			"ToDo",
			filters={"reference_type": "Care Request", "reference_name": request.name, "status": status},
			fields=["allocated_to", "date"],
		)


class TestCareRequest(CareRequestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.deacon = make_person("_Test Care", "Deacon").name

	def assign_deacon(self, deacon, start_date, end_date=None):
		return frappe.get_doc(
			{
				"doctype": "Care Assignment",
				"person": self.person,
				"deacon": deacon,
				"start_date": start_date,
				"end_date": end_date,
			}
		).insert(ignore_permissions=True)

	def test_caregiver_defaults_to_the_current_deacon(self):
		self.assign_deacon(self.deacon, add_days(nowdate(), -10))
		self.assertEqual(self.request().caregiver, self.deacon)

	def test_ended_assignments_are_ignored(self):
		self.assign_deacon(self.deacon, add_days(nowdate(), -30), end_date=add_days(nowdate(), -1))
		self.assertIsNone(self.request().caregiver)

	def test_assignment_ending_today_still_counts(self):
		self.assign_deacon(self.deacon, add_days(nowdate(), -30), end_date=nowdate())
		self.assertEqual(self.request().caregiver, self.deacon)

	def test_explicit_caregiver_is_kept(self):
		self.assign_deacon(self.deacon, add_days(nowdate(), -10))
		other = make_person("_Test Care", "Other Deacon").name
		self.assertEqual(self.request(caregiver=other).caregiver, other)

	def test_person_defaults_to_the_logged_in_users_person(self):
		user = ensure_user("_test_care_user@example.com", "_Test Care User")
		frappe.db.set_value("Person", self.person, "user", user)
		frappe.set_user(user)

		request = frappe.get_doc(
			{"doctype": "Care Request", "category": self.category, "description": "Portal ask"}
		).insert(ignore_permissions=True)
		self.assertEqual(request.person, self.person)


class TestDueDates(CareRequestCase):
	def test_the_due_date_follows_the_urgency(self):
		for urgency, days in (("Urgent", 1), ("High", 3), ("Medium", 7), ("Low", 14)):
			self.assertEqual(
				getdate(self.request(urgency=urgency).due_on), getdate(add_days(nowdate(), days))
			)

	def test_a_request_entered_late_is_due_from_the_day_it_was_submitted(self):
		request = self.request(urgency="Medium", submitted_on=add_days(nowdate(), -5))
		self.assertEqual(getdate(request.due_on), getdate(add_days(nowdate(), 2)))

	def test_a_due_date_typed_in_is_kept(self):
		self.assertEqual(str(self.request(due_on="2031-01-01").due_on), "2031-01-01")

	def test_a_new_urgency_counts_from_today(self):
		request = self.request(urgency="Low", submitted_on=add_days(nowdate(), -5))
		request.urgency = "Urgent"
		request.save(ignore_permissions=True)
		self.assertEqual(getdate(request.due_on), getdate(add_days(nowdate(), 1)))

	def test_a_due_date_changed_with_the_urgency_is_kept(self):
		request = self.request(urgency="Low")
		request.update({"urgency": "Urgent", "due_on": "2031-01-01"})
		request.save(ignore_permissions=True)
		self.assertEqual(str(request.due_on), "2031-01-01")


class TestCaregiverToDo(CareRequestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.anna, cls.anna_user = cls.make_caregiver("Anna")
		cls.ben, cls.ben_user = cls.make_caregiver("Ben")

	def test_assigning_from_the_sidebar_leaves_the_caregiver_alone(self):
		"""Frappe writes the assignee's User ID into a field named assigned_to, which was a Person link."""
		request = self.request(caregiver=self.anna)

		assign_to.add({"assign_to": [self.ben_user], "doctype": "Care Request", "name": request.name})
		self.assertEqual(frappe.db.get_value("Care Request", request.name, "caregiver"), self.anna)
		assign_to.remove("Care Request", request.name, self.ben_user)
		self.assertEqual(frappe.db.get_value("Care Request", request.name, "caregiver"), self.anna)

	def test_the_caregiver_gets_a_to_do_dated_when_the_request_is_due(self):
		request = self.request(caregiver=self.anna, urgency="High")

		self.assertEqual(
			[(row.allocated_to, getdate(row.date)) for row in self.todos(request)],
			[(self.anna_user, getdate(request.due_on))],
		)

	def test_the_to_do_moves_with_the_caregiver(self):
		request = self.request(caregiver=self.anna)
		request.caregiver = self.ben
		request.save(ignore_permissions=True)

		self.assertEqual([row.allocated_to for row in self.todos(request)], [self.ben_user])
		self.assertEqual([row.allocated_to for row in self.todos(request, "Cancelled")], [self.anna_user])

	def test_the_to_do_date_moves_with_the_due_date(self):
		request = self.request(caregiver=self.anna, urgency="Low")
		request.urgency = "Urgent"
		request.save(ignore_permissions=True)

		self.assertEqual(
			[getdate(row.date) for row in self.todos(request)], [getdate(add_days(nowdate(), 1))]
		)

	def test_resolving_closes_the_to_do_and_reopening_brings_it_back(self):
		request = self.request(caregiver=self.anna)
		request.status = "Resolved"
		request.save(ignore_permissions=True)
		self.assertEqual(self.todos(request), [])
		self.assertEqual(len(self.todos(request, "Closed")), 1)

		request.status = "In Progress"
		request.save(ignore_permissions=True)
		self.assertEqual([row.allocated_to for row in self.todos(request)], [self.anna_user])

	def test_a_caregiver_without_a_desk_login_gets_no_to_do_and_the_user_is_told(self):
		frappe.clear_messages()
		request = self.request(caregiver=make_person("_Test Care", "Offline").name)

		self.assertEqual(self.todos(request), [])
		self.assertTrue(any("no desk login" in str(message) for message in frappe.message_log))

	def test_a_care_team_member_hands_a_request_to_staff_who_could_not_open_it(self):
		"""Frappe shares with an assignee who cannot read the record only if the assigner may share."""
		staff, staff_user = self.make_caregiver("Stella", roles=("Church Staff",))
		request = self.request()

		frappe.set_user(self.anna_user)
		request.reload()
		request.caregiver = staff
		request.save()

		frappe.set_user(staff_user)
		self.assertTrue(frappe.has_permission("Care Request", "read", doc=request.name))
		self.assertEqual([row.allocated_to for row in self.todos(request)], [staff_user])

	def test_a_portal_request_reaches_the_deacon(self):
		member = ensure_user("_test_care_member@example.com", "Member")
		requester = make_person("_Test Care", "Member", user=member).name
		frappe.get_doc(
			{"doctype": "Care Assignment", "person": requester, "deacon": self.anna, "start_date": nowdate()}
		).insert(ignore_permissions=True)

		frappe.set_user(member)
		request = frappe.get_doc(
			{"doctype": "Care Request", "category": self.category, "description": "Portal ask"}
		).insert()

		frappe.set_user("Administrator")
		self.assertEqual([row.allocated_to for row in self.todos(request)], [self.anna_user])


class TestCaregiverChurch(CareRequestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.person = make_person("_Test Care", "In B", church=cls.branch_b).name

	def test_a_caregiver_from_another_church_is_refused_clearly(self):
		outsider, _user = self.make_caregiver("Outsider", roles=("Church Manager",), church=self.branch_a)

		with self.assertRaisesRegex(
			frappe.ValidationError, "cannot see the care requests of <strong>_Test Scope B"
		):
			self.request(caregiver=outsider)

	def test_a_caregiver_from_the_requests_church_gets_the_to_do(self):
		insider, user = self.make_caregiver("Insider", church=self.branch_b)
		self.assertEqual([row.allocated_to for row in self.todos(self.request(caregiver=insider))], [user])


class TestCareRequestOverdue(CareRequestCase):
	def test_the_notice_names_the_person_category_and_caregiver(self):
		caregiver, _user = self.make_caregiver("Notice")
		request = self.request(caregiver=caregiver, due_on=add_days(nowdate(), -1))
		notification, markdown = shipped_templates("church_communications", "Care Request Overdue")

		for template in (notification["subject"], notification["message"], markdown):
			rendered = frappe.render_template(template, get_context(request))
			self.assertIn("_Test Care Requester", rendered)
			self.assertIn("_Test Need", rendered)
		self.assertIn(
			"Notice Caregiver", frappe.render_template(notification["message"], get_context(request))
		)
		self.assertEqual(notification["message"], markdown)

	def test_it_goes_out_the_day_after_an_open_request_was_due(self):
		caregiver, user = self.make_caregiver("Late")
		late = self.request(caregiver=caregiver, due_on=add_days(nowdate(), -1))
		resolved = self.request(due_on=add_days(nowdate(), -1), status="Resolved")
		not_yet = self.request(due_on=nowdate())
		notice = frappe.get_doc("Notification", "Care Request Overdue")

		due = [doc.name for doc in notice.get_documents_for_today()]
		self.assertIn(late.name, due)
		self.assertNotIn(resolved.name, due)
		self.assertNotIn(not_yet.name, due)
		self.assertFalse(notice.enabled)
		self.assertIn(user, notice.get_list_of_recipients(late, get_context(late))[0])


class TestRenameAssignedTo(CareRequestCase):
	def setUp(self):
		super().setUp()
		if not frappe.db.has_column("Care Request", "assigned_to"):
			self.skipTest("this site never had Assigned To")
		Request = frappe.qb.DocType("Care Request")
		frappe.qb.update(Request).set(Request.caregiver, None).run()

	def set_old_value(self, request, value):
		Request = frappe.qb.DocType("Care Request")
		frappe.qb.update(Request).set(Request.assigned_to, value).where(Request.name == request.name).run()

	def caregiver_of(self, request):
		return frappe.db.get_value("Care Request", request.name, "caregiver")

	def test_values_move_and_a_user_id_becomes_that_users_person(self):
		deacon = make_person("_Test Rename", "Deacon").name
		helper, helper_user = self.make_caregiver("Helper")
		by_person, by_user, by_stranger = self.request(), self.request(), self.request()
		self.set_old_value(by_person, deacon)
		self.set_old_value(by_user, helper_user)
		self.set_old_value(by_stranger, "_test_rename_nobody@example.com")

		rename_assigned_to()

		self.assertEqual(self.caregiver_of(by_person), deacon)
		self.assertEqual(self.caregiver_of(by_user), helper)
		self.assertIsNone(self.caregiver_of(by_stranger))

	def test_a_second_run_keeps_caregivers_set_since(self):
		request = self.request()
		self.set_old_value(request, make_person("_Test Rename", "First").name)
		rename_assigned_to()
		later = make_person("_Test Rename", "Later").name
		frappe.db.set_value("Care Request", request.name, "caregiver", later)

		rename_assigned_to()

		self.assertEqual(self.caregiver_of(request), later)
