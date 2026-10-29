# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from churchit.church_scope import refuse_another_churches_fund
from churchit.questions import get_choices, get_fieldname


class QuestionSet(Document):
	"""Questions a church asks on a registration, a form or a room booking; see `churchit/questions.py`."""

	def validate(self):
		for row in self.questions:
			row.fieldname = get_fieldname(row.fieldname or row.label)
			if not row.fieldname:
				frappe.throw(
					_("Row {0}: give the question an Answer Name in letters or digits.").format(row.idx)
				)
			if row.question_type == "Select" and not get_choices(row.options):
				frappe.throw(_("Row {0}: list the choices, one on each line.").format(row.idx))
		names = [row.fieldname for row in self.questions]
		repeated = sorted({name for name in names if names.count(name) > 1})
		if repeated:
			frappe.throw(_("Give each question its own Answer Name: {0}.").format(", ".join(repeated)))

		if flt(self.price) and not self.fund:
			frappe.throw(_("Choose a Fund to take the form's payments."))
		refuse_another_churches_fund(self, self.fund)
