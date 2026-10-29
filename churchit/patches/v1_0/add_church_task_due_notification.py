# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Church Task Due Notification. A site's own changes to it stay."""

from churchit.church_operations.doctype.church_task.church_task import create_due_notification


def execute():
	create_due_notification()
