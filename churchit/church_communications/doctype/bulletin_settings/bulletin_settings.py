# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

# What a per-church row replaces. `roles` is absent because Frappe has no child
# table inside a child table. It costs little: `roles` lists which job titles the
# leadership section prints, and `sections.position_holders` reads who holds them
# from the bulletin's own church, so each branch already prints its own pastor.
SECTION_SETTINGS = (
	"show_contact_information",
	"show_order_of_worship",
	"show_church_roles",
	"show_upcoming_functions",
	"show_ministries",
	"show_church_verse",
	"show_church_image",
	"show_missionary",
	"show_prayer_requests",
	"show_birthdays",
	"show_anniversaries",
	"show_sermon_handout",
	"upcoming_functions_days",
	"include_sensitive_missionaries",
	"birthday_scope",
	"anniversary_scope",
	"celebration_days",
)


class BulletinSettings(Document):
	def for_church(self, church=None):
		"""These settings with *church*'s row applied, or unchanged when it has none.

		A row replaces the whole set rather than filling gaps in it: an unticked
		box and an unset box are the same value, so a row cannot say "inherit this
		one". Its fields ship with the same defaults as the settings above, so a
		new row starts where the site does.

		Resolved into a copy, never onto the cached Single, which every bulletin
		on the site would otherwise read.
		"""
		row = next((row for row in self.church_sections if row.church == church), None) if church else None
		if not row:
			return self

		settings = frappe.get_doc({"doctype": self.doctype, **self.as_dict()})
		settings.update({field: row.get(field) for field in SECTION_SETTINGS})
		return settings
