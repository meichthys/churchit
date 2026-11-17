# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

from churchit.church_scope import is_multi_church
from churchit.utils import get_dated_title


class WeeklyMetrics(Document):
	"""One church's figures for one week, written only by `churchit.church_summary.metrics`."""

	def validate(self):
		self.title = get_title(self.week_start, self.church)


def get_title(week_start, church: str) -> str:
	"""The first day of the week in the long form, with the church's abbreviation where each church has a row for the week."""
	title = get_dated_title(None, week_start)
	if not is_multi_church():
		return title
	return f"{title}, {frappe.get_cached_value('Church', church, 'abbreviation')}"
