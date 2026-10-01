# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.scripture import get_readable_translations

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
			"translation",
			"progress",
			"memorized",
			"memorized_on",
			"times_memorized",
			"assigned_by",
		],
		order_by="memorized asc, modified desc",
	)
	for it in items:
		it["label"] = f"{it['bible_reference']} ({it['translation']})"
		if it.get("assigned_by"):
			it["assigned_by_label"] = (
				frappe.db.get_value("User", it["assigned_by"], "full_name") or it["assigned_by"]
			)
	context.items = items
	context.translations = get_readable_translations()
