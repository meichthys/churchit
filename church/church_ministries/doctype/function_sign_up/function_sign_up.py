import frappe
from frappe.model.document import Document


class FunctionSignUp(Document):
	def after_insert(self):
		if self.attending:
			self._add_attendance_record()

	def _add_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person:
				if row.attendance_type != "Assumed":
					row.attendance_type = "Assumed"
					function_doc.save(ignore_permissions=True)
				return
		function_doc.append("attendance", {
			"person": self.person,
			"attendance_type": "Assumed",
		})
		function_doc.save(ignore_permissions=True)
