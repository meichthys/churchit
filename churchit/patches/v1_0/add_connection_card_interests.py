# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the starting interests a guest can tick on the Connection Card web form."""

from churchit.church_people.doctype.connection_card_interest.connection_card_interest import (
	create_connection_card_interests,
)


def execute():
	create_connection_card_interests()
