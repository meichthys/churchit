# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""MariaDB date and math functions for use with ``frappe.qb``.

The Query Builder ships the standard aggregates (``Sum``, ``Count``,
``Coalesce`` ...) in :mod:`frappe.query_builder.functions`. The functions here
are the MariaDB-specific ones the reports in this app need, which the builder
has no wrapper for.
"""

import calendar
from datetime import timedelta

from frappe.query_builder import Criterion
from frappe.utils import getdate
from pypika import CustomFunction

CurDate = CustomFunction("CURDATE", [])
Date = CustomFunction("DATE", ["expression"])
DateDiff = CustomFunction("DATEDIFF", ["end", "start"])
Day = CustomFunction("DAY", ["date"])
DayOfMonth = CustomFunction("DAYOFMONTH", ["date"])
DayOfWeek = CustomFunction("DAYOFWEEK", ["date"])
Greatest = CustomFunction("GREATEST", ["first", "second"])
Month = CustomFunction("MONTH", ["date"])
Round = CustomFunction("ROUND", ["value", "places"])
Year = CustomFunction("YEAR", ["date"])

# The unit argument is a bare SQL keyword, so it must be passed as a
# LiteralValue rather than a string, which would come out quoted.
TimestampDiff = CustomFunction("TIMESTAMPDIFF", ["unit", "start", "end"])


def this_week():
	"""The first and last day of the current Monday-to-Sunday week."""
	monday = getdate() - timedelta(days=getdate().weekday())
	return monday, monday + timedelta(days=6)


def falls_this_week(column):
	"""Criterion: the month and day of *column* land in the current Monday-to-Sunday
	week, in any year.

	Anniversaries cannot be matched with ``WEEK(column) = WEEK(CURDATE())`` because
	the week number of a given month and day drifts from one year to the next.
	"""
	return month_day_this_week(Month(column), Day(column))


def month_day_this_week(month, day):
	"""Criterion: the *month* and *day* columns name a day of the current week, in any year.

	It compares (month, day) pairs, since a week across the new year is no single range.
	In a common year, February 29 counts on the 28th.
	"""
	monday, _sunday = this_week()
	dates = [monday + timedelta(days=offset) for offset in range(7)]
	pairs = {(date.month, date.day) for date in dates}
	pairs |= {
		(2, 29) for date in dates if (date.month, date.day) == (2, 28) and not calendar.isleap(date.year)
	}
	return Criterion.any((month == pair[0]) & (day == pair[1]) for pair in sorted(pairs))
