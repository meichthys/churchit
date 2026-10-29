# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Print Volunteer check-ins on existing sites with the Volunteer Name Tag, which shows their team position."""

from churchit.church_ministries.doctype.check_in_settings.check_in_settings import add_volunteer_tag_format


def execute():
	add_volunteer_tag_format()
