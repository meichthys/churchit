# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Roles that may clear a booking on a room whose "Requires Approval" flag is set.
APPROVER_ROLES = {"Church Manager", "System Manager"}


class RoomBooking(Document):
	def validate(self):
		if self.end_datetime and self.start_datetime and self.end_datetime <= self.start_datetime:
			frappe.throw("End time must be after start time.")
		requires_approval = bool(frappe.db.get_value("Room", self.room, "requires_approval"))
		self.set_initial_status(requires_approval)
		self.validate_approver(requires_approval)
		self.check_conflicts()

	def set_initial_status(self, requires_approval):
		"""Approve bookings outright on rooms that need no manager's OK.

		This keeps "Requested" meaning exactly one thing: waiting on a manager.
		A booking deliberately created as Denied or Cancelled is left alone.
		"""
		if requires_approval or not self.is_new():
			return
		if self.status in (None, "", "Requested"):
			self.status = "Approved"

	def validate_approver(self, requires_approval):
		"""Let only a manager move a booking to Approved on an approval-gated room.

		Church Users hold write access to their own bookings, so without this a
		requester could approve the very booking they submitted.
		"""
		if not requires_approval or self.status != "Approved":
			return
		before = self.get_doc_before_save()
		if before and before.status == "Approved":
			return
		if not APPROVER_ROLES & set(frappe.get_roles()):
			frappe.throw("Only a Church Manager can approve a booking for this room.")

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
