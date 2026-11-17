# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the shipped sermons, missions, ministries, beliefs and home Web Pages on existing sites.

Each list page reads its records in one query, and the preacher, agency and country names in one
more each, not one query or more for every sermon, missionary, ministry or belief. In a sermon
series card the sermons are buttons that move focus to the sermon they open and back to the button,
and the headings of the sermons and home pages no longer skip a level.

The pages are user-owned starter data. Each group below replaces text this app shipped, and it
applies only when the page still has all of its shipped text, so a page the church rewrote stays
as it is.
"""

from churchit.patches.v1_0.fix_shipped_sermon_excerpt_and_missions_map import fix_page

SERMON_PREACHERS = (
	(
		"{%- set off_pages = get_switched_off_pages() -%}\n",
		'{%- set preacher_ids = published_sermons | map(attribute="prepared_by") | select | unique | list -%}\n'
		'{%- set preachers = dict(frappe.get_all("Person", filters={"name": ("in", preacher_ids)}, '
		'fields=["name", "full_name"], as_list=True)) if preacher_ids else {} -%}\n'
		"{%- set off_pages = get_switched_off_pages() -%}\n",
	),
	('frappe.db.get_value("Person", sermon.prepared_by, "full_name")', "preachers.get(sermon.prepared_by)"),
)

SERMON_SERIES_BUTTONS = (
	(
		'<a href="#" class="series-sermon-link" data-sermon-link="{{ loop.index }}">{{ sermon.title | e }}</a>',
		'<button type="button" class="series-sermon-link" data-sermon-link="{{ loop.index }}">'
		"{{ sermon.title | e }}</button>",
	),
	(
		'<a href="#" class="series-back small" data-series-back>&larr; Back to series</a>',
		'<button type="button" class="series-back small" data-series-back>&larr; Back to series</button>',
	),
	(
		'<h6 class="mt-2 mb-1">{% if "sermon" in off_pages %}',
		'<h2 class="h6 mt-2 mb-1" tabindex="-1" data-sermon-title>{% if "sermon" in off_pages %}',
	),
	("{% endif %}</h6>", "{% endif %}</h2>"),
	(
		"      e.preventDefault();\n      var card = link.closest",
		"      var card = link.closest",
	),
	(
		'      });\n      return;\n    }\n    var back = e.target.closest("[data-series-back]");',
		"      });\n"
		"      card.querySelector('[data-sermon-detail=\"' + target + '\"] [data-sermon-title]').focus();\n"
		'      return;\n    }\n    var back = e.target.closest("[data-series-back]");',
	),
	(
		'      e.preventDefault();\n      var card = back.closest("[data-series-card]");\n      if (!card) return;\n',
		'      var card = back.closest("[data-series-card]");\n      if (!card) return;\n'
		'      var opened = back.closest("[data-sermon-detail]").getAttribute("data-sermon-detail");\n',
	),
	(
		'      card.querySelector("[data-series-list]").style.display = "block";\n',
		'      card.querySelector("[data-series-list]").style.display = "block";\n'
		"      card.querySelector('[data-sermon-link=\"' + opened + '\"]').focus();\n",
	),
)

MISSIONS = (
	(
		'frappe.get_list("Missionary", fields=["name"], ',
		'frappe.get_list("Missionary", fields=["name", "title", "agency", "photo", "country", "website", '
		'"sensitive"], ',
	),
	(
		'{% if missionary_docs %}\n<div class="missions-map-card">',
		"{% if missionary_docs %}\n"
		'{%- set agency_ids = missionary_docs | map(attribute="agency") | select | unique | list -%}\n'
		'{%- set agency_names = dict(frappe.get_all("Missionary Agency", filters={"name": ("in", agency_ids)}, '
		'fields=["name", "agency_name"], as_list=True)) if agency_ids else {} -%}\n'
		'{%- set country_ids = missionary_docs | map(attribute="country") | select | unique | list -%}\n'
		'{%- set country_codes = dict(frappe.get_all("Country", filters={"name": ("in", country_ids)}, '
		'fields=["name", "code"], as_list=True)) if country_ids else {} %}\n'
		'<div class="missions-map-card">',
	),
	(
		'{% for doc in missionary_docs if not frappe.get_doc("Missionary", doc.name).sensitive %}\n'
		'    {% set missionary = frappe.get_doc("Missionary", doc.name) %}\n',
		"{% for missionary in missionary_docs if not missionary.sensitive %}\n",
	),
	(
		'frappe.db.get_value("Missionary Agency", missionary.agency, "agency_name")',
		"agency_names.get(missionary.agency)",
	),
	('frappe.db.get_value("Country", missionary.country, "code")', "country_codes.get(missionary.country)"),
)

MINISTRIES = (
	(
		'frappe.get_list("Ministry", fields=["name"], ',
		'frappe.get_list("Ministry", fields=["name", "ministry_name", "start_date", "description", '
		'"mission_statement"], ',
	),
	(
		'{% for doc in ministry_docs %}\n    {% set ministry = frappe.get_doc("Ministry", doc.name) %}\n',
		"{% for ministry in ministry_docs %}\n",
	),
)

BELIEFS = (
	(
		'frappe.get_list("Belief", fields=["name"], ',
		'frappe.get_list("Belief", fields=["name", "title", "belief_statement", "bible_references"], ',
	),
	(
		'{% for doc in belief_docs %}\n    {% set belief = frappe.get_doc("Belief", doc.name) %}\n',
		"{% for belief in belief_docs %}\n",
	),
)

HOME_HEADINGS = (
	(
		'<div class="home-aside-title">{{ next_up.function_name or next_up.title }}</div>',
		'<h2 class="home-aside-title">{{ next_up.function_name or next_up.title }}</h2>',
	),
	(
		'<h3 class="home-panel-title">{{ latest.title }}</h3>',
		'<h2 class="home-panel-title">{{ latest.title }}</h2>',
	),
)

GROUPS = {
	"sermons": (SERMON_PREACHERS, SERMON_SERIES_BUTTONS),
	"missions": (MISSIONS,),
	"ministries": (MINISTRIES,),
	"beliefs": (BELIEFS,),
	"home": (HOME_HEADINGS,),
}


def execute():
	for name, groups in GROUPS.items():
		fix_page(name, groups)
