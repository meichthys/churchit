# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the starting spiritual gifts a person can have."""

from churchit.church_people.doctype.skill.skill import create_spiritual_gifts


def execute():
	create_spiritual_gifts()
