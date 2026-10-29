# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the two Email Templates that group join requests send. A site's own copy stays."""

from churchit.patches.after_install import create_unsynced_records


def execute():
	create_unsynced_records()
