# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from pathlib import Path

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.email.doctype.notification.notification import create_notifications, get_notification_templates
from frappe.model.document import Document
from frappe.utils import cint

from churchit.church_foundations import church_access
from churchit.church_people import geocoding
from churchit.church_people.derived import refresh_daily

DIRECTORY_ROUTE = "directory"
# Each Person field a member ticks to share a detail in the member directory, by the setting that is its default.
SHARE_DEFAULTS = {
	"share_email": "directory_share_email",
	"share_phone": "directory_share_phone",
	"share_address": "directory_share_address",
	"share_birthday": "directory_share_birthday",
}
# Each reminder Notification, by the fields that turn it on and set its days. Its JSON and message are in reminders/.
REMINDERS = {
	"Follow-up Card Overdue": ("remind_overdue_follow_up_cards", "follow_up_card_reminder_days"),
	"Care Request Overdue": ("remind_overdue_care_requests", "care_request_reminder_days"),
	"Visitation Follow-Up Due": ("remind_planned_visits", "visit_reminder_days"),
}


class PeopleSettings(Document):
	def onload(self):
		self.set_onload("has_every_church", church_access.has_every_church(frappe.session.user))

	def validate(self):
		church_access.refuse_changing_shared_settings(self)

	def on_update(self):
		if self.has_value_changed("adult_age") or self.has_value_changed("school_year_start_month"):
			frappe.enqueue(refresh_daily, enqueue_after_commit=True)
		self.set_share_defaults()
		if self.has_value_changed("member_directory"):
			sync_directory_menu_item()
		if self.has_value_changed("look_up_addresses") and self.look_up_addresses:
			geocoding.queue_missing()
		self.set_reminders()

	def set_share_defaults(self):
		"""Make what a new Person shares in the member directory follow these settings, with Property Setters.

		A default fills new records only, so the people already on file keep their own choice.
		"""
		meta = frappe.get_meta("Person")
		for fieldname, setting in SHARE_DEFAULTS.items():
			default = str(cint(self.get(setting)))
			if meta.get_field(fieldname).default != default:
				make_property_setter(
					"Person", fieldname, "default", default, "Text", validate_fields_for_doctype=False
				)

	def set_reminders(self):
		"""Make each reminder Notification on or off, with its days, as these settings say.

		So a Church Manager needs no Notification rights. These settings own both values: a change made in
		the Notification itself goes back on the next save here. A standard one that the patch did not replace
		yet stays as it is: saving it in developer mode would write it back into the app.
		"""
		for name, (switch, days) in REMINDERS.items():
			if not frappe.db.exists("Notification", {"name": name, "is_standard": 0}):
				continue
			reminder = frappe.get_doc("Notification", name)
			wanted = {"enabled": cint(self.get(switch)), "days_in_advance": cint(self.get(days))}
			if any(reminder.get(field) != value for field, value in wanted.items()):
				reminder.update(wanted)
				reminder.save(ignore_permissions=True)


def store_defaults() -> None:
	"""Save People Settings once on a site that never saved it, so a reader gets its defaults rather than nothing."""
	if not frappe.db.get_singles_dict("People Settings"):
		frappe.get_single("People Settings").save(ignore_permissions=True)


def create_reminders() -> None:
	"""Insert the reminder Notifications once, turned off, as Frappe installs its own notification templates.

	They are not standard, because production cannot turn on a standard one, and a church may change them.
	"""
	create_notifications(get_notification_templates(str(Path(__file__).parent / "reminders")))


def sync_directory_menu_item() -> None:
	"""Show the Member Directory in the portal menu only while People Settings turns the page on."""
	enabled = cint(frappe.db.get_single_value("People Settings", "member_directory"))
	portal = frappe.get_single("Portal Settings")
	rows = [row for row in portal.get_all_menu_items() if (row.route or "").strip("/") == DIRECTORY_ROUTE]
	if any(row.enabled != enabled for row in rows):
		for row in rows:
			row.enabled = enabled
		portal.save(ignore_permissions=True)
