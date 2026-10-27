# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

from churchit.church_scope import CHURCH_FIELD, has_church_access

EMAIL = "Email"
SMS = "SMS"
PUSH = "Push"
PHONE = "Phone"
POST = "Post"

GIVEN = "Given"
WITHDRAWN = "Withdrawn"

DESK = "Desk"
WEB_FORM = "Web Form"
MEMBER_PORTAL = "Member Portal"
UNSUBSCRIBE_LINK = "Unsubscribe Link"
EMAIL_LINK = "Email Link"

# How far ahead of the server's clock a Recorded On may be, for a desk whose clock runs fast.
CLOCK_SKEW_MINUTES = 5


class CommunicationConsent(Document):
	"""A person's yes or no to one channel. Its fields are set once; a change of mind is a new record."""

	def validate(self):
		self.refuse_another_churches_person()
		if self.is_new():
			self.refuse_a_future_date()

	@property
	def is_due_for_renewal(self) -> bool:
		"""The Consent Renewal notification's condition: this yes is one the person's church must renew."""
		from churchit.church_communications import consent  # consent imports this module

		return consent.is_due_for_renewal(self)

	def refuse_a_future_date(self):
		"""The newest record decides, so one dated ahead would outrank every answer given before that date."""
		if get_datetime(self.recorded_on) > add_to_date(now_datetime(), minutes=CLOCK_SKEW_MINUTES):
			frappe.throw(_("Recorded On cannot be in the future."))

	def refuse_another_churches_person(self):
		"""Only the person's own church records their consent.

		Frappe checks the create right before `church` is fetched from the person,
		so it never sees whose person this is. The person is set once, so this checks
		every save rather than a change of the link (`refuse_another_churches_parent`).
		Writes with ignore_permissions, such as an unsubscribe link, are the app's own
		and are not refused.
		"""
		if self.flags.ignore_permissions:
			return
		church = frappe.db.get_value("Person", self.person, CHURCH_FIELD)
		if not has_church_access(frappe.session.user, church):
			frappe.throw(
				_("{0} belongs to another church, so only that church can record their consent.").format(
					self.person_name or self.person
				),
				frappe.PermissionError,
			)


def record(
	people: list[str],
	channel: str,
	status: str,
	purpose: str | None = None,
	method: str = DESK,
	recorded_on=None,
) -> list[str]:
	"""Add a consent for each of *people* and return their names."""
	return [
		frappe.get_doc(
			{
				"doctype": "Communication Consent",
				"person": person,
				"channel": channel,
				"purpose": purpose,
				"status": status,
				"method": method,
				"recorded_on": recorded_on or now_datetime(),
			}
		)
		.insert(ignore_permissions=True)
		.name
		for person in people
	]
