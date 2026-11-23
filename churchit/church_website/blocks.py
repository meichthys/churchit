# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the church's Web Template blocks show (church_website/web_template), on a Page Builder Web Page.

The home page is built from these blocks, and a church can add, move, retitle or hide them in the desk
as it does Frappe's own blocks, on any Web Page. Each function reads the selected church's public
records with church_filters, as the public pages do, and returns plain values; its template only lays
them out. Those records change without a save of the page, so each read keeps the page out of Frappe's
page cache.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, format_time, formatdate, getdate, nowdate, strip_html

from churchit.church_foundations.doctype.church.church import (
	church_contact_details,
	get_church,
	selected_church_name,
)
from churchit.church_people.group_meetings import describe_schedule_time
from churchit.church_scope import church_filters
from churchit.church_website.footer import get_footer_church
from churchit.church_website.pages import get_hidden_pages, is_link_off
from churchit.scripture import get_default_translation, get_printable_passage
from churchit.www.calendar import get_live_url
from churchit.www.podcast import get_feed_url
from churchit.www.register import get_open_functions

# The blocks of the shipped home page, in order: (Web Template, its values).
HOME_BLOCKS = (
	("Church Welcome", {}),
	("Church Events", {"count": 5}),
	("Church Sermons", {"count": 3}),
	("Church Announcements", {}),
	("Church Ministries", {"count": 6}),
	("Church Next Steps", {}),
	("Church Visit", {}),
)
LONG_DATE = "EEEE, MMMM d, yyyy"
TIME_FORMAT = "h:mm a"
SUMMARY_LENGTH = 180


def set_home_blocks(page) -> None:
	"""Make *page*, a Web Page, the shipped home page: the blocks of HOME_BLOCKS, from edge to edge.

	The page keeps its old HTML, so a church can switch the Content Type back to see it."""
	page.content_type = "Page Builder"
	page.dynamic_template = 0
	page.full_width = 1
	page.show_title = 0
	page.page_blocks = []
	for template, values in HOME_BLOCKS:
		page.append("page_blocks", {"web_template": template, "web_template_values": frappe.as_json(values)})


def get_church_welcome() -> frappe._dict | None:
	"""The church's name, mission, verse and photo, when it meets, a stream that is live now and what a
	visitor can do next, or None before the church is set up."""
	church = get_church()
	if not church:
		return None
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	place = get_footer_church()
	return frappe._dict(
		name=church.church_name,
		mission=church.mission_statement,
		verse=get_church_verse(church),
		image=church.image if church.image and not church.image.startswith("/private/") else None,
		gatherings=get_gatherings(church.name),
		address=place.address,
		map_url=place.map_url,
		live=get_live_function(hidden),
		actions=get_links(
			(
				("/connection-card/new", _("Plan a visit")),
				("/calendar", _("See the calendar")),
				("/contact", _("Get in touch")),
			),
			hidden,
		),
	)


def get_gatherings(church: str) -> list[frappe._dict]:
	"""When the church meets: each published repeating Function, such as "Weekly on Sunday at 10:00 AM",
	or else the next gathering on the calendar."""
	templates = frappe.get_all(
		"Function",
		filters=church_filters(church, publish=1, is_link_only=0, auto_repeat=1),
		fields=[
			"function_name",
			"start_date",
			"start_time",
			"all_day",
			"repeat_frequency",
			"repeat_interval",
			"repeat_day_of_week",
			"repeat_monthly_by",
			"repeat_week_of_month",
			"repeat_month_day",
			"repeat_until",
		],
		order_by="start_time asc",
	)
	today = getdate()
	gatherings = [
		frappe._dict(name=template.function_name, when=describe_schedule_time(template))
		for template in templates
		if not template.repeat_until or getdate(template.repeat_until) >= today
	]
	if gatherings:
		return gatherings
	return [
		frappe._dict(name=function.title, when=_("Next on {0}").format(function.when))
		for function in get_functions(church, 1)
	]


def get_church_verse(church) -> frappe._dict | None:
	"""The church's verse, with its text when the church's Bible translation is ready to read now."""
	if not church.church_verse:
		return None
	translation = get_default_translation(church.name)
	# A Free Use translation not yet downloaded would download while the visitor waits.
	if not translation or frappe.get_cached_value("Bible Translation", translation, "status") != "Ready":
		return frappe._dict(reference=church.church_verse, text=None)
	return get_printable_passage(church.church_verse, church.name, limit=400)


def get_live_function(hidden: set[str]) -> frappe._dict | None:
	"""The streamed Function of the selected church that is live now, with its /live link."""
	if "live" in hidden:
		return None
	today = getdate()
	functions = frappe.get_all(
		"Function",
		filters=church_filters(
			selected_church_name(),
			publish=1,
			streamed=1,
			auto_repeat=0,
			start_date=["between", [add_days(today, -1), today]],
		),
		fields=[
			"function_name",
			"church",
			"streamed",
			"start_date",
			"start_time",
			"end_date",
			"end_time",
			"all_day",
		],
	)
	streams = {}
	for function in functions:
		if url := get_live_url(function, streams):
			return frappe._dict(title=function.function_name, url=url)
	return None


def get_church_events(count: int | None = None) -> frappe._dict:
	"""The next published gatherings, each with a link to it on the calendar and to its sign-up while it
	takes one, and the link to the calendar."""
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	calendar_on = not is_link_off("/calendar", hidden)
	register_on = not is_link_off("/register", hidden)
	open_for_sign_up = {function.name for function in get_open_functions()} if register_on else set()
	functions = get_functions(selected_church_name(), cint(count) or 5)
	for function in functions:
		function.url = f"/calendar?event={function.name}" if calendar_on else None
		function.register_url = (
			f"/register?function={function.name}" if function.name in open_for_sign_up else None
		)
	return frappe._dict(functions=functions, calendar_url="/calendar" if calendar_on else None)


def get_functions(church: str, count: int) -> list[frappe._dict]:
	"""The next *count* published Functions of *church* from today on, with their day, time and place."""
	functions = frappe.get_all(
		"Function",
		filters=church_filters(
			church, publish=1, is_link_only=0, auto_repeat=0, start_date=[">=", nowdate()]
		),
		fields=[
			"name",
			"function_name",
			"title",
			"start_date",
			"start_time",
			"all_day",
			"description",
			"address",
		],
		order_by="start_date asc, start_time asc",
		limit=count,
	)
	today = getdate()
	places = get_address_titles({function.address for function in functions if function.address})
	return [
		frappe._dict(
			name=function.name,
			title=function.function_name or function.title,
			number=formatdate(function.start_date, "d"),
			weekday=formatdate(function.start_date, "EEE"),
			month=formatdate(function.start_date, "MMM"),
			is_today=getdate(function.start_date) == today,
			date=formatdate(function.start_date, LONG_DATE),
			time=_("All day")
			if function.all_day or not function.start_time
			else format_time(function.start_time, TIME_FORMAT),
			when=get_when(function),
			place=places.get(function.address),
			description=function.description,
		)
		for function in functions
	]


def get_when(function) -> str:
	"""When *function* starts, such as "Monday, November 23, 2026 at 10:00 AM", or the day alone."""
	date = formatdate(function.start_date, LONG_DATE)
	if function.all_day or not function.start_time:
		return date
	return _("{0} at {1}").format(date, format_time(function.start_time, TIME_FORMAT))


def get_address_titles(addresses: set[str]) -> dict[str, str]:
	"""The title of each of *addresses*, the place a Function names."""
	if not addresses:
		return {}
	return dict(
		frappe.get_all(
			"Address",
			filters={"name": ("in", list(addresses))},
			fields=["name", "address_title"],
			as_list=True,
		)
	)


def get_church_sermons(count: int | None = None) -> frappe._dict:
	"""The newest published sermons with their preacher, series and summary, and the links to every sermon
	and to the podcast."""
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	if is_link_off("/sermons", hidden):
		return frappe._dict(sermons=[])
	church = selected_church_name()
	sermons = frappe.get_all(
		"Sermon",
		filters=church_filters(church, publish=1),
		fields=[
			"name",
			"title",
			"sermon_date",
			"scripture",
			"notes",
			"handout",
			"audio_recording",
			"prepared_by",
			"series",
		],
		order_by="sermon_date desc, modified desc",
		limit=cint(count) or 3,
	)
	preacher_ids = list({sermon.prepared_by for sermon in sermons if sermon.prepared_by})
	series_ids = list({sermon.series for sermon in sermons if sermon.series})
	preachers = dict(
		frappe.get_all(
			"Person", filters={"name": ("in", preacher_ids)}, fields=["name", "full_name"], as_list=True
		)
		if preacher_ids
		else []
	)
	series = dict(
		frappe.get_all(
			"Sermon Series",
			filters={"name": ("in", series_ids)},
			fields=["name", "series_name"],
			as_list=True,
		)
		if series_ids
		else []
	)
	sermon_page_on = not is_link_off("/sermon", hidden)
	return frappe._dict(
		sermons=[
			frappe._dict(
				title=sermon.title,
				url=f"/sermon/{sermon.name}" if sermon_page_on else None,
				date=formatdate(sermon.sermon_date, LONG_DATE) if sermon.sermon_date else None,
				preacher=preachers.get(sermon.prepared_by),
				series=series.get(sermon.series),
				scripture=sermon.scripture,
				summary=get_summary(sermon.notes) if not sermon.handout else None,
				audio=sermon.audio_recording,
			)
			for sermon in sermons
		],
		sermons_url="/sermons",
		podcast_url=None if is_link_off("/podcast.xml", hidden) else get_feed_url(church),
	)


def get_summary(notes: str | None) -> str | None:
	"""The opening paragraph of a sermon's notes as plain text, without the handout's [blanks]."""
	if not notes:
		return None
	opening = notes.split("<p>", 1)[1].split("</p>")[0] if "<p>" in notes else notes
	text = " ".join(strip_html(opening).replace("[", "").replace("]", "").split())
	return text if len(text) <= SUMMARY_LENGTH else text[:SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"


def get_church_announcements(count: int | None = None) -> frappe._dict:
	"""The announcements the selected church shares from its newest published bulletins."""
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	bulletins = frappe.get_all(
		"Bulletin",
		filters=church_filters(
			selected_church_name(),
			**{"publish": 1, "share_announcements": 1, "announcements": ("is", "set")},
		),
		fields=["function_name", "function_date", "announcements"],
		order_by="function_date desc",
		limit=cint(count) or 1,
	)
	for bulletin in bulletins:
		bulletin.date = formatdate(bulletin.function_date, LONG_DATE) if bulletin.function_date else None
	return frappe._dict(
		bulletins=bulletins, url=None if is_link_off("/announcements", hidden) else "/announcements"
	)


def get_church_ministries(count: int | None = None) -> frappe._dict:
	"""The selected church's published, active ministries, each with a line about it."""
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	ministries = frappe.get_all(
		"Ministry",
		filters=church_filters(selected_church_name(), publish=1, status="Active"),
		fields=["ministry_name", "mission_statement", "description"],
		order_by="ministry_name asc",
		limit=cint(count) or 6,
	)
	return frappe._dict(
		ministries=[
			frappe._dict(
				name=ministry.ministry_name,
				text=ministry.mission_statement or get_summary(ministry.description),
			)
			for ministry in ministries
		],
		url=None if is_link_off("/ministries", hidden) else "/ministries",
	)


def get_church_next_steps() -> list[frappe._dict]:
	"""A visitor's next steps, each a page of the site that is on for them."""
	steps = (
		(
			"/connection-card/new",
			_("I'm new"),
			_("Tell us a little about yourself, and we will be in touch."),
		),
		("/find-a-group", _("Find a group"), _("Meet with others during the week to study, pray and serve.")),
		("/prayer-request-anonymous/new", _("Ask for prayer"), _("Send us a prayer request. We will pray.")),
		("/beliefs", _("What we believe"), _("Read what our church believes and why.")),
		("/missions", _("Missions"), _("Meet the missionaries our church supports.")),
		("/give", _("Give"), _("Support the ministry of our church.")),
	)
	hidden = get_hidden_pages()
	return [
		frappe._dict(url=url, title=title, text=text)
		for url, title, text in steps
		if not is_link_off(url, hidden)
	]


def get_church_visit() -> frappe._dict | None:
	"""Where the church is and how to reach it, with the opening of its About text, or None before setup."""
	church = get_church()
	if not church:
		return None
	keep_out_of_page_cache()
	hidden = get_hidden_pages()
	place = get_footer_church()
	contact = church_contact_details(church)
	return frappe._dict(
		name=church.church_name,
		about=get_summary(church.about),
		about_url=None if is_link_off("/about", hidden) else "/about",
		address=place.address,
		map_url=place.map_url,
		phone=contact.phone,
		email=contact.email,
		contact_url=None if is_link_off("/contact", hidden) else "/contact",
	)


def get_links(links, hidden: set[str]) -> list[frappe._dict]:
	"""Each (url, label) of *links* whose page is on for this visitor."""
	return [frappe._dict(url=url, label=label) for url, label in links if not is_link_off(url, hidden)]


def keep_out_of_page_cache() -> None:
	"""Frappe caches a page for 30 minutes; a block's records change without a save of the page."""
	frappe.local.no_cache = 1
