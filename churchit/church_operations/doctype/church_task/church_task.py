# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.form.assign_to import close_all_assignments
from frappe.utils import getdate
from frappe.utils.nestedset import NestedSet

from churchit.church_scope import refuse_another_churches_record

LINKED_RECORDS = {"requester": "Person", "asset": "Church Asset", "room": "Room"}

DUE_NOTIFICATION = "Church Task Due"
DUE_MESSAGE = """<p>A task assigned to you is due {{ frappe.utils.format_datetime(doc.due_date) }}.</p>

<ul>
  <li><strong>Task:</strong> {{ doc.title | e }}</li>
  <li><strong>Status:</strong> {{ doc.status }}</li>
  <li><strong>Priority:</strong> {{ doc.priority }}</li>
</ul>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the task</a></p>
"""


class ChurchTask(NestedSet):
	def validate(self):
		# A link checked once stays, so a later save does not fail when the record moves church.
		for fieldname, doctype in LINKED_RECORDS.items():
			if self.has_value_changed(fieldname) or self.has_value_changed("church"):
				refuse_another_churches_record(self, doctype, self.get(fieldname))

	def on_update(self):
		super().on_update()
		# Frappe's assignments (ToDo) own the assignee, and the task owns their date.
		if self.has_value_changed("due_date"):
			self.date_assignments()
		if self.has_value_changed("status") and self.status == "Completed":
			close_all_assignments(self.doctype, self.name, ignore_permissions=True)

	def date_assignments(self):
		frappe.db.set_value(
			"ToDo",
			{"reference_type": self.doctype, "reference_name": self.name, "status": "Open"},
			"date",
			getdate(self.due_date) if self.due_date else None,
		)


def on_assignment(doc, method=None):
	"""ToDo after_insert: an Open Church Task that gets an assignee becomes Assigned."""
	if doc.reference_type != "Church Task":
		return
	task = frappe.get_doc("Church Task", doc.reference_name, for_update=True)
	# Each assignee gets the task's reminder, so only a user who may change the task assigns it.
	task.check_permission("write")
	if doc.status != "Open":
		return
	if task.due_date:
		doc.db_set("date", getdate(task.due_date))
	if task.status == "Open":
		# A real save, so the timeline and an open form see the change.
		task.status = "Assigned"
		task.save(ignore_permissions=True)


def refuse_moved_assignment(doc, method=None):
	"""ToDo validate: moving a ToDo onto a Church Task needs write on the task, like a new one."""
	if doc.is_new() or doc.reference_type != "Church Task":
		return
	if doc.has_value_changed("reference_type") or doc.has_value_changed("reference_name"):
		frappe.get_doc("Church Task", doc.reference_name).check_permission("write")


def create_due_notification() -> None:
	"""Insert the Notification that reminds a task's assignees the day before it is due, once.

	It is not standard, because production cannot enable a shipped one, and a church may change it.
	"""
	if frappe.db.exists("Notification", DUE_NOTIFICATION):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": DUE_NOTIFICATION,
			"subject": "Task due: {{ doc.title }}",
			"document_type": "Church Task",
			"event": "Days Before",
			"date_changed": "due_date",
			"days_in_advance": 1,
			"condition_type": "Python",
			"condition": 'doc.status != "Completed"',
			"channel": "Email",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"send_to_all_assignees": 1,
			"message_type": "HTML",
			"message": DUE_MESSAGE,
		}
	).insert(ignore_permissions=True)
