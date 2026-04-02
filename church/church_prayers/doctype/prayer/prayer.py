# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Prayer(Document):
	def before_save(self):
<<<<<<< Updated upstream
		self.title = self.person or ""
=======
		parts = [self.person or "", str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)
>>>>>>> Stashed changes
