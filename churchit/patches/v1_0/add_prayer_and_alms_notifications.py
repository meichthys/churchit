# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Notifications for new prayer and alms requests. A site's own changes to them stay."""

from churchit.church_finances.doctype.alms_request.alms_request import create_new_alms_request_notification
from churchit.church_prayers.doctype.prayer_request.prayer_request import (
	create_new_prayer_request_notifications,
)


def execute():
	create_new_prayer_request_notifications()
	create_new_alms_request_notification()
