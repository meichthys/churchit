# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe


def sync_user_church_field(doc, method):
	"""Sync the user's default church when their User record is saved.

	The church field on User is still the source of truth for which church
	a user belongs to. Permission enforcement is now handled entirely by
	permission_query_conditions hooks (Church Subscription model) rather
	than Frappe User Permissions.
	"""
	church = doc.get("church")

	if church:
		frappe.defaults.set_user_default("church", church, user=doc.name)
	else:
		frappe.defaults.clear_user_default("church", user=doc.name)


def validate_church_manager_edits(doc, method):
	"""Prevent Church Managers from escalating user privileges."""
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		return

	if "Church Manager" not in frappe.get_roles():
		return

	# Require a role profile — direct role assignment is not allowed
	allowed_profiles = {"Church Manager", "Church User"}
	if not doc.role_profile_name:
		frappe.throw(
			"Church Managers cannot modify individual roles. A role profile must be selected ('Church Manager' or 'Church User').",
			frappe.PermissionError,
		)

	if doc.role_profile_name not in allowed_profiles:
		frappe.throw(
			"Church Managers can only assign the 'Church Manager' or 'Church User' role profiles.",
			frappe.PermissionError,
		)
