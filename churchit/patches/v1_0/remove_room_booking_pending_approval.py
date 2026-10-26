# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the shipped Room Booking Pending Approval Notification: approvers now get a ToDo for each request."""

import frappe


def execute():
	frappe.delete_doc_if_exists("Notification", "Room Booking Pending Approval")
