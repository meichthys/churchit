# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the default Background Check Types new installs now get."""

from churchit.church_people.doctype.background_check_type.background_check_type import (
	create_background_check_types,
)


def execute():
	create_background_check_types()
