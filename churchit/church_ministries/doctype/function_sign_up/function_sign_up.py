import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum

from churchit.utils import resolve_link_titles


class FunctionSignUp(Document):
	def validate(self):
		if not frappe.db.get_value("Function", self.function, "allow_sign_ups"):
			frappe.throw("Sign ups are not enabled for this function.")

		# Prevent duplicate sign-ups for the same function and person
		if frappe.db.exists(
			"Function Sign-Up", {"function": self.function, "person": self.person, "name": ("!=", self.name)}
		):
			frappe.throw("This person has already signed up for this function.")

		user_roles = frappe.get_roles(frappe.session.user)
		is_manager = "Church Manager" in user_roles or "System Manager" in user_roles
		if not is_manager:
			# Force person from the linked Person record to prevent tampering
			person_name = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
			if not person_name:
				frappe.throw("No Person record is linked to your account.")
			self.person = person_name

	def before_save(self):
		function_label = (
			frappe.db.get_value("Function", self.function, "function_name") if self.function else ""
		)
		person_label = frappe.db.get_value("Person", self.person, "full_name") if self.person else ""
		parts = [function_label or "", person_label or ""]
		self.title = " - ".join(p for p in parts if p)

		if self.attending:
			self._add_attendance_record()
		else:
			self._remove_attendance_record()

	def on_trash(self):
		self._remove_attendance_record()

	def _add_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person:
				if row.attendance_type != "Signed-Up":
					row.attendance_type = "Signed-Up"
					function_doc.save(ignore_permissions=True)
				return
		function_doc.append(
			"attendance",
			{
				"person": self.person,
				"attendance_type": "Signed-Up",
			},
		)
		function_doc.save(ignore_permissions=True)

	def _remove_attendance_record(self):
		function_doc = frappe.get_doc("Function", self.function)
		for row in function_doc.attendance:
			if row.person == self.person and row.attendance_type == "Signed-Up":
				function_doc.remove(row)
				function_doc.save(ignore_permissions=True)
				frappe.msgprint("The associated attendance record has been removed.")
				return


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_function_items(doctype, txt, searchfield, start, page_len, filters):
	"""Search query: only Sign-Up Items configured on the given Function."""
	function = (filters or {}).get("function")
	if not function:
		return []
	Item = frappe.qb.DocType("Function Sign-Up Item")
	return (
		frappe.qb.from_(Item)
		.select(Item.item)
		.where((Item.parent == function) & (Item.parenttype == "Function") & Item.item.like(f"%{txt or ''}%"))
		.orderby(Item.idx)
		.limit(page_len or 20)
		.offset(start or 0)
		.run()
	)


@frappe.whitelist()
def get_item_status(function, item, exclude_sign_up=None):
	"""Return live quantity_needed (from the Function) and quantity_signed_up
	(summed across all Function Sign-Ups for the same function/item).

	Args:
		function: Function document name.
		item: Sign-Up Item name.
		exclude_sign_up: Optional Function Sign-Up name to exclude from totals
			(used when editing an existing sign-up to show others' contributions).
	"""
	qty_needed = frappe.db.get_value(
		"Function Sign-Up Item",
		{"parent": function, "parenttype": "Function", "item": item},
		"quantity_needed",
	)

	Item = frappe.qb.DocType("Function Sign-Up Item")
	SignUp = frappe.qb.DocType("Function Sign-Up")

	query = (
		frappe.qb.from_(Item)
		.join(SignUp)
		.on(SignUp.name == Item.parent)
		.select(Coalesce(Sum(Item.my_quantity), 0).as_("total"))
		.where((SignUp.function == function) & (Item.parenttype == "Function Sign-Up") & (Item.item == item))
	)
	if exclude_sign_up:
		query = query.where(SignUp.name != exclude_sign_up)

	result = query.run(as_dict=True)
	qty_signed_up = (result[0].total if result else 0) or 0

	return {
		"quantity_needed": qty_needed or 0,
		"quantity_signed_up": int(qty_signed_up),
	}


@frappe.whitelist()
def get_function_item_totals(function, exclude_sign_up=None):
	"""Return live quantity_signed_up totals for every item configured on a Function.

	Returns a dict mapping item -> {quantity_needed, quantity_signed_up}.
	"""
	function_items = frappe.db.get_all(
		"Function Sign-Up Item",
		filters={"parent": function, "parenttype": "Function"},
		fields=["item", "quantity_needed"],
	)

	Item = frappe.qb.DocType("Function Sign-Up Item")
	SignUp = frappe.qb.DocType("Function Sign-Up")

	query = (
		frappe.qb.from_(Item)
		.join(SignUp)
		.on(SignUp.name == Item.parent)
		.select(Item.item, Coalesce(Sum(Item.my_quantity), 0).as_("total"))
		.where((SignUp.function == function) & (Item.parenttype == "Function Sign-Up"))
	)
	if exclude_sign_up:
		query = query.where(SignUp.name != exclude_sign_up)

	totals = {row.item: int(row.total or 0) for row in query.groupby(Item.item).run(as_dict=True)}

	return {
		row.item: {
			"quantity_needed": row.quantity_needed or 0,
			"quantity_signed_up": totals.get(row.item, 0),
		}
		for row in function_items
	}


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
