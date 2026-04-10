# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe


def _get_subscription_condition(user, doctype):
	"""Return SQL WHERE fragment restricting doctype to docs subscribed by user's church."""
	if "System Manager" in frappe.get_roles(user):
		return ""
	church = frappe.db.get_value("User", user, "church")
	if not church:
		return "1=0"
	esc = frappe.db.escape(church)
	esc_dt = frappe.db.escape(doctype)
	return f"""EXISTS (
		SELECT 1 FROM `tabChurch Subscription`
		WHERE `parent` = `tab{doctype}`.`name`
		AND `parenttype` = {esc_dt}
		AND `parentfield` = 'church_subscriptions'
		AND `church` = {esc}
		AND `subscribed` = 1
	)"""


def has_subscription_permission(doc, ptype, user):
	"""Document-level permission check: user's church must have subscribed = 1.

	Queries the DB directly because Frappe may pass a lightweight doc object
	to this hook without child tables loaded.
	"""
	if "System Manager" in frappe.get_roles(user):
		return True
	church = frappe.db.get_value("User", user, "church")
	if not church:
		return False
	return bool(
		frappe.db.exists(
			"Church Subscription",
			{
				"parent": doc.name,
				"parenttype": doc.doctype,
				"parentfield": "church_subscriptions",
				"church": church,
				"subscribed": 1,
			},
		)
	)


def make_perm_func(dt):
	"""Generate a permission_query_conditions function for a specific doctype."""

	def _func(user):
		return _get_subscription_condition(user, dt)

	_func.__name__ = f"get_{dt.lower().replace(' ', '_')}_permission"
	return _func
