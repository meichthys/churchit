# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Room Booking Decided Notification. A site's own changes to it stay."""

from churchit.church_operations.doctype.room_booking.room_booking import create_decided_notification


def execute():
	create_decided_notification()
