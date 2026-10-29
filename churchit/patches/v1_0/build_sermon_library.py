# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the sermon library: a dated, searchable /sermons that links each sermon.

The ``sermons`` Web Page is user-owned starter data, so only a page that still holds the template
this app shipped is replaced. Sites installed before the page was scoped to the church differ from
it by one blank line, so the comparison ignores whitespace. A church that edited its page keeps it.
"""

from pathlib import Path

import frappe
from frappe.query_builder.functions import Min

from churchit.patches.after_install import read_template

SHIPPED_SERMONS = (Path(__file__).resolve().parent / "templates" / "sermons_v1.html").read_text()


def execute():
	rewrite_shipped_page()
	date_sermons()


def rewrite_shipped_page():
	if not frappe.db.exists("Web Page", "sermons"):
		return

	doc = frappe.get_doc("Web Page", "sermons")
	if without_whitespace(doc.main_section_html) != without_whitespace(SHIPPED_SERMONS):
		print("Web Page sermons was edited, so it keeps its own layout without the sermon library.")
		return

	doc.main_section_html = read_template("sermons.html")
	doc.save(ignore_permissions=True)


def without_whitespace(html):
	return "".join((html or "").split())


def date_sermons():
	"""Date each undated sermon from its first presentation, without changing its modified time."""
	Presentation = frappe.qb.DocType("Sermon Presentation")
	first_dates = (
		frappe.qb.from_(Presentation)
		.select(Presentation.parent, Min(Presentation.date))
		.where(Presentation.parenttype == "Sermon")
		.where(Presentation.date.isnotnull())
		.groupby(Presentation.parent)
		.run()
	)
	undated = set(frappe.get_all("Sermon", filters={"sermon_date": ("is", "not set")}, pluck="name"))
	for sermon, first_date in first_dates:
		if sermon in undated:
			frappe.db.set_value("Sermon", sermon, "sermon_date", first_date, update_modified=False)
