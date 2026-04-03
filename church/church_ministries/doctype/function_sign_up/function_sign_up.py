import frappe
from frappe.model.document import Document


class FunctionSignUp(Document):
	def before_save(self):
		parts = [self.function or "", self.person or ""]
		self.title = " - ".join(p for p in parts if p)

	def validate(self):
		if not frappe.db.get_value("Function", self.function, "allow_sign_ups"):
			frappe.throw("Sign ups are not enabled for this function.")

		user_roles = frappe.get_roles(frappe.session.user)
		is_manager = "Church Manager" in user_roles or "System Manager" in user_roles
		if not is_manager:
			# Force person and church from the linked Person record to prevent tampering
			person = frappe.db.get_value("Person", {"portal_user": frappe.session.user}, ["name", "church"], as_dict=True)
			if not person:
				frappe.throw("No Person record is linked to your account.")
			self.person = person.name
			self.church = person.church

	def after_insert(self):
		if self.attending:
			self._add_attendance_record()

	def _add_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person:
				if row.attendance_type != "Self-Reported":
					row.attendance_type = "Self-Reported"
					function_doc.save(ignore_permissions=True)
				return
		function_doc.append("attendance", {
			"person": self.person,
			"attendance_type": "Self-Reported",
		})
		function_doc.save(ignore_permissions=True)
