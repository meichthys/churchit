# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re

import frappe
from frappe import _
from frappe.model.document import Document

# Set by a Death life event and by a confirmed Member Transfer out.
DECEASED = "Deceased"
TRANSFERRED = "Transferred to another church"
SET_AUTOMATICALLY = (DECEASED, TRANSFERRED)


class InactiveReason(Document):
	"""Why a person is no longer active. The reasons the app sets cannot be deleted or renamed."""

	def on_trash(self):
		if self.name in SET_AUTOMATICALLY:
			frappe.throw(
				_("{0} is set automatically, so it cannot be deleted.").format(frappe.bold(self.name))
			)

	def before_rename(self, old, new, merge=False):
		if old in SET_AUTOMATICALLY:
			frappe.throw(_("{0} is set automatically, so it cannot be renamed.").format(frappe.bold(old)))


def create_inactive_reasons():
	"""Make the reasons the app sets, and one for each reason already typed on a Person, so every stored value links.

	A typed reason becomes a name Frappe accepts first (`get_valid_reason`), on the Person too.
	"""
	Person = frappe.qb.DocType("Person")
	# church-scope: every church's stored reasons become the one site-wide list of reasons
	stored = (
		frappe.qb.from_(Person)
		.select(Person.inactive_reason)
		.distinct()
		.where(Person.inactive_reason.isnotnull())
		.orderby(Person.inactive_reason)
		.run(pluck=True)
	)
	for value in (*SET_AUTOMATICALLY, *stored):
		reason = get_valid_reason(value)
		if reason != value or not reason:
			# The database ignores trailing spaces here, so an empty value stands for values of spaces too.
			frappe.qb.update(Person).set(Person.inactive_reason, reason or None).where(
				Person.inactive_reason == value
			).run()
		if reason and not frappe.db.exists("Inactive Reason", reason):
			frappe.get_doc({"doctype": "Inactive Reason", "reason": reason}).insert(ignore_permissions=True)


def get_valid_reason(text: str) -> str:
	"""*text* as an Inactive Reason name: without the < and > Frappe refuses, and with single spaces."""
	return " ".join(re.sub("[<>]", " ", text).split())
