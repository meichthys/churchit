# Copyright (c) 2026, meichthys and contributors

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/memorize"
		raise frappe.Redirect

	context.no_cache = 1
	context.title = "Bible Memory"

	items = frappe.get_all(
		"Bible Memory Item",
		filters={"user": frappe.session.user},
		fields=[
			"name",
			"bible_reference",
			"progress",
			"memorized",
			"memorized_on",
			"times_memorized",
			"assigned_by",
		],
		order_by="memorized asc, modified desc",
	)
	for it in items:
		it["label"] = frappe.db.get_value(
			"Bible Reference", it["bible_reference"], "reference"
		) or it["bible_reference"]
		if it.get("assigned_by"):
			it["assigned_by_label"] = (
				frappe.db.get_value("User", it["assigned_by"], "full_name")
				or it["assigned_by"]
			)
	context.items = items

	context.books = frappe.get_all(
		"Bible Book",
		fields=["name", "abbreviation"],
		order_by="creation asc",
		ignore_permissions=True,
	)
	context.translations = frappe.get_all(
		"Bible Translation",
		fields=["name", "abbreviation"],
		order_by="name asc",
		ignore_permissions=True,
	)
	context.default_translation = (
		frappe.db.get_value(
			"Church",
			{"default_bible_translation": ("is", "set")},
			"default_bible_translation",
		)
		or ""
	)
