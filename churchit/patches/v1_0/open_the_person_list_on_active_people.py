# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Open the Person list on Active people for every user.

A user's saved filters win over the list's own, and an empty saved filter list wins too.
"""

from churchit.user_settings import clear_list_filters_and_sort


def execute():
	clear_list_filters_and_sort(("Person",))
