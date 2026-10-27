# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people import smart_lists
from churchit.church_people.followup import VALUE_TYPES


class FollowupTrigger(Document):
	"""Something that happens to a person and starts a card on the workflow. Its parent validates it."""

	def set_value_type(self):
		self.value_type = VALUE_TYPES.get(self.trigger)

	def validate_smart_list(self):
		"""On Smart List needs a smart list: a saved Report Builder list of people or a saved Attendance Count."""
		if not smart_lists.is_smart_list(self.value):
			frappe.throw(
				_(
					"Row {0}: choose a smart list, a saved Report Builder list of people or a saved Attendance Count."
				).format(self.idx)
			)
