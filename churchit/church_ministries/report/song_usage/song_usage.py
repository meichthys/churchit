# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count, Max, Sum

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "song", "fieldtype": "Link", "label": _("Song"), "options": "Song", "width": 300},
		{"fieldname": "ccli", "fieldtype": "Data", "label": _("CCLI #"), "width": 120},
		{"fieldname": "times_used", "fieldtype": "Int", "label": _("Times Used"), "width": 110},
		{"fieldname": "last_used", "fieldtype": "Date", "label": _("Last Used"), "width": 120},
		{"fieldname": "displayed", "fieldtype": "Int", "label": _("Displayed"), "width": 100},
		{"fieldname": "printed", "fieldtype": "Int", "label": _("Printed"), "width": 100},
		{"fieldname": "streamed", "fieldtype": "Int", "label": _("Streamed"), "width": 100},
		{"fieldname": "recorded", "fieldtype": "Int", "label": _("Recorded"), "width": 100},
	]


def get_data(filters):
	"""How often each song is on the schedule of a function dated in the range, most used first.

	The copy types count the uses that displayed or printed the song, or were at a streamed or
	recorded function, for the church to report to CCLI.
	"""
	Schedule = frappe.qb.DocType("Function Schedule")
	Function = frappe.qb.DocType("Function")
	Song = frappe.qb.DocType("Song")
	times_used = Count(Schedule.name)
	query = (
		frappe.qb.from_(Schedule)
		.join(Function)
		.on(Schedule.parent == Function.name)
		.join(Song)
		.on(Schedule.item == Song.name)
		.select(
			Song.name.as_("song"),
			Song.ccli,
			times_used.as_("times_used"),
			Max(Function.start_date).as_("last_used"),
			Sum(Schedule.displayed).as_("displayed"),
			Sum(Schedule.printed).as_("printed"),
			Sum(Function.streamed).as_("streamed"),
			Sum(Function.recorded).as_("recorded"),
		)
		.where(
			(Schedule.parenttype == "Function")
			& (Schedule.item_type == "Song")
			& Function.start_date[filters.from_date : filters.to_date]
		)
		.groupby(Song.name, Song.ccli, Song.title)
		.orderby(times_used, order=Order.desc)
		.orderby(Song.title)
	)
	return scoped(query, Function, filters).run(as_dict=True)
