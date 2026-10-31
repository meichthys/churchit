# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Address read rule that new installs now get."""

from churchit.patches.after_install import let_church_roles_read_addresses


def execute():
	let_church_roles_read_addresses()
