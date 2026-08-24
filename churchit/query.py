# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

"""MariaDB date and math functions for use with ``frappe.qb``.

The Query Builder ships the standard aggregates (``Sum``, ``Count``,
``Coalesce`` ...) in :mod:`frappe.query_builder.functions`. The functions here
are the MariaDB-specific ones the reports in this app need, which the builder
has no wrapper for.
"""

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
Week = CustomFunction("WEEK", ["date", "mode"])
Year = CustomFunction("YEAR", ["date"])

# The unit argument is a bare SQL keyword, so it must be passed as a
# LiteralValue rather than a string, which would come out quoted.
TimestampDiff = CustomFunction("TIMESTAMPDIFF", ["unit", "start", "end"])
