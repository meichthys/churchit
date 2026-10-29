# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_scope import refuse_another_churches_parent


class PickupRestriction(Document):
	def validate(self):
		refuse_another_churches_parent(
			self,
			"child",
			_("{0} belongs to another church, so only that church can restrict who collects them."),
		)
		if not (self.restricted_person or self.restricted_name):
			frappe.throw(_("Choose the Restricted Person or type their name."))
		if self.restricted_person == self.child:
			frappe.throw(_("The Restricted Person cannot be the child."))
		if self.court_order and not frappe.db.get_value("File", {"file_url": self.court_order}, "is_private"):
			frappe.throw(_("Attach the court order as a private file, so only staff can open it."))
