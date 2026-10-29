# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the starter Group Types new installs now get."""

from churchit.patches.after_install import create_group_types


def execute():
	create_group_types()
