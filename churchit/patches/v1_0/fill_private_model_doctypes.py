# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Start Only for Local or Zero Retention Models on Church AI Settings with the recommended doctypes
on existing sites. A list with rows stays as it is. after_migrate deletes the rows of doctypes that are
gone only after the patches, and such a row fails the save, so the patch deletes them first."""

from churchit.ai.flow_switch import forget_missing_blocked_doctypes
from churchit.ai.private_doctypes import fill_private_doctypes


def execute():
	forget_missing_blocked_doctypes()
	fill_private_doctypes()
