# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Make the sermon list of the shipped sermons Web Page update by itself on existing sites.

The list becomes a part of its own (id sermon-list) that reads itself again when a sermon or a series
changes (church_website/live.py). The page is user-owned starter data: it changes only while it still
has the shipped text this patch replaces, so a page the church rewrote stays as it is.
"""

from churchit.patches.v1_0.fix_shipped_sermon_excerpt_and_missions_map import fix_page

SERMON_LIST = (
	(
		"{%- endmacro -%}\n\n{% if published_sermons %}",
		"{%- endmacro -%}\n\n</div>\n\n"
		'<div class="row justify-content-center" id="sermon-list" data-live="Sermon,Sermon Series">\n'
		"{% if published_sermons %}",
	),
)

GROUPS = {"sermons": (SERMON_LIST,)}


def execute():
	for name, groups in GROUPS.items():
		fix_page(name, groups)
