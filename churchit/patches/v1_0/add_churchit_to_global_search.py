# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Let the search bar (Ctrl+K) find people, families, groups, sermons, songs and the other records in the
`global_search_doctypes` hook.

Frappe copies the hook into Global Search Settings only in the setup wizard, and migrate does not index the
existing records of a doctype whose search fields changed.
"""

from churchit.patches.after_install import add_to_global_search, get_searched_doctypes


def execute():
	add_to_global_search(get_searched_doctypes())
