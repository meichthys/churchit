# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Work out every person's ministry teams, team positions and membership change dates for the first time."""

from churchit.church_people.summaries import refresh


def execute():
	refresh()
