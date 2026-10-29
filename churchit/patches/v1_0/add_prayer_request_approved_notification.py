# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Notification that tells the prayer team of a request approved after it was made.

Only that one: a Notification that a church deleted stays deleted.
"""

from churchit.church_prayers.doctype.prayer_request.prayer_request import (
	APPROVED_NOTIFICATION,
	create_new_prayer_request_notifications,
)


def execute():
	create_new_prayer_request_notifications(names=(APPROVED_NOTIFICATION,))
