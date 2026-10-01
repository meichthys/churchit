# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Notification subclass that keeps role-based recipients inside the document's church."""

import frappe
from frappe.email.doctype.notification.notification import Notification

from churchit.church_scope import allowed_churches, document_church, is_multi_church


class ScopedNotification(Notification):
	def get_list_of_recipients(self, doc, context):
		recipients, cc, bcc = super().get_list_of_recipients(doc, context)
		return drop_out_of_scope(recipients, doc, "email"), cc, bcc

	def get_receiver_list(self, doc, context, field_on_user="mobile_no", recipient_extractor_func=None):
		receivers = super().get_receiver_list(doc, context, field_on_user, recipient_extractor_func)
		return drop_out_of_scope(receivers, doc, field_on_user)


def drop_out_of_scope(values, doc, field):
	"""Remove users whose Church permission excludes the document's church.

	Values that belong to no user (a member's address) and users with no Church
	permission are kept. Role recipients are resolved with ignore_permissions in
	Frappe, so this is the only place the church boundary is applied to them.
	"""
	if not is_multi_church():
		return values
	church = document_church(doc)
	if not church:
		return values
	users = users_by_field(values, field)
	return [value for value in values if church_allows(users.get(value), church)]


def users_by_field(values, field):
	rows = frappe.get_all("User", filters={field: ("in", values), "enabled": 1}, fields=["name", field])
	return {row.get(field): row.name for row in rows}


def church_allows(user, church):
	if not user:
		return True
	allowed = allowed_churches(user)
	return allowed is None or church in allowed
