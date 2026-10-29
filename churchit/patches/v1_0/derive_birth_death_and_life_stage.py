# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Work out every person's birth date, death and life stage from their life events.

The living people filter reads the deceased box, so directories and birthday lists need it set before anyone
opens them. Life stage reads People Settings' adult age, so its defaults are stored first.
"""

from churchit.church_people.derived import refresh_daily
from churchit.church_people.doctype.people_settings.people_settings import store_defaults


def execute():
	store_defaults()
	refresh_daily()
