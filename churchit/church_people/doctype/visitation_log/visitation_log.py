# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from pypika.terms import ExistsCriterion

from churchit.church_scope import refuse_another_churches_parent


class VisitationLog(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "person", _("{0} belongs to another church, so only that church can log visits to them.")
		)


def has_no_later_visit(visit):
	"""Query criterion for *visit*, a Visitation Log table: its person has no later Scheduled or Completed visit.

	A follow-up that was scheduled or done no longer needs a reminder. A visit on the same day counts
	when it was added later.
	"""
	# church-scope: a subquery of one person's visits inside a query the caller already scopes
	later = frappe.qb.DocType("Visitation Log").as_("later")
	subquery = (
		frappe.qb.from_(later)
		.select(later.name)
		.where(
			(later.person == visit.person)
			& (
				(later.visit_date > visit.visit_date)
				| ((later.visit_date == visit.visit_date) & (later.creation > visit.creation))
			)
			& later.status.isin(["Scheduled", "Completed"])
		)
	)
	return ExistsCriterion(subquery).negate()
