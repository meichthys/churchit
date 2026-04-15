import frappe
from frappe.model.document import Document

from church.utils import resolve_link_titles


class FunctionSignUp(Document):
	def before_save(self):
		function_label = frappe.db.get_value("Function", self.function, "function_name") if self.function else ""
		person_label = frappe.db.get_value("Person", self.person, "full_name") if self.person else ""
		parts = [function_label or "", person_label or ""]
		self.title = " - ".join(p for p in parts if p)

	def validate(self):
		if not frappe.db.get_value("Function", self.function, "allow_sign_ups"):
			frappe.throw("Sign ups are not enabled for this function.")

		user_roles = frappe.get_roles(frappe.session.user)
		is_manager = "Church Manager" in user_roles or "System Manager" in user_roles
		if not is_manager:
			# Force person from the linked Person record to prevent tampering
			person_name = frappe.db.get_value("Person", {"portal_user": frappe.session.user}, "name")
			if not person_name:
				frappe.throw("No Person record is linked to your account.")
			self.person = person_name

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


def get_list_context(context):
	context.filters = {"owner": frappe.session.user}
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		from frappe.www.list import get_list as default_get_list

		rows = default_get_list(doctype, txt, filters, limit_start, limit_page_length, **kwargs)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context
