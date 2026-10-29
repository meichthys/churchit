# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, getdate

from churchit.church_ministries.availability import REPEATS
from churchit.church_scope import refuse_another_churches_parent


class MinistryTeamBlock(Document):
	def validate(self):
		refuse_another_churches_parent(
			self,
			"person",
			_("{0} belongs to another church, so only that church can block them from serving."),
		)
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("To Date cannot be before From Date."))
		self.validate_repeat()

	def validate_repeat(self):
		if not self.repeat_frequency:
			self.repeat_until = None
			return
		if self.repeat_frequency not in REPEATS:
			frappe.throw(_("Choose a Repeat from the list."))

		_frequency, _interval, most_days = REPEATS[self.repeat_frequency]
		if date_diff(self.to_date, self.from_date) >= most_days:
			frappe.throw(
				_("A block that repeats {0} can last at most {1} days.").format(
					frappe.bold(_(self.repeat_frequency)), most_days
				)
			)
		if self.repeat_until and getdate(self.repeat_until) < getdate(self.to_date):
			frappe.throw(_("Repeat Until cannot be before To Date."))
