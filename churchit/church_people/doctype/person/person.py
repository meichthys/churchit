# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from dateutil.relativedelta import relativedelta
from frappe.model.document import Document
from frappe.utils import cstr, get_link_to_form, getdate, nowdate

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
		# Update Family Member list in Family
		if self.family:
			family = frappe.get_doc("Family", self.family)
			found = False
			for member in family.members:
				if member.member == self.name:
					found = True
					break
			if not found:
				family.append("members", {"member": self.name})
			family.save()

		# Return if this is a new person
		if not self.get_doc_before_save():
			return
		# Remove person from Family if family is removed
		if not self.family and self.get_doc_before_save().family is not None:
			family = frappe.get_doc("Family", self.get_doc_before_save().family)
			for member in family.members:
				if member.member == self.name:
					family.remove(member)
					break
			family.save()

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
		# Remove person from Family. A bulk delete takes the Family out first, and
		# then there is no member row left to remove.
		if self.family and frappe.db.exists("Family", self.family):
			family = frappe.get_doc("Family", self.family)
			for member in family.members:
				if member.member == self.name:
					family.remove(member)
					break
			family.save()

	def validate(self):
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
					family_doc.family_name = f"{self.family} - {self.first_name}"
				else:
					family_doc.family_name = f"{family_doc.family_name[: dashes + 1]} {self.first_name}"
				family_doc.save()

		self.sync_spouse()

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
		existing_family = frappe.db.exists("Family", {"family_name": f"{self.last_name} - {self.first_name}"})

		if existing_family:
			# Set this person's family to the existing one
			self.family = existing_family
			self.is_head_of_household = False  # Not head of household in an existing family
			self.save()
			frappe.msgprint(
				f"⚠️ The <a href='/app/church-family/{existing_family}'>{self.last_name} - {self.first_name}</a> family already exists. This person has been added to that family."
			)

			return  # Don't create a new family

		doc = frappe.new_doc("Family")
		doc.family_name = f"{self.last_name} - {self.first_name}"
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
				"Outgoing email is not configured. Please set up a default "
				"<a href='/app/email-account'>Email Account</a> before inviting portal users.",
				title="Email Not Configured",
			)

		# The invitation goes to the address marked primary in the Emails table.
		email = primary_email(self)
		if not email:
			frappe.throw(
				"Add an email address on the Contact tab before inviting this person to the portal.",
				title="No Email Address",
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
