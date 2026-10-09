# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

from churchit.church_people.doctype.person.person import SPOUSE_RELATION_TYPES, spouse_relation_type
from churchit.church_people.family_relations import (
	FamilyRelations,
	get_spouse_label,
	keep_relations_of,
	set_family_relations,
)
from churchit.church_scope import is_multi_church
from churchit.contacts import validate_contact_tables


class Family(Document):
	def validate(self):
		validate_contact_tables(self)
		self.label_spouse_of_head_of_household()
		self.label_spouses_of_members()
		self.follow_head_of_households_church()

	def on_update(self):
		before = self.get_doc_before_save()
		members = {member.member for member in self.members}
		keep_relations_of(
			[member.member for member in before.members if member.member not in members] if before else []
		)
		FamilyRelations(self).sync()

	def on_trash(self):
		# Deleting a family undoes it, so unlike leaving, its rows go too.
		for member in self.members:
			if frappe.db.exists("Person", member.member):
				set_family_relations(member.member, [])

	def follow_head_of_households_church(self):
		"""A family belongs to the church of its head of household."""
		head = is_multi_church() and self.head_of_household
		church = head and frappe.db.get_value("Person", head, "church")
		if church:
			self.church = church

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

	def label_spouses_of_members(self):
		"""Fill a blank ``relationship_to_head`` from the member's spouse, e.g. a Son's wife is a Daughter-in-law."""
		members = {member.member: member for member in self.members if member.member}
		people = frappe.get_all(
			"Person",
			# church-scope: only this family's own members, by name
			filters={"name": ["in", list(members)], "spouse": ["in", list(members)]},
			fields=["name", "spouse", "gender"],
		)
		for person in people:
			member = members[person.name]
			label = get_spouse_label(members[person.spouse].relationship_to_head, person.gender)
			if not member.relationship_to_head and label and frappe.db.exists("Person Relation Type", label):
				member.relationship_to_head = label

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
		"""Point each member at this family, and clear it on people dropped who have not moved elsewhere."""
		members = {member.member for member in self.members if member.member}
		before = self.get_doc_before_save()
		for member in before.members if before else []:
			if member.member not in members:
				frappe.db.set_value(
					"Person",
					{"name": member.member, "family": self.name},
					"family",
					None,
					update_modified=False,
				)
		for member in members:
			frappe.db.set_value("Person", member, "family", self.name, update_modified=False)
