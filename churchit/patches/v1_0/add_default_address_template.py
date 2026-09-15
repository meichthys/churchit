# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the default Address Template new installs now get."""

from churchit.patches.after_install import create_default_address_template


def execute():
	create_default_address_template()
