# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe


def before_insert(doc, method):
	"""Wildcard hook: runs for ALL doctypes on insert.

	Skips any doc that doesn't have a church_subscriptions field.
	Auto-subscribes the creating user's church, then applies any
	configured auto-subscription rules from Church Subscription Settings.
	"""
	if not doc.meta.get_field("church_subscriptions"):
		return

	church = frappe.db.get_value("User", frappe.session.user, "church")
	if church and not any(r.church == church for r in doc.get("church_subscriptions", [])):
		doc.append("church_subscriptions", {"church": church, "subscribed": 1})

	# Apply configured rules (only for System Manager / Administrator)
	if frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles():
		_apply_new_doc_rules(doc)


def after_church_insert(doc, method):
	"""When a new Church is created, auto-subscribe it to configured existing docs."""
	settings = frappe.get_single("Church Subscription Settings")
	for rule in settings.get("subscription_rules", []):
		if not rule.apply_to_new_churches:
			continue
		if rule.target_church and rule.target_church != doc.name:
			continue

		is_subscribed = 1 if rule.access_type == "Auto-Subscribed" else 0
		docs = frappe.get_all(rule.doctype_name, pluck="name", ignore_permissions=True)
		for doc_name in docs:
			if not frappe.db.exists(
				"Church Subscription",
				{
					"parent": doc_name,
					"parenttype": rule.doctype_name,
					"parentfield": "church_subscriptions",
					"church": doc.name,
				},
			):
				frappe.db.insert(
					"Church Subscription",
					{
						"name": frappe.generate_hash(),
						"parent": doc_name,
						"parenttype": rule.doctype_name,
						"parentfield": "church_subscriptions",
						"church": doc.name,
						"subscribed": is_subscribed,
						"idx": 1,
						"creation": frappe.utils.now(),
						"modified": frappe.utils.now(),
						"owner": "Administrator",
						"modified_by": "Administrator",
					},
				)


def _apply_new_doc_rules(doc):
	"""Apply Church Subscription Settings rules that have apply_to_new_docs set."""
	try:
		settings = frappe.get_single("Church Subscription Settings")
	except Exception:
		return

	rules = [
		r
		for r in settings.get("subscription_rules", [])
		if r.doctype_name == doc.doctype and r.apply_to_new_docs
	]
	if not rules:
		return

	all_churches = frappe.get_all("Church", pluck="name")
	subscribed = {r.church for r in doc.get("church_subscriptions", [])}

	for rule in rules:
		targets = all_churches if not rule.target_church else [rule.target_church]
		is_subscribed = 1 if rule.access_type == "Auto-Subscribed" else 0
		for church in targets:
			if church not in subscribed:
				doc.append("church_subscriptions", {"church": church, "subscribed": is_subscribed})
				subscribed.add(church)
