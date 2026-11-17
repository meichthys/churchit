# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the New Care Request and Alms Request Approved Notifications. A site's own changes stay."""

from churchit.church_finances.doctype.alms_request.alms_request import (
	create_alms_request_approved_notification,
)
from churchit.church_people.doctype.care_request.care_request import create_new_care_request_notification


def execute():
	create_new_care_request_notification()
	create_alms_request_approved_notification()
