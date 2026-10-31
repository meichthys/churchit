# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Each user's saved list filters and sort, which hide a list's new defaults after a change.

Frappe saves the filters and sort a user last had on every list they open
(`frappe.model.utils.user_settings`), in the Redis hash `_user_settings` and, at the hourly sync,
in the `__UserSettings` table. A saved filter list, even an empty one, replaces
`listview_settings.filters`, and a saved sort replaces the doctype's `sort_field`.
"""

import json

import frappe
from frappe.model.utils.user_settings import clear_user_settings_cache, sync_user_settings

LIST_VIEW_KEYS = ("filters", "sort_by", "sort_order")


def clear_list_filters_and_sort(doctypes: tuple[str, ...]):
	"""Open these lists on their own default filters and sort for every user.

	Only the List view changes. Report view columns, Kanban and Calendar settings, saved filter
	layouts and child table grid columns stay as each user left them.
	"""
	# Settings that wait in Redis go to the table first, so dropping the cache loses no other view.
	sync_user_settings()

	rows = frappe.db.sql(
		"select `user`, `doctype`, `data` from `__UserSettings` where `doctype` in %s", [doctypes]
	)
	for user, doctype, data in rows:
		settings = json.loads(data or "{}")
		list_view = settings.get("List") or {}
		removed = [list_view.pop(key) for key in LIST_VIEW_KEYS if key in list_view]
		if removed:
			frappe.db.sql(
				"update `__UserSettings` set `data` = %s where `user` = %s and `doctype` = %s",
				(json.dumps(settings), user, doctype),
			)

	for doctype in doctypes:
		clear_user_settings_cache(doctype)
