# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Name the replacement in the Ministry Team Decline email, which said the position was open again.

Only a copy that still has the shipped text gets the new text. A church's own words stay.
"""

import json
from pathlib import Path

import frappe

FOLDER = "ministry_team_decline_template"
SHIPPED_HTML = (
	"<p>{{ person_name | e }} declined to serve as <strong>{{ position | e }}</strong> ({{ ministry | e }}) "
	"at {{ function | e }} on {{ date }}{% if time %} at {{ time }}{% endif %}.</p>\n\n"
	"{% if decline_reason %}<p>Reason: {{ decline_reason | e }}</p>{% endif %}\n\n"
	'<p>The position is open again. <a href="{{ assignment_link }}">Open the assignment</a></p>'
)


def execute():
	folder = Path(frappe.get_app_path("churchit", "church_communications", "email_template", FOLDER))
	values = json.loads((folder / f"{FOLDER}.json").read_text())
	if frappe.db.get_value("Email Template", values["name"], "response_html") == SHIPPED_HTML:
		frappe.db.set_value("Email Template", values["name"], "response_html", values["response_html"])
