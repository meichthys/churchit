# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give the weekly AI note its own Notification Type on existing sites, so that Frappe emails it. The note
was an Alert, which Frappe shows only in the desk."""

from churchit.church_summary.ai import create_note_type


def execute():
	create_note_type()
