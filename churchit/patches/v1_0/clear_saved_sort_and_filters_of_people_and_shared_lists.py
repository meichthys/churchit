# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Open the desk lists that the UX roadmap changed on their new defaults, for every user.

A user's saved filters and sort win over a list's own. The lists of records a church can share lost
their Shared filter, and a list saved with it stayed filtered on a field that no longer shows. The
People lists got a new sort, new columns and a default filter. The old Summary sidebar links saved
their filters onto the Prayer Request and Alms Request lists.
"""

from churchit.user_settings import clear_list_filters_and_sort

SHAREABLE_LISTS = (
	"Belief",
	"Church Asset",
	"Church Location",
	"Fund",
	"Function",
	"Meeting Minutes",
	"Ministry",
	"Question Set",
	"Room",
	"Sermon",
	"Sermon Handout",
	"Sermon Series",
	"Song",
	"Vendor",
)
PEOPLE_LISTS = ("Care Request", "Family", "Person")
SUMMARY_LISTS = ("Alms Request", "Prayer Request")
LISTS = SHAREABLE_LISTS + PEOPLE_LISTS + SUMMARY_LISTS


def execute():
	clear_list_filters_and_sort(LISTS)
