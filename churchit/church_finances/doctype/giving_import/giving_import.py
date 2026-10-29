# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.imports.provider import ImportTarget


class GivingImport(ImportTarget):
	"""Data Import's log links each imported row here under the name of the Collection it went into."""

	def load_from_db(self):
		if not frappe.db.exists("Collection", self.name):
			raise frappe.DoesNotExistError(self.not_stored_message)
		super(Document, self).__init__({"doctype": self.doctype, "name": self.name})

	@property
	def not_stored_message(self) -> str:
		return _("{0} keeps no records. Import gifts with Data Import.").format(_(self.doctype))
