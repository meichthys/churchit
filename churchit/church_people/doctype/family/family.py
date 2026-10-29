# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from churchit.church_people import household
from churchit.church_people.derived import life_stage_for
from churchit.church_people.doctype.authorized_pickup.authorized_pickup import set_pickups_church
from churchit.church_people.family_relations import (
	ROLE_TYPES,
	get_gendered_type,
	get_rebased_labels,
	get_spouse_label,
)
from churchit.church_people.member_access import refuse_member_edits_beyond_photo
from churchit.church_people.merge import (
	adopt_contact_rows,
	adopt_rows,
	drop_deleted_document,
	fill_blanks,
	refuse_all_but_a_merge,
	take_import_id,
	typed_fields,
)
from churchit.church_scope import has_church_access, is_multi_church
from churchit.contacts import validate_contact_tables


class Family(Document):
	def validate(self):
		# First, so the controller's own changes below are not taken for a member's.
		refuse_member_edits_beyond_photo(self)
		validate_contact_tables(self)
		if self.primary_contact and self.primary_contact not in self.member_names:
			frappe.throw(_("The Primary Contact must be one of the Family Members."))
		self.follow_primary_contacts_church()
		self.refuse_another_churches_primary_contact()
		self.refuse_another_churches_members()
		previous = self.replaced_primary_contact
		if previous:
			self.relabel_members(previous)
		self.label_primary_contact_and_spouse()
		self.label_spouses_of_members()
		self.fill_household_roles()
		if previous:
			old_family_name = self.family_name
			self.rename_after_primary_contact()
			self.warn_about_new_primary_contact(old_family_name)

	@property
	def member_names(self):
		return [member.member for member in self.members if member.member]

	@property
	def replaced_primary_contact(self):
		"""The primary contact before this save, when another person has taken their place."""
		before = self.get_doc_before_save()
		previous = before.primary_contact if before else None
		if previous and self.primary_contact and previous != self.primary_contact:
			return previous

	def get_member_values(self, fieldname):
		# church-scope: only this family's own members, by name
		return dict(
			frappe.get_all(
				"Person",
				filters={"name": ["in", self.member_names]},
				fields=["name", fieldname],
				as_list=True,
			)
		)

	def relabel_members(self, previous):
		"""Turn each member's relationship to *previous* into their relationship to the new primary contact."""
		labels = {member.member: member.relationship_to_primary_contact for member in self.members}
		rebased = get_rebased_labels(labels, self.get_member_values("gender"), previous, self.primary_contact)
		relation_types = set(frappe.get_all("Person Relation Type", pluck="name"))
		for member in self.members:
			label = rebased.get(member.member)
			member.relationship_to_primary_contact = label if label in relation_types else None

	def label_primary_contact_and_spouse(self):
		"""Label the primary contact and their linked spouse Husband or Wife.

		The spouse link owns those two labels, so any other member carrying one is cleared.
		"""
		contact = self.primary_contact
		if not contact:
			return
		spouse = frappe.db.get_value("Person", contact, "spouse")
		genders = self.get_member_values("gender") if spouse else {}
		for member in self.members:
			if spouse and member.member in (contact, spouse):
				member.relationship_to_primary_contact = get_gendered_type(
					"spouse", genders.get(member.member)
				)
			elif member.relationship_to_primary_contact in ROLE_TYPES["spouse"]:
				member.relationship_to_primary_contact = None

	def label_spouses_of_members(self):
		"""Fill a blank relationship from the member's spouse, e.g. a Son's wife is a Daughter-in-law."""
		members = {member.member: member for member in self.members if member.member}
		people = frappe.get_all(
			"Person",
			# church-scope: only this family's own members, by name
			filters={"name": ["in", list(members)], "spouse": ["in", list(members)]},
			fields=["name", "spouse", "gender"],
		)
		for person in people:
			member = members[person.name]
			label = get_spouse_label(members[person.spouse].relationship_to_primary_contact, person.gender)
			if (
				not member.relationship_to_primary_contact
				and label
				and frappe.db.exists("Person Relation Type", label)
			):
				member.relationship_to_primary_contact = label

	def fill_household_roles(self) -> list:
		"""Fill each blank household role that the member's relationship and age decide, and return the rows filled.

		A role someone set is never changed. With no primary contact yet, no one's relationship to them is known,
		so every role waits for one.
		"""
		if not self.primary_contact:
			return []
		blank = [member for member in self.members if member.member and not member.household_role]
		ages = household.get_ages([member.member for member in blank])
		adult_age = frappe.db.get_single_value("People Settings", "adult_age")
		for member in blank:
			member.household_role = household.get_household_role(
				member.member == self.primary_contact,
				member.relationship_to_primary_contact,
				ages.get(member.member),
				adult_age,
			)
		return [member for member in blank if member.household_role]

	def rename_after_primary_contact(self):
		"""Put the primary contact's first name after the last dash, "Doe - John" to "Doe - Jane"."""
		first_name = frappe.db.get_value("Person", self.primary_contact, "first_name")
		surname, dash, _first_name = self.family_name.rpartition("-")
		self.family_name = f"{surname}{dash} {first_name}" if dash else f"{self.family_name} - {first_name}"

	def warn_about_new_primary_contact(self, old_family_name):
		names = self.get_member_values("full_name")
		contact = escape_html(names.get(self.primary_contact) or self.primary_contact)
		message = _(
			"{0} is the new Primary Contact. The family was renamed from {1} to {2}, and each member's relationship is now their relationship to {0}."
		).format(contact, escape_html(old_family_name), escape_html(self.family_name))
		unknown = [
			escape_html(names.get(member.member) or member.member)
			for member in self.members
			if member.member != self.primary_contact and not member.relationship_to_primary_contact
		]
		if unknown:
			message += "<br><br>" + _("Set the relationship by hand for: {0}.").format(", ".join(unknown))
		frappe.msgprint(message, title=_("Relationships Changed"), indicator="orange")

	def follow_primary_contacts_church(self):
		"""A family belongs to the church of its primary contact."""
		contact = is_multi_church() and self.primary_contact
		church = contact and frappe.db.get_value("Person", contact, "church")
		if church:
			self.church = church

	def refuse_another_churches_primary_contact(self):
		"""Only the primary contact's own church makes them one, because the family moves to their church.

		Frappe checks the right to the family before `follow_primary_contacts_church` sets its church, so it
		never sees where the family goes. The church is set in code, not by `fetch_from`, so this checks the
		church it set rather than calling `refuse_another_churches_parent`. Writes with ignore_permissions, such as a person joining their
		family's roster, are the app's own and are not refused.
		"""
		if self.flags.ignore_permissions or not self.has_value_changed("primary_contact"):
			return
		if not has_church_access(frappe.session.user, self.church):
			name = frappe.db.get_value("Person", self.primary_contact, "full_name") or self.primary_contact
			frappe.throw(
				_(
					"{0} belongs to another church, so only that church can make them the primary contact."
				).format(frappe.bold(escape_html(name))),
				frappe.PermissionError,
			)

	def refuse_another_churches_members(self):
		"""Only a user who can see a person's church adds them to a family, as for its primary contact.

		A household Adult may collect its children at Verify Pickup, so a household spans churches only
		when a user of both links it. Writes with ignore_permissions are the app's own and are not refused.
		"""
		if self.flags.ignore_permissions:
			return
		before = self.get_doc_before_save()
		known = set(before.member_names) if before else set()
		churches = self.get_member_values("church")
		for member in self.members:
			if member.member in known or has_church_access(frappe.session.user, churches.get(member.member)):
				continue
			frappe.throw(
				_(
					"Row {0}: {1} belongs to another church, so only that church can add them to a family."
				).format(member.idx, frappe.bold(escape_html(member.member))),
				frappe.PermissionError,
			)

	def before_rename(self, old, new, merge=False):
		"""A family's ID changes only by a merge into another family.

		The rename then points this family's authorized pickups at the kept family, so a pickup the kept
		family has already goes first.
		"""
		refuse_all_but_a_merge(self, frappe.get_doc("Family", new) if merge else None)
		# church-scope: the pickups of the one family a merge keeps, by name
		kept = frappe.get_all("Authorized Pickup", filters={"family": new}, pluck="person")
		frappe.db.delete("Authorized Pickup", {"family": old, "person": ("in", kept)})

	def after_rename(self, old, new, merge=False):
		"""Take over a merged family's members, contact rows and blank fields.

		A member's relationship is to the primary contact, so a member who comes from a family with another
		primary contact loses it, and validate fills what it can work out again. A household role stays.
		"""
		if not merge:
			return
		drop_deleted_document(self.doctype, old)
		removed = frappe.get_doc("Family", old)
		same_contact = not self.primary_contact or self.primary_contact == removed.primary_contact
		moved = adopt_rows(self, removed, "members", lambda row: row.member)
		adopt_contact_rows(self, removed)
		self.reload()
		fill_blanks(self, removed, typed_fields(self))
		take_import_id(self, removed)
		for member in self.members:
			if member.name in moved and not same_contact:
				member.relationship_to_primary_contact = None
		self.save(ignore_permissions=True)

	def before_save(self):
		"""Point each member at this family, and clear it on people dropped who have not moved elsewhere."""
		members = set(self.member_names)
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

	def on_update(self):
		if self.has_value_changed("church"):
			set_pickups_church(self.name, self.church)
		before = self.get_doc_before_save()
		roles = {member.member: member.household_role or None for member in before.members} if before else {}
		self.set_life_stages(
			[member for member in self.members if (member.household_role or None) != roles.get(member.member)]
		)

	def on_trash(self):
		"""A family's authorized pickups go with it."""
		frappe.db.delete("Authorized Pickup", {"family": self.name})

	def set_life_stages(self, rows):
		"""Give the member of each of *rows* the life stage their household role implies."""
		ages = household.get_ages([row.member for row in rows])
		for row in rows:
			frappe.db.set_value(
				"Person",
				row.member,
				"life_stage",
				life_stage_for(row.household_role or None, ages.get(row.member)),
				update_modified=False,
			)


def primary_contacts():
	"""Subquery of every family's primary contact."""
	Family = frappe.qb.DocType("Family")
	# church-scope: only narrows queries that are scoped already
	return frappe.qb.from_(Family).select(Family.primary_contact).where(Family.primary_contact.isnotnull())
