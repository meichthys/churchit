# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Hide the dock entries that each existing desk user cannot use, in the user's own layer."""

from churchit.church_setup.doctype.church_features.user_dock import sync_every_user


def execute():
	sync_every_user()
