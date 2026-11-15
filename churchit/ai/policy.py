# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What churchit promises about AI, for the people a church serves."""

import frappe

PAGE_NAME = "how-we-use-ai"


def create_how_we_use_ai_page() -> None:
	"""Insert the unpublished starter Web Page "How We Use AI" once. The church owns it afterwards."""
	from churchit.patches.after_install import read_template

	if frappe.db.exists("Web Page", PAGE_NAME):
		return

	frappe.get_doc(
		{
			"doctype": "Web Page",
			"name": PAGE_NAME,
			"title": "How We Use AI",
			"route": PAGE_NAME,
			"published": 0,
			"content_type": "HTML",
			"module": "Church Website",
			"full_width": 0,
			"show_title": 1,
			"main_section_html": read_template("how_we_use_ai.html"),
		}
	).insert(ignore_permissions=True)
