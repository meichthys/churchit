# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rename the Skill doctype to Church Skill, because Frappe HR ships a Skill doctype too.

Frappe keeps one record per name, so the two apps could not share a site.
"""

from churchit.patches.v1_0.rename_records_that_clash_with_erpnext import rename_records


def execute():
	rename_records((("DocType", "Skill", "Church Skill", "Church People"),))
