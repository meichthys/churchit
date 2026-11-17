# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Open the lists whose columns or filters changed on their new defaults.

Follow-up Workflow, Pathway and Connection Card Interest got a title field. Family shows its primary
contact. Group Join Request lost a duplicate Person filter.
"""

from churchit.user_settings import clear_list_filters_and_sort

LISTS = ("Connection Card Interest", "Family", "Follow-up Workflow", "Group Join Request", "Pathway")


def execute():
	clear_list_filters_and_sort(LISTS)
