# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RoomBooking(Document):
	def validate(self):
		if self.end_datetime and self.start_datetime and self.end_datetime <= self.start_datetime:
			frappe.throw("End time must be after start time.")
		self.check_conflicts()

	def check_conflicts(self):
		if self.status in ("Denied", "Cancelled"):
			return
		conflicts = frappe.db.sql(
			"""
			SELECT name FROM `tabRoom Booking`
			WHERE room = %s
				AND name != %s
				AND status IN ('Requested', 'Approved')
				AND start_datetime < %s
				AND end_datetime > %s
			""",
			(self.room, self.name or "", self.end_datetime, self.start_datetime),
		)
		if conflicts:
			frappe.throw(f"Room is already booked at that time (conflicts with: {', '.join(c[0] for c in conflicts)}).")
