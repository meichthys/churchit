# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from dateutil.relativedelta import relativedelta
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, get_link_to_form, getdate, nowdate

from churchit.church_foundations import church_access
from churchit.church_people.member_access import refuse_member_edits_beyond_personal_details
from churchit.church_scope import is_multi_church
from churchit.contacts import primary_email, validate_contact_tables

SPOUSE_RELATION_TYPES = {"Male": "Husband", "Female": "Wife"}


def spouse_relation_type(gender):
	"""Relation Type a person of ``gender`` is to their spouse, or None when unknown."""
	return SPOUSE_RELATION_TYPES.get(gender)


def years_since(date):
	"""Whole years from ``date`` until today; 0 when ``date`` is empty."""
	if not date:
		return 0
	return max(relativedelta(getdate(nowdate()), getdate(date)).years, 0)


class Person(Document):
	def on_update(self):
		self.sync_church_permission()
		self.sync_family_church()
		self.sync_family_members()

	def sync_family_members(self):
		"""Put this person on their family's roster, bringing a newly linked or moving spouse along.

		The rosters follow the person, so the right to edit this person is the one
		that counts, not a right to the Family. Leave the old family before the new
		one is saved, so the new one's labels see who its members are.
		"""
		before = self.get_doc_before_save()
		moving_spouse = self.spouse_moving_along
		if moving_spouse:
			frappe.db.set_value("Person", moving_spouse, "is_head_of_household", 0)
		spouse = moving_spouse or self.spouse_without_family
		if before and before.family and before.family != self.family:
			self.remove_from_family(before.family, spouse)
		if self.family:
			family = frappe.get_doc("Family", self.family)
			for person in filter(None, (self.name, spouse)):
				if not any(member.member == person for member in family.members):
					family.append("members", {"member": person})
			family.save(ignore_permissions=True)
		if self.family or (before and before.family):
			# The Family rewrote this person's From Family relation rows.
			self.load_children_from_db()

	def remove_from_family(self, family_name, spouse=None):
		"""Drop this person, and *spouse* when given, from *family_name*'s members, when that family still exists."""
		if not frappe.db.exists("Family", family_name):
			return
		family = frappe.get_doc("Family", family_name)
		for member in [member for member in family.members if member.member in (self.name, spouse)]:
			family.remove(member)
		family.save(ignore_permissions=True)

	def sync_church_permission(self):
		"""Keep the linked user's Church permission pointed at this person's church.

		Only a change of user or church re-points it, so an administrator's
		edits to the permission survive unrelated saves.
		"""
		if not is_multi_church() or not self.user or not self.church:
			return
		before = self.get_doc_before_save()
		if before and before.user == self.user and before.church == self.church:
			return
		church_access.set_user_church(self.user, self.church)

	def sync_family_church(self):
		"""Move the family with its head of household when the head changes church."""
		if not is_multi_church() or not self.family or not self.is_head_of_household:
			return
		if frappe.db.get_value("Family", self.family, "church") != self.church:
			frappe.db.set_value("Family", self.family, "church", self.church)

	def before_save(self):
		# We set this here since virtual fields do not work with
		#   View Settings -> Title Field as of 2025-08-26
		self.full_name = f"{self.first_name}" + ((" " + self.last_name) if self.last_name else "")
		self.marriage_years = years_since(self.anniversary)
		self._recompute_age()

	def _recompute_age(self):
		"""Set age from the Birth row in life_events. Cleared when no Birth event."""
		birth = next(
			(le for le in (self.life_events or []) if le.event_type == "Birth" and le.date),
			None,
		)
		self.age = years_since(birth.date) if birth else None

	def on_trash(self):
		if self.spouse:
			self.unlink_spouse(self.spouse)
		# Leaving a family keeps its rows as hand-entered ones, which would block the delete.
		frappe.db.delete("Person Relation", {"parenttype": "Person", "person": self.name, "from_family": 1})
		# A bulk delete takes the Family out first, and then there is no member row left to remove.
		if self.family:
			self.remove_from_family(self.family)

	def validate(self):
		refuse_member_edits_beyond_personal_details(self)
		# Normalise the emails / phones / addresses tables before anything else
		# reads a primary value off them.
		validate_contact_tables(self)

		# Remove head of household status when family is removed
		if not self.family and self.is_head_of_household:
			self.set("is_head_of_household", False)
		# Remove old head of household when new one is assigned - Also rename family
		if self.is_head_of_household:
			old_heads_of_household = frappe.db.get_all(
				doctype="Person",
				filters=[
					["family", "=", self.family],
					["is_head_of_household", "=", True],
					["name", "!=", self.name],
				],
			)
			if old_heads_of_household:
				# There should only be one head of household, but just in case we loop through all of them.
				for head in old_heads_of_household:
					head_doc = frappe.get_doc("Person", head["name"])
					frappe.msgprint(
						f"ℹ️ {head_doc.full_name} was removed from being the head of this household."
					)
					head_doc.is_head_of_household = False
					head_doc.save()
				# Rename family with new head of household
				family_doc = frappe.get_doc("Family", self.family)
				dashes = family_doc.family_name.rfind("-")
				if dashes == -1:  # If no dashes found, add one
					family_doc.family_name = f"{family_doc.family_name} - {self.first_name}"
				else:
					family_doc.family_name = f"{family_doc.family_name[: dashes + 1]} {self.first_name}"
				family_doc.save(ignore_permissions=True)

		self.sync_spouse()
		self.share_family_with_spouse()

	def sync_spouse(self):
		"""Mirror the spouse link, anniversary and Husband/Wife relation onto the other person."""
		before = self.get_doc_before_save()
		previous = before.spouse if before else None
		if self.spouse and self.is_married:
			if previous and previous != self.spouse:
				self.unlink_spouse(previous)
			self.link_spouse()
			return
		if previous:
			self.unlink_spouse(previous)
			self.is_married = False
			self.anniversary = None
		self.spouse = None
		self.sync_spouse_relation(None)

	@property
	def has_new_spouse(self):
		before = self.get_doc_before_save()
		return bool(self.spouse) and (not before or before.spouse != self.spouse)

	@property
	def spouse_without_family(self):
		"""A newly linked spouse with no family yet, who joins this person's."""
		if self.has_new_spouse and not frappe.db.get_value("Person", self.spouse, "family"):
			return self.spouse

	@property
	def spouse_moving_along(self):
		"""The spouse who shared this person's old family, and so moves with them to the new one."""
		before = self.get_doc_before_save()
		has_moved = self.family and before and before.family and before.family != self.family
		if (
			has_moved
			and self.spouse
			and frappe.db.get_value("Person", self.spouse, "family") == before.family
		):
			return self.spouse

	@property
	def household_name(self):
		return f"{self.last_name} - {self.first_name}" if self.last_name else self.first_name

	def share_family_with_spouse(self):
		"""Give a newly linked couple one family: this person's, the spouse's, or a new one this person heads."""
		if self.family or not self.has_new_spouse:
			return
		self.family = frappe.db.get_value("Person", self.spouse, "family")
		if self.family:
			return
		family = frappe.get_doc({"doctype": "Family", "family_name": self.household_name})
		family.insert(ignore_permissions=True)
		self.family = family.name
		self.is_head_of_household = 1
		if not frappe.flags.in_import:
			family_link = get_link_to_form("Family", family.name, family.family_name)
			frappe.msgprint(f"👨‍👩‍👧‍👦 New family created: {family_link}")

	def link_spouse(self):
		"""Point the spouse back at this person, sharing the anniversary and relation rows."""
		spouse = frappe.get_doc("Person", self.spouse)
		self.anniversary = self.anniversary or spouse.anniversary
		self.sync_spouse_relation(spouse)
		spouse.sync_spouse_relation(self)
		spouse.update_child_table("relations")
		if spouse.spouse != self.name:
			if spouse.spouse:
				spouse.unlink_spouse(spouse.spouse)
			if not frappe.flags.in_import:
				frappe.msgprint(f"Spouses have been linked:<br>{self.full_name} 👩‍❤️‍👨 {spouse.full_name}")
		if spouse.spouse != self.name or cstr(spouse.anniversary) != cstr(self.anniversary):
			frappe.db.set_value(
				"Person",
				spouse.name,
				{
					"spouse": self.name,
					"is_married": True,
					"anniversary": self.anniversary,
					"marriage_years": years_since(self.anniversary),
				},
			)

	def unlink_spouse(self, spouse_name):
		"""Clear the marriage fields and Husband/Wife relation on the other person, if they still point here."""
		spouse = frappe.get_doc("Person", spouse_name)
		if spouse.spouse != self.name:
			return
		spouse.sync_spouse_relation(None)
		spouse.update_child_table("relations")
		frappe.db.set_value(
			"Person",
			spouse.name,
			{"spouse": None, "is_married": False, "anniversary": None, "marriage_years": 0},
		)
		if not frappe.flags.in_import:
			frappe.msgprint(f"Spouses have been unlinked:<br>{self.full_name} 💔 {spouse.full_name}")

	def sync_spouse_relation(self, spouse):
		"""Keep exactly one Husband/Wife row in ``relations``, pointing at ``spouse`` (a Person or None)."""
		relation = spouse_relation_type(spouse.gender) if spouse else None
		for row in list(self.relations):
			is_wanted = relation and row.person == spouse.name and row.type == relation
			if row.type in SPOUSE_RELATION_TYPES.values() and not is_wanted:
				self.remove(row)
		if relation and not any(row.type == relation and row.person == spouse.name for row in self.relations):
			self.append("relations", {"type": relation, "person": spouse.name})

	@frappe.whitelist()
	def new_family_from_person(self):
		# Check if a family with this person's name already exists
		existing_family = frappe.db.exists("Family", {"family_name": self.household_name})

		if existing_family:
			# Set this person's family to the existing one
			self.family = existing_family
			self.is_head_of_household = False  # Not head of household in an existing family
			self.save()
			family_link = get_link_to_form("Family", existing_family, self.household_name)
			frappe.msgprint(
				f"⚠️ The {family_link} family already exists. This person has been added to that family."
			)

			return  # Don't create a new family

		doc = frappe.new_doc("Family")
		doc.family_name = self.household_name
		doc.save()
		self.set("family", doc.name)
		self.set("is_head_of_household", True)
		self.save()
		self.reload()
		family_link = get_link_to_form("Family", doc.name, doc.family_name)
		frappe.msgprint(f"👨‍👩‍👧‍👦 New family created: {family_link}")

	@frappe.whitelist()
	def invite_to_portal(self):
		# Block invitation if outgoing email is not configured
		if not frappe.db.exists("Email Account", {"enable_outgoing": 1, "default_outgoing": 1}):
			frappe.throw(
				_(
					"Outgoing email is not configured. Please set up a default "
					"<a href='/app/email-account'>Email Account</a> before inviting portal users."
				),
				title=_("Email Not Configured"),
			)

		# The invitation goes to the address marked primary in the Emails table.
		email = primary_email(self)
		if not email:
			frappe.throw(
				_("Add an email address on the Contact tab before inviting this person to the portal."),
				title=_("No Email Address"),
			)

		# Check if user already exists with this email
		user = frappe.db.exists("User", {"email": email})

		if not user:
			# Create a new portal user
			new_user = frappe.new_doc("User")
			new_user.email = email
			new_user.first_name = self.first_name
			new_user.last_name = self.last_name
			new_user.send_welcome_email = 1
			new_user.enabled = 1
			new_user.append("role_profiles", {"role_profile": "Church User"})
			new_user.save(ignore_permissions=True)

			# Update Person to mark as portal user
			self.user = new_user.name
			self.save(ignore_permissions=True)

			frappe.msgprint(
				f"👤 Portal user created for <a href='/app/user/{new_user.name}'>{self.full_name}</a> "
				f"and an invitation email was sent to {email}.",
				title="Invitation Sent",
				indicator="green",
			)
		else:
			# User already exists, just update the user field
			self.user = user
			self.save(ignore_permissions=True)
			frappe.msgprint(
				f"⚠️ Portal user <a href='/app/user/{user}'>{user}</a> already exists. User is now linked to this person."
			)


def get_user_dashboard_data(data):
	data["transactions"].append({"label": "Church", "items": ["Person"]})
	data["non_standard_fieldnames"] = data.get("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["Person"] = "user"
	return data


def get_list_context(context):
	# Only show documents related to the active user
	context.filters = {"user": frappe.session.user}
	# Sort the portal list view by status descending
	context.order_by = "modified desc"
	return context
