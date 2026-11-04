# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each prayer with the name of the person who prayed and the day, not the Person ID and the time."""

import frappe

from churchit.church_prayers.doctype.prayer.prayer import get_prayer_title


def execute():
	prayers = frappe.get_all("Prayer", fields=["name", "person", "date", "title"])
	people = list({prayer.person for prayer in prayers if prayer.person})
	full_names = dict(
		frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", "full_name"], as_list=True)
	)
	for prayer in prayers:
		title = get_prayer_title(full_names.get(prayer.person), prayer.date)
		if title != prayer.title:
			frappe.db.set_value("Prayer", prayer.name, "title", title, update_modified=False)
