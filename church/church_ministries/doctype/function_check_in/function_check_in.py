# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


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

	def after_insert(self):
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
				frappe.msgprint("The associated attendance record has been removed.")
				return
