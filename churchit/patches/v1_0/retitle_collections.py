# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title every existing Collection with its day and its Function's name, as a save now does."""

import frappe

from churchit.church_finances.doctype.collection.collection import get_title


def execute():
	function_names = dict(frappe.get_all("Function", fields=["name", "function_name"], as_list=True))
	for collection in frappe.get_all("Collection", fields=["name", "function", "date", "title"]):
		title = get_title(function_names.get(collection.function), collection.date)
		if collection.title != title:
			frappe.db.set_value("Collection", collection.name, "title", title, update_modified=False)
