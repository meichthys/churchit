# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_scope import default_church, is_multi_church, refuse_another_churches_record


class GLAccountMapping(Document):
	def validate(self):
		# ensure_church runs after this method, so a new mapping may not have its church yet.
		church = (self.church or default_church()) if is_multi_church() else None
		if self.mapping_for == "Fund":
			refuse_another_churches_record(self, "Fund", self.record)
		if self.mapping_for == "Church" and church and self.record != church:
			frappe.throw(_("A Church mapping holds the account that pays the expenses of its own church."))
		self.refuse_a_second_mapping(church)

	def refuse_a_second_mapping(self, church):
		# Two saves for one record wait on its row, and the locking read sees a mapping the other committed.
		frappe.db.get_value(self.mapping_for, self.record, "name", for_update=True)
		filters = {"mapping_for": self.mapping_for, "record": self.record, "name": ("!=", self.name)}
		if church:
			filters["church"] = church
		other = frappe.db.get_value("GL Account Mapping", filters, "account", for_update=True)
		if other:
			frappe.throw(
				_("{0} {1} is already mapped to account {2}.").format(
					_(self.mapping_for), self.record, other
				),
				frappe.DuplicateEntryError,
			)
