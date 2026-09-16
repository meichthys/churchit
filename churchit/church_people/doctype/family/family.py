# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

from churchit.church_people.doctype.person.person import SPOUSE_RELATION_TYPES, spouse_relation_type
from churchit.contacts import validate_contact_tables


class Family(Document):
	def validate(self):
		validate_contact_tables(self)
		self.label_spouse_of_head_of_household()

	def label_spouse_of_head_of_household(self):
		"""Set ``relationship_to_head`` to Husband/Wife for the head's linked spouse.

		The Person spouse link owns those two labels, so any other member carrying one is cleared.
		"""
		head = self.head_of_household
		spouse = head and frappe.db.get_value("Person", head, "spouse")
		if not spouse:
			return
		relation = spouse_relation_type(frappe.db.get_value("Person", spouse, "gender"))
		for member in self.members:
			if member.member == spouse:
				member.relationship_to_head = relation
			elif member.relationship_to_head in SPOUSE_RELATION_TYPES.values():
				member.relationship_to_head = None

	@property
	def head_of_household(self):
		# To ensure we don't have multiple people returned here,
		#   After saving a 'Person', we uncheck `head_of_household`
		#   for any other 'Person's that are part of the same family
		doc_dict = frappe.get_list(
			doctype="Person",
			filters=[["family", "=", self.name], ["is_head_of_household", "=", True]],
		)
		if not doc_dict:
			return
		doc_dict[0]["doctype"] = "Person"
		return frappe.get_doc(doc_dict[0]).name

	def before_save(self):
		# Remove family from Person records when Person is removed from Family
		if self.get_doc_before_save() and self.get_doc_before_save().members:
			for member in self.get_doc_before_save().members:
				if member not in self.members:
					frappe.db.set_value("Person", member.member, "family", None, update_modified=False)
		# Update Person records when Family is updated
		if self.members:
			for member in self.members:
				if member.member:
					frappe.db.set_value("Person", member.member, "family", self.name, update_modified=False)
