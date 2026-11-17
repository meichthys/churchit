# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill the full name of Form Responses and the user name of Bible Memory Items, then reset those saved lists.

Form Response titles and lists read the full name, and the Bible Memory Item list shows the user's
name, not the user ID. A user's saved filters and sort on Communication Purpose, which now shows
its title, are reset too.
"""

import frappe

from churchit.user_settings import clear_list_filters_and_sort

LISTS = ("Bible Memory Item", "Communication Purpose", "Form Response")


def execute():
	frappe.db.sql(
		"""
		update `tabForm Response`
		set full_name = trim(concat_ws(' ', first_name, last_name))
		where ifnull(full_name, '') = ''
		"""
	)
	frappe.db.sql(
		"""
		update `tabBible Memory Item` item
		join `tabUser` user on user.name = item.user
		set item.user_full_name = user.full_name
		where ifnull(item.user_full_name, '') = ''
		"""
	)
	clear_list_filters_and_sort(LISTS)
