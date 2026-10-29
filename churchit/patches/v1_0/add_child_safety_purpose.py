# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Child Safety Communication Purpose, which pages from the Check-In Station ask consent for."""

from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	create_communication_purposes,
)


def execute():
	create_communication_purposes()
