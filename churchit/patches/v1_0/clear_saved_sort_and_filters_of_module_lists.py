# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Open the module lists that the UX roadmap changed on their new defaults, for every user.

A user's saved filters and sort win over a list's own. These lists got new columns, a new sort or
a default filter. A few lists also lost a sidebar link, count or card that saved its filter onto them.
"""

from churchit.user_settings import clear_list_filters_and_sort

PEOPLE_LISTS = (
	"Address Type",
	"Background Check Type",
	"Care Assignment",
	"Care Request Type",
	"Connection Card",
	"Connection Card Interest",
	"Email Type",
	"Follow-up Action Run",
	"Follow-up Card",
	"Follow-up Workflow",
	"Group",
	"Group File",
	"Group Join Request",
	"Group Role",
	"Group Status",
	"Group Type",
	"Inactive Reason",
	"Life Event Type",
	"Marital Status",
	"Member Status",
	"Membership Type",
	"Note Category",
	"Pathway",
	"Phone Type",
	"Position Type",
	"Visit Type",
)
MINISTRY_LISTS = (
	"Case Type",
	"Counseling Case",
	"Function",
	"Function Attendance Type",
	"Function Check-In",
	"Function Sign-Up",
	"Function Type",
	"Ministry",
	"Ministry Team Assignment",
	"Ministry Team Block",
	"Ministry Team Position",
	"Sign-Up Item",
	"Song",
)
FINANCE_LISTS = (
	"Alms Request",
	"Collection",
	"Expense",
	"Expense Type",
	"Fund",
	"Fund Transfer",
	"GL Account Mapping",
	"Giving Statement",
	"Online Donation",
	"Payment Type",
	"Pledge",
	"Pledge Campaign",
	"Vendor",
)
MISSION_AND_PRAYER_LISTS = (
	"Missionary",
	"Missionary Agency",
	"Missionary Status",
	"Missionary Support Frequency",
	"Prayer",
	"Prayer Request",
	"Prayer Request Status",
	"Prayer Request Type",
)
COMMUNICATION_LISTS = (
	"Bulletin",
	"Church Email",
	"Communication Consent",
	"Communication Purpose",
	"Push Subscription",
)
STUDY_LISTS = ("Bible Memory Item", "Bible Translation", "Sermon", "Sermon Handout", "Sermon Series")
OPERATION_LISTS = (
	"Church Asset",
	"Church Location",
	"Church Task",
	"Meeting Minutes",
	"Room",
	"Room Booking",
)
FOUNDATION_LISTS = ("Belief", "Church", "Form Response", "Question Set", "Weekly Metrics")
LISTS = (
	PEOPLE_LISTS
	+ MINISTRY_LISTS
	+ FINANCE_LISTS
	+ MISSION_AND_PRAYER_LISTS
	+ COMMUNICATION_LISTS
	+ STUDY_LISTS
	+ OPERATION_LISTS
	+ FOUNDATION_LISTS
)


def execute():
	clear_list_filters_and_sort(LISTS)
