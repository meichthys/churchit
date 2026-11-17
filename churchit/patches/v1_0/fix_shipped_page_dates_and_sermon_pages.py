# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the shipped home, sermons, ministries and missions Web Pages on existing sites.

Dates read "Sunday, November 15, 2026", as emails and prints do; the home Upcoming list, where space
is tight, uses the site's short date format. The home page leaves out a recurring template, whose
first date is a real occurrence of its own. The sermons page shows 12 sermons a page with Older and
Newer links. A missionary card without a photo is only as tall as its text.

The pages are user-owned starter data. Each group below replaces text this app shipped, and it
applies only when the page still has all of its shipped text, so a page the church rewrote stays
as it is.
"""

from churchit.patches.v1_0.fix_shipped_sermon_excerpt_and_missions_map import fix_page

LONG_DATE = '"EEEE, MMMM d, yyyy")'

NEXT_GATHERING_DATE = (
	(
		'frappe.utils.format_date(next_up.start_date, "EEEE, d MMMM")',
		f"frappe.utils.format_date(next_up.start_date, {LONG_DATE}",
	),
)

UPCOMING_DATE = (
	(
		'frappe.utils.format_date(event.start_date, "EEE, d MMM")',
		"frappe.utils.format_date(event.start_date)",
	),
)

UPCOMING_TEMPLATES = (
	(
		"filters=selected_church_filters(publish=1, is_link_only=0, start_date=",
		"filters=selected_church_filters(publish=1, is_link_only=0, auto_repeat=0, start_date=",
	),
)

SERMON_DATE = (
	(
		'frappe.utils.formatdate(sermon.sermon_date, "d MMMM yyyy")',
		f"frappe.utils.formatdate(sermon.sermon_date, {LONG_DATE}",
	),
)

SERMON_PAGES = (
	(
		"{%- set published_sermons = frappe.get_all(\n",
		"{%- set page_length = 12 -%}\n"
		"{%- set page_number = [frappe.utils.cint(frappe.form_dict.page), 1] | max -%}\n"
		"{%- set sermon_rows = frappe.get_all(\n",
	),
	(
		'    order_by="sermon_date desc, modified desc"\n) -%}\n',
		'    order_by="sermon_date desc, modified desc",\n'
		"    limit_start=(page_number - 1) * page_length,\n"
		"    limit_page_length=page_length + 1\n"
		") -%}\n"
		"{%- set has_older = sermon_rows | length > page_length -%}\n"
		"{%- set published_sermons = sermon_rows[:page_length] -%}\n",
	),
	(
		"{%- set preacher_ids = published_sermons",
		'{%- set page_series = published_sermons | map(attribute="series") | select | unique | list -%}\n'
		'{%- set series_totals = dict(frappe.get_all("Sermon", fields=["series", {"COUNT": "name", "as": "total"}], '
		'filters=selected_church_filters(publish=1, series=("in", page_series)), group_by="series", '
		"ignore_permissions=True, as_list=True)) if page_series else {} -%}\n"
		"{%- set preacher_ids = published_sermons",
	),
	(
		"{%- macro sermon_meta(sermon) -%}",
		"{%- macro page_url(number) -%}\n"
		"  {%- set params = [] -%}\n"
		'  {%- if frappe.form_dict.church %}{% set _ = params.append(("church", frappe.form_dict.church)) %}{% endif -%}\n'
		'  {%- if q %}{% set _ = params.append(("q", q)) %}{% endif -%}\n'
		'  {%- if number > 1 %}{% set _ = params.append(("page", number)) %}{% endif -%}\n'
		'  {{- "/sermons" -}}{%- if params %}?{{ params | urlencode }}{% endif -%}\n'
		"{%- endmacro -%}\n\n"
		"{%- macro sermon_meta(sermon) -%}",
	),
	(
		'              <div class="small text-muted mb-2">{{ series_sermons | length }} sermon'
		'{{ "" if series_sermons | length == 1 else "s" }} in this series</div>',
		"              {%- set series_total = series_totals.get(series.name) or series_sermons | length -%}\n"
		'              <div class="small text-muted mb-2">{{ series_total }} sermon'
		'{{ "" if series_total == 1 else "s" }} in this series'
		"{% if series_sermons | length < series_total %} ({{ series_sermons | length }} on this page){% endif %}</div>",
	),
	(
		"  {% endfor %}\n\n{% elif q %}",
		"  {% endfor %}\n\n"
		"  {% if page_number > 1 or has_older %}\n"
		'  <nav class="col-12 d-flex justify-content-between" aria-label="Sermon pages">\n'
		'    {% if page_number > 1 %}<a class="btn btn-default" href="{{ page_url(page_number - 1) }}">'
		"&larr; Newer sermons</a>{% else %}<span></span>{% endif %}\n"
		'    {% if has_older %}<a class="btn btn-default" href="{{ page_url(page_number + 1) }}">'
		"Older sermons &rarr;</a>{% endif %}\n"
		"  </nav>\n"
		"  {% endif %}\n\n"
		"{% elif page_number > 1 %}\n"
		'  <div class="col-lg-8 col-md-10 text-center" style="padding: 60px 20px;">\n'
		'    <p class="text-muted" style="font-size: 1.1em;">There are no more sermons.</p>\n'
		'    <a href="{{ page_url(1) }}">Show the newest sermons</a>\n'
		"  </div>\n"
		"{% elif q %}",
	),
)

MINISTRY_DATE = (
	(
		'frappe.utils.formatdate(ministry.start_date, "d MMMM yyyy")',
		f"frappe.utils.formatdate(ministry.start_date, {LONG_DATE}",
	),
)

MISSIONARY_CARD_HEIGHT = (('<div class="card h-100">', '<div class="card">'),)

GROUPS = {
	"home": (NEXT_GATHERING_DATE, UPCOMING_DATE, UPCOMING_TEMPLATES),
	"sermons": (SERMON_DATE, SERMON_PAGES),
	"ministries": (MINISTRY_DATE,),
	"missions": (MISSIONARY_CARD_HEIGHT,),
}


def execute():
	for name, groups in GROUPS.items():
		fix_page(name, groups)
