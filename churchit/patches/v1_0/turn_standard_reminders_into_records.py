# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Replace the three standard reminder Notifications with records that are not standard.

Production cannot turn on a standard Notification, so People Settings now turns these on. A site
keeps whether each was on and its days, and People Settings shows them. A church's own copy, with
another name, stays as it is.
"""

import frappe

from churchit.church_people.doctype.people_settings.people_settings import REMINDERS, create_reminders


def execute():
	kept = {}
	for name in REMINDERS:
		standard = frappe.db.get_value(
			"Notification", {"name": name, "is_standard": 1}, ["enabled", "days_in_advance"], as_dict=True
		)
		if standard:
			kept[name] = standard
			frappe.delete_doc("Notification", name, force=True, ignore_permissions=True)

	create_reminders()
	for name, values in kept.items():
		frappe.db.set_value("Notification", name, values)

	# People Settings shows each reminder as it now stands.
	for name, (switch, days) in REMINDERS.items():
		reminder = frappe.db.get_value("Notification", name, ["enabled", "days_in_advance"], as_dict=True)
		if reminder:
			frappe.db.set_single_value(
				"People Settings", {switch: reminder.enabled, days: reminder.days_in_advance}
			)
