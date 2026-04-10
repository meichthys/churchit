# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe


def _get_all_church_doctypes():
	"""Dynamically returns all doctypes that use the church_subscriptions field."""
	return frappe.get_all(
		"DocField",
		filters={"fieldname": "church_subscriptions", "fieldtype": "Table"},
		pluck="parent",
	)


@frappe.whitelist()
def get_pending_subscriptions():
	"""Return docs the current user's church is allowed (subscribed=0) to subscribe to."""
	church = frappe.db.get_value("User", frappe.session.user, "church")
	if not church:
		return []

	results = []
	for doctype in _get_all_church_doctypes():
		meta = frappe.get_meta(doctype)
		title_field = meta.title_field or "name"
		allowed = frappe.db.get_all(
			"Church Subscription",
			filters={
				"parenttype": doctype,
				"parentfield": "church_subscriptions",
				"church": church,
				"subscribed": 0,
			},
			pluck="parent",
		)
		for name in allowed:
			title = frappe.db.get_value(doctype, name, title_field)
			results.append({"doctype": doctype, "name": name, "title": title})

	return results


@frappe.whitelist()
def subscribe(doctype_name, doc_name):
	"""Flip subscribed=1 for the current user's church on an allowed doc.

	Also cascades to any church-scoped documents linked via Link fields on the
	subscribed doc, so the subscribing church can navigate to related records
	(e.g. subscribing to a Person also grants access to their Family).
	"""
	church = frappe.db.get_value("User", frappe.session.user, "church")
	row_name = frappe.db.get_value(
		"Church Subscription",
		{
			"parent": doc_name,
			"parenttype": doctype_name,
			"parentfield": "church_subscriptions",
			"church": church,
			"subscribed": 0,
		},
		"name",
	)
	if not row_name:
		frappe.throw("Your church is not allowed to subscribe to this document.")
	frappe.db.set_value("Church Subscription", row_name, "subscribed", 1)

	_cascade_linked_subscriptions(doctype_name, doc_name, church)


def _cascade_linked_subscriptions(doctype_name, doc_name, church):
	"""Subscribe the church to any church-scoped documents linked from this doc.

	Walks all Link fields on the subscribed doc. For each one that points to a
	church-scoped doctype, ensures the church has a subscribed=1 row.
	"""
	from church.hooks import CHURCH_SCOPED_DOCTYPES

	meta = frappe.get_meta(doctype_name)
	link_fields = [f for f in meta.fields if f.fieldtype == "Link" and f.options in CHURCH_SCOPED_DOCTYPES]
	if not link_fields:
		return

	doc_values = frappe.db.get_value(
		doctype_name, doc_name, [f.fieldname for f in link_fields], as_dict=True
	) or {}

	for df in link_fields:
		linked_name = doc_values.get(df.fieldname)
		if not linked_name:
			continue
		existing = frappe.db.get_value(
			"Church Subscription",
			{
				"parent": linked_name,
				"parenttype": df.options,
				"parentfield": "church_subscriptions",
				"church": church,
			},
			["name", "subscribed"],
			as_dict=True,
		)
		if existing and not existing.subscribed:
			frappe.db.set_value("Church Subscription", existing.name, "subscribed", 1)
		elif not existing:
			frappe.db.sql(
				"""INSERT INTO `tabChurch Subscription`
					(name, parent, parenttype, parentfield, church, subscribed,
					 creation, modified, owner, modified_by, idx)
				VALUES (%s, %s, %s, 'church_subscriptions', %s, 1,
					NOW(), NOW(), %s, %s, 1)""",
				(
					frappe.generate_hash(),
					linked_name,
					df.options,
					church,
					frappe.session.user,
					frappe.session.user,
				),
			)


@frappe.whitelist()
def copy_doc_to_my_church(doctype_name, source_name):
	"""Clone a subscribed doc into the current user's church."""
	frappe.only_for(["System Manager", "Church Manager"])
	church = frappe.db.get_value("User", frappe.session.user, "church")
	source = frappe.get_doc(doctype_name, source_name)  # permission check included
	new_doc = frappe.copy_doc(source)
	new_doc.church_subscriptions = [{"church": church, "subscribed": 1}]
	new_doc.insert(ignore_permissions=True)
	return new_doc.name
