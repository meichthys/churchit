# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Mark the walk-ins the Check-In Station added as Visitors who share nothing.

The station added them with no Membership and the directory share defaults, so the member directory
listed them with the phone number the volunteer typed. They never saw that choice. A walk-in with a
portal login may have made their own choices since, so they are left alone.
"""

import frappe

from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.doctype.person.person import SOURCE_CHECK_IN
from churchit.church_people.membership import VISITOR


def execute():
	walk_ins = frappe.get_all(
		"Person",
		filters={"source": SOURCE_CHECK_IN, "membership": ("is", "not set"), "user": ("is", "not set")},
		pluck="name",
	)
	for name in walk_ins:
		frappe.db.set_value(
			"Person", name, {"membership": VISITOR, **dict.fromkeys(SHARE_DEFAULTS, 0)}, update_modified=False
		)
