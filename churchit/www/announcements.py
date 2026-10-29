# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import church_filters

no_cache = 1
sitemap = 1

LIMIT = 5


def get_context(context):
	"""The announcements the selected church shares from its newest published bulletins, and nothing else of them."""
	context.no_cache = 1
	context.title = _("Announcements")
	context.bulletins = frappe.get_all(
		"Bulletin",
		filters=church_filters(
			selected_church_name(),
			**{"publish": 1, "share_announcements": 1, "announcements": ("is", "set")},
		),
		fields=["name", "function_name", "function_date", "announcements"],
		order_by="function_date desc",
		limit=LIMIT,
	)
