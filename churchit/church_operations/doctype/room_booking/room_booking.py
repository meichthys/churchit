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
		Booking = frappe.qb.DocType("Room Booking")
		conflicts = (
			frappe.qb.from_(Booking)
			.select(Booking.name)
			.where(
				(Booking.room == self.room)
				& (Booking.name != (self.name or ""))
				& Booking.status.isin(["Requested", "Approved"])
				& (Booking.start_datetime < self.end_datetime)
				& (Booking.end_datetime > self.start_datetime)
			)
			.run()
		)
		if conflicts:
			frappe.throw(f"Room is already booked at that time (conflicts with: {', '.join(c[0] for c in conflicts)}).")
