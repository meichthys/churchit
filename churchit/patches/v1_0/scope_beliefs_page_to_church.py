# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Scope the shipped beliefs page, now that a belief belongs to a church.

Belief was global when the other pages were scoped, so the beliefs page was left
out of that patch. It reuses the same rewrite, which leaves a church that reworded
its own query alone.
"""

from churchit.patches.v1_0.scope_website_pages_to_church import scope_page


def execute():
	scope_page("beliefs")
