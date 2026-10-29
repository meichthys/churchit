# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Inactive Reasons: the two the app sets, and each reason already typed on a Person.

Inactive Reason on Person was free text and is now a link, so every value it holds needs a record. A value is
tidied into a name Frappe accepts first, on the Person too, so the patch never stops a migrate over messy text.
"""

from churchit.church_people.doctype.inactive_reason.inactive_reason import create_inactive_reasons


def execute():
	create_inactive_reasons()
