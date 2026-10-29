# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people import smart_lists


class Pathway(Document):
	"""Steps people take through the life of the church, each one a smart list a person is on once they took it."""

	def validate(self):
		names = [row.step for row in self.steps]
		repeated = sorted({name for name in names if names.count(name) > 1})
		if repeated:
			frappe.throw(_("Give each step its own name: {0}.").format(", ".join(repeated)))
		for row in self.steps:
			if not smart_lists.is_smart_list(row.smart_list):
				frappe.throw(
					_(
						"Row {0}: choose a smart list, a saved Report Builder list of people or a saved Attendance Count."
					).format(row.idx)
				)

	def get_steps_done(self) -> dict[str, set[str]]:
		"""The steps each living person of this pathway's church has done, for everyone who has done one."""
		done: dict[str, set[str]] = {}
		for row in self.steps:
			for person in smart_lists.get_people(row.smart_list, self.church):
				done.setdefault(person, set()).add(row.step)
		return done
