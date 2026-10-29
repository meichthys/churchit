# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.document import Document
from frappe.utils import cint

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


class PeopleSettings(Document):
	def on_update(self):
		if self.has_value_changed("adult_age") or self.has_value_changed("school_year_start_month"):
			frappe.enqueue(refresh_daily, enqueue_after_commit=True)
		self.set_share_defaults()
		if self.has_value_changed("member_directory"):
			sync_directory_menu_item()
		if self.has_value_changed("look_up_addresses") and self.look_up_addresses:
			geocoding.queue_missing()

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


def store_defaults() -> None:
	"""Save People Settings once on a site that never saved it, so a reader gets its defaults rather than nothing."""
	if not frappe.db.get_singles_dict("People Settings"):
		frappe.get_single("People Settings").save(ignore_permissions=True)


def sync_directory_menu_item() -> None:
	"""Show the Member Directory in the portal menu only while People Settings turns the page on."""
	enabled = cint(frappe.db.get_single_value("People Settings", "member_directory"))
	portal = frappe.get_single("Portal Settings")
	rows = [row for row in portal.get_all_menu_items() if (row.route or "").strip("/") == DIRECTORY_ROUTE]
	if any(row.enabled != enabled for row in rows):
		for row in rows:
			row.enabled = enabled
		portal.save(ignore_permissions=True)
