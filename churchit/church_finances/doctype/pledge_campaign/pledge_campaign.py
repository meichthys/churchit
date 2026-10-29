# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from churchit.church_scope import refuse_another_churches_record


class PledgeCampaign(Document):
	def validate(self):
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("The End Date cannot be before the Start Date."))
		refuse_another_churches_record(self, "Fund", self.fund)
