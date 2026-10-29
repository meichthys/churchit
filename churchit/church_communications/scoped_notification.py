# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Notification subclass that keeps role recipients inside the document's church and members to their consent."""

import frappe
from frappe.email.doctype.notification.notification import Notification

from churchit.church_communications.consent import refused_values
from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL, SMS
from churchit.church_scope import document_church, has_church_access, is_multi_church


class ScopedNotification(Notification):
	def get_list_of_recipients(self, doc, context):
		recipients, cc, bcc = super().get_list_of_recipients(doc, context)
		recipients = drop_out_of_scope(recipients, doc, "email")
		return tuple(drop_refused(values, "email", EMAIL) for values in (recipients, cc, bcc))

	def get_receiver_list(self, doc, context, field_on_user="mobile_no", recipient_extractor_func=None):
		receivers = super().get_receiver_list(doc, context, field_on_user, recipient_extractor_func)
		return drop_refused(drop_out_of_scope(receivers, doc, field_on_user), field_on_user, SMS)


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
	return [value for value in values if value not in users or has_church_access(users[value].name, church)]


def drop_refused(values, field, channel):
	"""Remove addresses or numbers that no one holding them lets the church use on *channel*.

	A Notification has no purpose, so only consent for every purpose counts. Staff
	logins are kept: what they receive is their work, not the church contacting them.
	"""
	if not values:
		return values
	staff = {
		value for value, user in users_by_field(values, field).items() if user.user_type == "System User"
	}
	refused = refused_values([value for value in values if value not in staff], channel)
	return [value for value in values if value not in refused]


def users_by_field(values, field):
	if not values:
		return {}
	rows = frappe.get_all(
		"User", filters={field: ("in", values), "enabled": 1}, fields=["name", "user_type", field]
	)
	return {row.get(field): row for row in rows}
