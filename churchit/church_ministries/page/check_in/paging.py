# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Paging a child's parents from the Check-In Station.

A page is a fixed message to the Adults of the child's household that no Pickup Restriction names,
sent with the Child Safety purpose, so it honors their consent like any other message. An Adult who allows texts gets a text when the site
sends texts and the user may send them (SMS Settings Allowed Roles). Every other Adult gets an email.
"""

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import check_sms_permission
from frappe.model.document import Document
from frappe.utils import now_datetime
from requests import RequestException

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL, SMS
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHILD_SAFETY
from churchit.church_communications.sending import can_send_texts, send
from churchit.church_ministries.doctype.check_in_settings.check_in_settings import name_gone_by
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_ministries.page.check_in.check_in import get_restrictions
from churchit.church_people import household

PAGE_KEY = "churchit_page_parents:{}"
PAGE_INTERVAL_SECONDS = 120


@frappe.whitelist(methods=["POST"])
def page_parents(check_in: str) -> list[str]:
	"""Ask the household Adults of *check_in*'s child to come, and return the full names of those reached."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	doc = frappe.get_doc("Function Check-In", check_in)
	doc.check_permission("read")

	# The row lock makes a second volunteer's page wait here, then find the first one's key.
	if frappe.db.get_value("Function Check-In", check_in, "collected_at", for_update=True):
		frappe.throw(_("This child has been collected, so their parents cannot be paged."))
	if frappe.cache.get_value(PAGE_KEY.format(check_in)):
		frappe.throw(_("This child's parents were paged less than 2 minutes ago."))
	frappe.cache.set_value(PAGE_KEY.format(check_in), 1, expires_in_sec=PAGE_INTERVAL_SECONDS)
	# A text gateway can hang, and every code draw locks the day's coded check-ins, so the row is freed
	# here and the copies are about the child: `send` locks its source until the commit.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit

	child = frappe.get_doc("Person", doc.person)
	adults = household.members(child.family, [household.ADULT]) if child.family else []
	restricted = {row.restricted_person for row in get_restrictions([child.name])}
	adults = [adult for adult in adults if adult not in restricted]
	key = f"page-{check_in}-{now_datetime():%Y%m%d%H%M%S}"
	context = {
		"child": name_gone_by(child.name),
		"function": frappe.db.get_value("Function", doc.function, "function_name"),
	}
	reached = text_adults(adults, child, f"{key}-sms", context) if can_text() else set()
	if can_send_email():
		reached |= send(
			[adult for adult in adults if adult not in reached],
			EMAIL,
			CHILD_SAFETY,
			child,
			key=f"{key}-email",
			subject=_("Please come to {{ function }}"),
			message=_("<p>{{ child }} needs you at {{ function }}. Please come now.</p>"),
			context=context,
		)

	if not reached:
		# A page that reached no one does not block a second try, for example once the gateway works again.
		frappe.cache.delete_value(PAGE_KEY.format(check_in))
		return []
	# church-scope: the household Adults of a check-in the caller may read
	names = dict(
		frappe.get_all(
			"Person", filters={"name": ("in", list(reached))}, fields=["name", "full_name"], as_list=True
		)
	)
	return [names[adult] for adult in adults if adult in reached]


def text_adults(adults: list[str], child: Document, key: str, context: dict) -> set[str]:
	"""Text the page to each of *adults* and return those reached. A gateway failure stops the texts."""
	reached = set()
	text = _("Please come to {{ function }}. {{ child }} needs you.")
	for adult in adults:
		frappe.db.savepoint("page_text")
		try:
			reached |= send([adult], SMS, CHILD_SAFETY, child, key=key, text=text, context=context)
		except RequestException:
			# Undo the copy of the text that did not leave; the Adults not reached get an email.
			frappe.db.rollback(save_point="page_text")
			frappe.log_error(
				title=f"Could not text a page for {child.name}",
				reference_doctype=child.doctype,
				reference_name=child.name,
			)
			break
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (a text has left, so its copy must outlive a later error)
	return reached


def can_text() -> bool:
	"""True when the site sends texts and the user passes SMS Settings Allowed Roles."""
	if not can_send_texts():
		return False
	try:
		check_sms_permission()
	except frappe.PermissionError:
		frappe.clear_last_message()
		return False
	return True
