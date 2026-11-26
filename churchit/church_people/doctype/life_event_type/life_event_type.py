# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.derived import BIRTH, DEATH, WEDDING

# The types whose rows fill in Person fields (`derived`), which the app finds by name.
FILLS_IN_PERSON_FIELDS = (BIRTH, DEATH, WEDDING)


class LifeEventType(Document):
	"""A kind of life event. The types that fill in Person fields cannot be deleted or renamed."""

	def on_trash(self):
		if self.name in FILLS_IN_PERSON_FIELDS:
			frappe.throw(
				_("{0} fills in fields of each person, so it cannot be deleted.").format(
					frappe.bold(self.name)
				)
			)

	def before_rename(self, old, new, merge=False):
		if old in FILLS_IN_PERSON_FIELDS:
			frappe.throw(
				_("{0} fills in fields of each person, so it cannot be renamed.").format(frappe.bold(old))
			)
