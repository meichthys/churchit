# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe import _
from frappe.model.document import Document

from churchit.church_scope import refuse_another_churches_parent


class CareAssignment(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "person", _("{0} belongs to another church, so only that church can give them a deacon.")
		)
