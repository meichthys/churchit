# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the shipped sermons, home and missions Web Pages on existing sites.

The sermon summary starts at the first paragraph, so an outline heading no longer runs into it, and
it leaves out the square brackets of a handout blank. The missions page shows the map only when it
lists a missionary, and leaves out Inactive missionaries.

The pages are user-owned starter data. Each group below replaces text this app shipped. A group
applies only when the page still has all of its shipped text, so a page the church rewrote stays
as it is.
"""

import frappe

OLD_EXCERPT = '{}.notes.split("</p>")[0] | striptags | truncate(180, False, "…") | e'
NEW_EXCERPT = (
	'({0}.notes.split("<p>", 1)[1].split("</p>")[0] if "<p>" in {0}.notes else {0}.notes)'
	' | striptags | replace("[", "") | replace("]", "") | truncate(180, False, "…") | e'
)

MAP_CARD = '<div class="missions-map-card">\n    <div id="missions-map" class="missions-map"></div>\n</div>\n'
SHIPPED_FILTERS = "filters=selected_church_filters(publish=1), ignore_permissions=True) %}"
FIXED_FILTERS = (
	'filters=selected_church_filters(publish=1, status=("!=", "Inactive")), ignore_permissions=True) %}'
)
SET_MISSIONARIES = '{% set missionary_docs = frappe.get_list("Missionary", fields=["name"], '

MISSIONS_GROUP = (
	(
		MAP_CARD
		+ "\n"
		+ '<div class="row justify-content-center">\n'
		+ SET_MISSIONARIES
		+ SHIPPED_FILTERS
		+ "\n{% if missionary_docs %}\n",
		SET_MISSIONARIES
		+ FIXED_FILTERS
		+ "\n{% if missionary_docs %}\n"
		+ MAP_CARD
		+ '\n<div class="row justify-content-center">\n',
	),
	(
		"{% endfor %}\n{% else %}\n    <div",
		'{% endfor %}\n</div>\n{% else %}\n<div class="row justify-content-center">\n    <div',
	),
	("    </div>\n{% endif %}\n</div>\n", "    </div>\n</div>\n{% endif %}\n"),
)

GROUPS = {
	"sermons": (((OLD_EXCERPT.format("sermon"), NEW_EXCERPT.format("sermon")),),),
	"home": (((OLD_EXCERPT.format("latest"), NEW_EXCERPT.format("latest")),),),
	"missions": (MISSIONS_GROUP,),
}


def execute():
	for name, groups in GROUPS.items():
		fix_page(name, groups)


def fix_page(name, groups):
	if not frappe.db.exists("Web Page", name):
		return

	doc = frappe.get_doc("Web Page", name)
	original = doc.main_section_html or ""
	html = original
	for group in groups:
		if all(shipped in html for shipped, _fixed in group):
			for shipped, fixed in group:
				html = html.replace(shipped, fixed)

	if html != original:
		doc.main_section_html = html
		doc.save(ignore_permissions=True)
