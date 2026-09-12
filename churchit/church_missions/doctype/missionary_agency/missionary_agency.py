# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.model.document import Document

from churchit.contacts import validate_contact_tables


class MissionaryAgency(Document):
	def validate(self):
		validate_contact_tables(self)
