# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class Person(Document):
	def on_update(self):
		# Sync church to linked portal user when church field changes
		if self.portal_user and self.has_value_changed("church"):
			frappe.db.set_value("User", self.portal_user, "church", self.church)

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

	def before_delete(self):
		# Remove person from Family
		if self.family:
			family = frappe.get_doc("Family", self.family)
			for member in family.members:
				if member.name == self.name:
					family.remove(member)
					break
			family.save()

	def validate(self):
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

		# Sync spouses
		if self.spouse and self.is_married:
			# Sync spouses
			spouse = frappe.get_doc("Person", self.spouse)
			if spouse.spouse != self.name:
				# Unlink spouse's old spouse if there was one
				frappe.db.set_value("Person", spouse.spouse, "spouse", None)
				frappe.db.set_value("Person", spouse.spouse, "anniversary", None)
				frappe.db.set_value("Person", spouse.spouse, "is_married", False)
				# Link spouses
				frappe.db.set_value("Person", spouse.name, "spouse", self.name)
				frappe.db.set_value("Person", spouse.name, "is_married", True)
				frappe.db.set_value("Person", spouse.name, "anniversary", self.anniversary)
				frappe.msgprint(f"Spouses have been linked:<br>{self.full_name} 👩‍❤️‍👨 {spouse.full_name}")
			elif spouse.anniversary != self.anniversary:
				# Keep anniversary in sync when it changes on either side
				frappe.db.set_value("Person", spouse.name, "anniversary", self.anniversary)
		else:
			if self._doc_before_save and self._doc_before_save.is_married and self._doc_before_save.spouse:
				spouse = frappe.get_doc("Person", self._doc_before_save.spouse)
				frappe.db.set_value("Person", spouse.name, "spouse", None)
				frappe.db.set_value("Person", spouse.name, "is_married", False)
				self.spouse = None
				self.anniversary = None
				self.is_married = False
				frappe.msgprint(f"Spouses have been unlinked:<br>{self.full_name} 💔 {spouse.full_name}")

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
		doc.church = self.church
		doc.save()
		self.set("family", doc)
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

		# Inherit church from the creating user; fall back to root church if unset
		church = frappe.db.get_value("User", frappe.session.user, "church")
		if not church:
			church = frappe.db.get_value("Church", {"parent_church": ("is", "not set")})

		# Check if user already exists with this email
		user = frappe.db.exists("User", {"email": self.email})

		if not user:
			# Create a new portal user
			new_user = frappe.new_doc("User")
			new_user.email = self.email
			new_user.first_name = self.first_name
			new_user.last_name = self.last_name
			new_user.send_welcome_email = 1
			new_user.enabled = 1
			new_user.role_profile_name = "Church User"
			new_user.church = church
			new_user.save(ignore_permissions=True)

			# Update Person to mark as portal user
			self.portal_user = new_user.name
			self.save(ignore_permissions=True)

			if church:
				frappe.msgprint(
					f"👤 Portal user created for <a href='/app/user/{new_user.name}'>{self.full_name}</a> at <b>{church}</b> "
					f"and an invitation email was sent to {self.email}.",
					title="Invitation Sent",
					indicator="green",
				)
			else:
				frappe.msgprint(
					f"👤 Portal user created for <a href='/app/user/{new_user.name}'>{self.full_name}</a> "
					f"and an invitation email was sent to {self.email}. "
					f"⚠️ No church was assigned — please set a church on the user.",
					title="Invitation Sent",
					indicator="orange",
				)
		else:
			# User already exists, just update the portal_user field
			self.portal_user = user
			self.save(ignore_permissions=True)
			existing_church = frappe.db.get_value("User", user, "church")
			church_text = f" at <b>{existing_church}</b>" if existing_church else " (no church assigned)"
			frappe.msgprint(
				f"⚠️ Portal user <a href='/app/user/{user}'>{user}</a>{church_text} already exists. User is now linked to this person."
			)


def has_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user

	# Church Manager / System Manager — no extra restriction
	if "Church Manager" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
		return True

	# Church User — can only access their own Person record
	if "Church User" in frappe.get_roles(user):
		return doc.portal_user == user

	return None


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if "System Manager" in roles or "Church Manager" in roles:
		return ""

	if "Church User" in roles:
		return f"(`tabPerson`.portal_user = {frappe.db.escape(user)})"

	return ""


def get_list_context(context):
	# Only show documents related to the active user
	context.filters = {"portal_user": frappe.session.user}
	# Sort the portal list view by status descending
	context.order_by = "modified desc"
	return context
