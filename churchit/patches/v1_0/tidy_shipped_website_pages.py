# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the shipped home, sermons, ministries and missions Web Pages on existing sites.

The home page shows the newest sermon, hides its links to a switched-off calendar or contact page,
lists only the events after the next gathering, and no longer shows the default login before setup.
The home and sermons pages show a short, escaped summary of the notes, and none for a sermon with a
handout, whose notes hold its answers. Dates read "15 November 2026", and missionary photos have alt
text.

The pages are user-owned starter data, so each pair below replaces one piece of text this app
shipped. Each pair is safe alone, so a page gets whichever fixes it still has the shipped text for,
and a piece the church rewrote stays as it is.
"""

import frappe

SHIPPED_SETUP_MESSAGE = """        <h2 style="color: #4a4a4a; margin-bottom: 16px;">Welcome to Your Website</h2>
        <p style="font-size: 1.2em; color: #6c757d; margin-bottom: 32px;">
            Your new church website is almost ready!<br>
            To get started, please log in and configure your church information.<br>
            <br>
            The default login credentials are:<br>
            Username: Administrator<br>
            Password: admin<br>
            Be sure to change the password immediately!
        </p>
        <a href="/login" class="btn btn-primary btn-lg" style="padding: 12px 40px; font-size: 1.1em;">
            Log In to Get Started
        </a>
"""
SETUP_MESSAGE = """        <h2>{{ _("This website is being set up") }}</h2>
        <p class="text-muted">{{ _("Please check back soon.") }}</p>
        <a href="/login" class="btn btn-default">{{ _("Log In") }}</a>
"""

FIXES = {
	"home": (
		(
			'{%- set sermons_on = "sermons" not in get_switched_off_pages() -%}',
			'{%- set off_pages = get_switched_off_pages() -%}\n{%- set sermons_on = "sermons" not in off_pages -%}',
		),
		(
			'fields=["name", "title", "notes", "audio_recording", "prepared_by"],',
			'fields=["name", "title", "notes", "handout", "audio_recording", "prepared_by"],',
		),
		('order_by="modified desc",\n\tlimit=1,', 'order_by="sermon_date desc, modified desc",\n\tlimit=1,'),
		(
			'\t<a class="btn btn-primary btn-lg" href="/calendar">{{ _("See the calendar") }} &rarr;</a>\n',
			'\t{% if "calendar" not in off_pages %}<a class="btn btn-primary btn-lg" href="/calendar">'
			'{{ _("See the calendar") }} &rarr;</a>{% endif %}\n',
		),
		(
			'\t<a class="btn btn-lg home-btn-ghost" href="/contact">{{ _("Get in touch") }} &rarr;</a>\n',
			'\t{% if "contact" not in off_pages %}<a class="btn btn-lg home-btn-ghost" href="/contact">'
			'{{ _("Get in touch") }} &rarr;</a>{% endif %}\n',
		),
		(
			'\t<a class="home-aside-link" href="/calendar">{{ _("See the full calendar") }} &rarr;</a>\n',
			'\t{% if "calendar" not in off_pages %}<a class="home-aside-link" href="/calendar">'
			'{{ _("See the full calendar") }} &rarr;</a>{% endif %}\n',
		),
		("{% if latest.notes %}", "{% if latest.notes and not latest.handout %}"),
		('| striptags | truncate(180, False, "…") }}', '| striptags | truncate(180, False, "…") | e }}'),
		("{% if sermons or upcoming %}", "{% if sermons or upcoming[1:] %}"),
		(
			'{% if upcoming %}\n\t<div class="card home-panel">',
			'{% if upcoming[1:] %}\n\t<div class="card home-panel">',
		),
		("{% for event in upcoming %}", "{% for event in upcoming[1:] %}"),
		(SHIPPED_SETUP_MESSAGE, SETUP_MESSAGE),
	),
	"sermons": (
		(
			'fields=["name", "title", "sermon_date", "scripture", "notes", "audio_recording", "prepared_by", "series"],',
			'fields=["name", "title", "sermon_date", "scripture", "notes", "handout", "audio_recording", "prepared_by", "series"],',
		),
		(
			"{{ frappe.utils.formatdate(sermon.sermon_date) }}",
			'{{ frappe.utils.formatdate(sermon.sermon_date, "d MMMM yyyy") }}',
		),
		(
			'{% if sermon.notes %}<p class="card-text">{{ sermon.notes }}</p>{% endif %}',
			'{% if sermon.notes and not sermon.handout %}<p class="card-text">'
			'{{ sermon.notes.split("</p>")[0] | striptags | truncate(180, False, "…") | e }}</p>{% endif %}',
		),
	),
	"ministries": (
		(
			'frappe.utils.formatdate(ministry.start_date, "M/d/yyyy")',
			'frappe.utils.formatdate(ministry.start_date, "d MMMM yyyy")',
		),
	),
	"missions": (
		(
			'<img src="{{ missionary.photo }}">',
			'<img src="{{ missionary.photo }}" alt="{{ missionary.title | e }}">',
		),
	),
}


def execute():
	for name, fixes in FIXES.items():
		fix_page(name, fixes)


def fix_page(name, fixes):
	if not frappe.db.exists("Web Page", name):
		return

	doc = frappe.get_doc("Web Page", name)
	html = doc.main_section_html or ""
	for shipped, fixed in fixes:
		html = html.replace(shipped, fixed)
	if html == doc.main_section_html:
		return

	doc.main_section_html = html
	doc.save(ignore_permissions=True)
