# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.model.document import Document


class Prayer(Document):
	def before_save(self):
		parts = [self.person or "", str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)
