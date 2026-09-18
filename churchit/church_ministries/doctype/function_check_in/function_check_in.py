# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import secrets

import frappe
from frappe import _
from frappe.model.document import Document

# Letters and digits that are hard to confuse on a printed tag.
SECURITY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class FunctionCheckIn(Document):
	def validate(self):
		# Prevent duplicate check-ins for the same function and person
		if frappe.db.exists(
			"Function Check-In", {"function": self.function, "person": self.person, "name": ("!=", self.name)}
		):
			frappe.throw("This person has already been checked in to this function.")

	def before_save(self):
		function_label = (
			frappe.db.get_value("Function", self.function, "function_name") if self.function else ""
		)
		person_label = frappe.db.get_value("Person", self.person, "full_name") if self.person else ""
		parts = [function_label or "", person_label or ""]
		self.title = " - ".join(p for p in parts if p)

		self._add_attendance_record()

	def on_trash(self):
		self._remove_attendance_record()

	def _add_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person:
				if row.attendance_type != "Checked-In":
					row.attendance_type = "Checked-In"
					function_doc.save(ignore_permissions=True)
				return
		function_doc.append(
			"attendance",
			{
				"person": self.person,
				"attendance_type": "Checked-In",
			},
		)
		function_doc.save(ignore_permissions=True)

	def _remove_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person and row.attendance_type == "Checked-In":
				function_doc.remove(row)
				function_doc.save(ignore_permissions=True)
				frappe.msgprint(_("The associated attendance record has been removed."), alert=True)
				return


def new_security_code():
	return "".join(secrets.choice(SECURITY_CODE_ALPHABET) for _ in range(4))


@frappe.whitelist()
def check_in_persons(function_name, persons):
	"""Check *persons* in to a function. New check-ins made in one call share a security code."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	persons = frappe.parse_json(persons)

	code = None
	if frappe.db.get_single_value("Check-In Settings", "security_codes"):
		code = new_security_code()

	names = []
	for person in persons:
		existing = frappe.db.get_value(
			"Function Check-In", {"function": function_name, "person": person}, "name"
		)
		if existing:
			frappe.get_doc("Function Check-In", existing)._add_attendance_record()
			names.append(existing)
			continue
		check_in = frappe.get_doc(
			{
				"doctype": "Function Check-In",
				"function": function_name,
				"person": person,
				"security_code": code,
			}
		).insert(ignore_permissions=True)
		names.append(check_in.name)
	return names


@frappe.whitelist()
def print_name_tags(check_ins=None, persons=None):
	"""Name tags for saved check-ins, or plain tags for people who are not checked in."""
	docs = [frappe.get_doc("Function Check-In", name) for name in frappe.parse_json(check_ins) or []]
	for doc in docs:
		doc.check_permission("read")
	for person in frappe.parse_json(persons) or []:
		frappe.has_permission("Person", doc=person, throw=True)
		docs.append(frappe.get_doc({"doctype": "Function Check-In", "person": person}))
	if not docs:
		frappe.throw(_("Nothing to print."))
	return frappe.get_single("Check-In Settings").print_name_tags(docs)
