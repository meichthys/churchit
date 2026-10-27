# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.desk.form import assign_to
from frappe.email.doctype.notification.notification import get_context
from frappe.utils import add_days, getdate, today

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.church_task.church_task import (
	DUE_NOTIFICATION,
	create_due_notification,
)
from churchit.connections import get_open_count
from churchit.patches.v1_0 import add_church_task_due_notification
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)


def make_task(title, **values):
	return frappe.get_doc({"doctype": "Church Task", "title": title, **values}).insert(
		ignore_permissions=True
	)


def make_asset(title, church, **values):
	return (
		frappe.get_doc({"doctype": "Church Asset", "title": title, "church": church, **values})
		.insert(ignore_permissions=True)
		.name
	)


def assign(task, user):
	assign_to.add({"doctype": "Church Task", "name": task.name, "assign_to": [user]})


def todos(task, status="Open"):
	return frappe.get_all(
		"ToDo",
		filters={"reference_type": "Church Task", "reference_name": task.name, "status": status},
		fields=["allocated_to", "date"],
	)


def forge_todo(task, user):
	"""Insert, as *user*, a ToDo for *task* allocated to *user*, the way POST /api/resource/ToDo does."""
	frappe.set_user(user)
	try:
		todo = {"allocated_to": user, "reference_type": "Church Task", "reference_name": task}
		return frappe.get_doc({"doctype": "ToDo", "description": "_Test forged", **todo}).insert()
	finally:
		frappe.set_user("Administrator")


def move_todo(task, user):
	"""As *user*, insert a plain ToDo for *user*, then move it onto *task*, the way PUT /api/resource/ToDo does."""
	frappe.set_user(user)
	try:
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "_Test plain todo", "allocated_to": user}
		).insert()
		todo = frappe.get_doc("ToDo", todo.name)
		todo.update({"reference_type": "Church Task", "reference_name": task})
		return todo.save()
	finally:
		frappe.set_user("Administrator")


class TaskUsersTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.staff = ensure_user("_test_task_staff@example.com", "Task Staff", roles=("Church Staff",))
		cls.other_staff = ensure_user("_test_task_other@example.com", "Task Other", roles=("Church Staff",))


class TestTaskAssignment(TaskUsersTestCase):
	def test_assigning_an_open_task_marks_it_assigned_and_dates_the_todo(self):
		task = make_task("_Test Task Assigned", due_date="2031-05-03 10:00:00")

		assign(task, self.staff)

		self.assertEqual(frappe.db.get_value("Church Task", task.name, "status"), "Assigned")
		self.assertEqual(todos(task), [{"allocated_to": self.staff, "date": getdate("2031-05-03")}])

	def test_assigning_a_task_in_progress_keeps_its_status(self):
		task = make_task("_Test Task Underway", status="In Progress")

		assign(task, self.staff)

		self.assertEqual(frappe.db.get_value("Church Task", task.name, "status"), "In Progress")

	def test_a_todo_for_another_doctype_inserts(self):
		person = make_person("_Test Task", "Other Record").name

		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "_Test other record",
				"allocated_to": self.staff,
				"reference_type": "Person",
				"reference_name": person,
			}
		).insert(ignore_permissions=True)

		self.assertTrue(frappe.db.exists("ToDo", todo.name))

	def test_a_user_who_cannot_change_the_task_cannot_assign_it(self):
		task = make_task("_Test Task Forged", due_date="2031-07-09 10:00:00")
		outsider = ensure_user("_test_task_outsider@example.com", "Task Outsider", roles=())

		with self.assertRaises(frappe.PermissionError):
			forge_todo(task.name, outsider)

		self.assertEqual(frappe.db.get_value("Church Task", task.name, "status"), "Open")
		# The request rolls the ToDo back; here it stays, without the task's due date.
		self.assertNotIn(getdate("2031-07-09"), [todo.date for todo in todos(task)])

	def test_moving_a_todo_onto_a_task_needs_write_on_it(self):
		task = make_task("_Test Task Moved Onto")
		outsider = ensure_user("_test_task_mover@example.com", "Task Mover", roles=("Church User",))

		with self.assertRaises(frappe.PermissionError):
			move_todo(task.name, outsider)
		move_todo(task.name, self.staff)

		self.assertEqual(
			frappe.parse_json(frappe.db.get_value("Church Task", task.name, "_assign")), [self.staff]
		)

	def test_a_new_due_date_moves_the_open_assignments(self):
		task = make_task("_Test Task Moved", due_date="2031-05-03 10:00:00")
		assign(task, self.staff)
		task.reload()

		task.due_date = "2031-06-10 09:00:00"
		task.save()

		self.assertEqual(todos(task)[0].date, getdate("2031-06-10"))

	def test_completing_the_task_closes_its_assignments(self):
		task = make_task("_Test Task Done")
		assign(task, self.staff)
		assign(task, self.other_staff)
		task.reload()

		task.status = "Completed"
		task.save()

		self.assertEqual(todos(task), [])
		self.assertEqual(len(todos(task, "Closed")), 2)
		self.assertIsNone(frappe.db.get_value("Church Task", task.name, "_assign") or None)


class TestChurchTaskDue(TaskUsersTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.delete_doc_if_exists("Notification", DUE_NOTIFICATION)
		create_due_notification()

	def setUp(self):
		super().setUp()
		self.notification = frappe.get_doc("Notification", DUE_NOTIFICATION)
		self.tomorrow = f"{add_days(today(), 1)} 10:00:00"

	def due_tomorrow(self):
		return [doc.name for doc in self.notification.get_documents_for_today()]

	def test_a_task_due_tomorrow_reaches_only_its_assignees(self):
		task = make_task("_Test Task Due", due_date=self.tomorrow)
		assign(task, self.staff)
		other = make_task("_Test Task Due Elsewhere", due_date=self.tomorrow)
		assign(other, self.other_staff)
		task.reload()

		recipients, cc, bcc = self.notification.get_list_of_recipients(task, get_context(task))

		self.assertIn(task.name, self.due_tomorrow())
		self.assertEqual((recipients, cc, bcc), ([self.staff], [], []))

	def test_a_completed_or_later_task_is_not_reminded(self):
		done = make_task("_Test Task Due Done", due_date=self.tomorrow)
		done.status = "Completed"
		done.save()
		later = make_task("_Test Task Due Later", due_date=f"{add_days(today(), 5)} 10:00:00")

		self.assertNotIn(done.name, self.due_tomorrow())
		self.assertNotIn(later.name, self.due_tomorrow())

	def test_the_notification_is_added_once_and_a_churchs_change_stays(self):
		frappe.db.set_value("Notification", DUE_NOTIFICATION, "days_in_advance", 3)

		with patch.dict(frappe.flags, {"in_patch": True}):
			for _run in range(2):
				add_church_task_due_notification.execute()

		notification = frappe.get_doc("Notification", DUE_NOTIFICATION)
		self.assertEqual((notification.is_standard, notification.enabled, notification.module), (0, 1, None))
		self.assertEqual((notification.event, notification.date_changed), ("Days Before", "due_date"))
		self.assertEqual(notification.days_in_advance, 3)


class TestWorkOrders(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user("_test_work_manager_a@example.com", "Work A", roles=("Church Manager",))
		set_user_church(cls.manager_a, cls.branch_a)
		cls.staff_b = ensure_user("_test_work_staff_b@example.com", "Work B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)

		cls.asset_a = make_asset("_Test Work Mower A", cls.branch_a)
		cls.asset_b = make_asset("_Test Work Mower B", cls.branch_b)
		cls.shared_asset = make_asset("_Test Work Shared Organ", cls.branch_b, is_shared=1)
		cls.room_b = (
			frappe.get_doc({"doctype": "Room", "room_name": "_Test Work Hall B", "church": cls.branch_b})
			.insert(ignore_permissions=True)
			.name
		)
		cls.requester_b = make_person("_Test Work", "Requester B", church=cls.branch_b).name

	def tearDown(self):
		super().tearDown()
		# Frappe's get_open_count limits the session's statements to 1 second, meant to end with the request.
		frappe.db.set_execution_timeout(0)

	def work_order(self, title, user=None, **values):
		doc = frappe.get_doc({"doctype": "Church Task", "title": title, "task_type": "Work Order", **values})
		if not user:
			return doc.insert(ignore_permissions=True)
		frappe.set_user(user)
		try:
			return doc.insert()
		finally:
			frappe.set_user("Administrator")

	def test_another_churches_asset_room_or_requester_is_refused(self):
		for field, value in (("asset", self.asset_b), ("room", self.room_b), ("requester", self.requester_b)):
			with self.assertRaises(frappe.PermissionError, msg=field):
				self.work_order("_Test Work Refused", self.manager_a, **{field: value})

	def test_a_shared_asset_and_the_churchs_own_asset_save(self):
		order = self.work_order(
			"_Test Work Shared", self.manager_a, asset=self.shared_asset, priority="Urgent"
		)
		own = self.work_order("_Test Work Own", self.manager_a, asset=self.asset_a)

		self.assertEqual((order.church, order.priority), (self.branch_a, "Urgent"))
		self.assertEqual(own.asset, self.asset_a)

	def test_an_unchanged_asset_is_not_checked_again(self):
		order = self.work_order("_Test Work Moved Asset", church=self.branch_a, asset=self.asset_a)
		frappe.db.set_value("Church Asset", self.asset_a, "church", self.branch_b)

		order.status = "In Progress"
		order.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Church Task", order.name, "status"), "In Progress")

	def test_an_assignee_of_another_church_is_refused(self):
		order = self.work_order("_Test Work Assigned Across", church=self.branch_a)

		with self.assertRaises(frappe.PermissionError):
			assign(order, self.staff_b)

	def test_a_user_of_another_church_cannot_assign_themselves(self):
		order = self.work_order("_Test Work Forged", church=self.branch_a, due_date="2031-07-09 10:00:00")

		with self.assertRaises(frappe.PermissionError):
			forge_todo(order.name, self.staff_b)

		self.assertEqual(frappe.db.get_value("Church Task", order.name, "status"), "Open")
		self.assertNotIn(getdate("2031-07-09"), [todo.date for todo in todos(order)])

	def test_moving_a_work_order_to_another_church_checks_its_links(self):
		order = self.work_order("_Test Work Moved Church", church=self.branch_a, asset=self.asset_a)

		order.church = self.branch_b
		with self.assertRaises(frappe.PermissionError):
			order.save(ignore_permissions=True)

	def test_open_work_orders_lists_only_the_readers_church(self):
		open_a = self.work_order("_Test Work Open A", church=self.branch_a, due_date="2031-05-04 09:00:00")
		first_a = self.work_order("_Test Work First A", church=self.branch_a, due_date="2031-05-01 09:00:00")
		done_a = self.work_order("_Test Work Done A", church=self.branch_a, status="Completed")
		task_a = make_task("_Test Work Plain Task A", church=self.branch_a)
		open_b = self.work_order("_Test Work Open B", church=self.branch_b)
		report = frappe.get_doc("Report", "Open Work Orders")

		_columns, rows = report.get_data(user=self.manager_a, as_dict=True)
		shown = [
			row.name
			for row in rows
			if row.name in {open_a.name, first_a.name, done_a.name, task_a.name, open_b.name}
		]

		self.assertEqual(shown, [first_a.name, open_a.name])
		_columns, rows = report.get_data(user=self.staff_b, as_dict=True)
		self.assertIn(open_b.name, [row.name for row in rows])
		self.assertNotIn(open_a.name, [row.name for row in rows])

	def test_a_shared_asset_counts_only_the_readers_work_orders(self):
		self.work_order("_Test Work Count A", church=self.branch_a, asset=self.shared_asset)
		self.work_order(
			"_Test Work Count Done A", church=self.branch_a, asset=self.shared_asset, status="Completed"
		)
		self.work_order("_Test Work Count B", church=self.branch_b, asset=self.shared_asset)
		frappe.set_user(self.manager_a)

		found = get_open_count("Church Asset", self.shared_asset)["count"]["external_links_found"]

		self.assertEqual({row["doctype"]: row["count"] for row in found}, {"Church Task": 2})
