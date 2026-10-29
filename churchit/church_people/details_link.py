# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A link a person follows to check their own details, with no login.

The link is a Frappe Web Form Request for the key-only Update Your Details form,
bound to one Person. It works once, for `LINK_DAYS` days.
"""

import frappe
from frappe import _
from frappe.utils import add_days, escape_html, get_url, now_datetime
from frappe.website.doctype.web_form_request.web_form_request import get_web_form_request_query

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.contacts import primary_email

DETAILS_FORM = "update-your-details"
LINK_DAYS = 7


@frappe.whitelist(methods=["POST"])
def send_details_link(person: str) -> str:
	"""Email *person* a link to the Update Your Details form, and return the address it went to."""
	doc = frappe.get_doc("Person", person)
	doc.check_permission("write")
	email = primary_email(doc)
	if not email:
		frappe.throw(_("Add an email address on the Contact tab before you send a details link."))
	if not can_send_email():
		frappe.throw(_("Set up an outgoing Email Account first."))

	request = make_details_request(doc.name)
	frappe.sendmail(
		recipients=[email],
		subject=_("Please check your details"),
		message=get_message(doc, get_details_url(request)),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)
	doc.add_comment("Info", _("Sent a link to update their details to {0}.").format(email))
	return email


def make_details_request(person: str):
	"""A Web Form Request that opens Update Your Details on *person* until it expires or is used."""
	request = frappe.get_doc(
		{
			"doctype": "Web Form Request",
			"web_form": DETAILS_FORM,
			"expires_on": add_days(now_datetime(), LINK_DAYS),
			"references": [{"link_doctype": "Person", "link_name": person}],
		}
	)
	# Only Website Manager may make one; the caller's right to change the person was checked.
	return request.insert(ignore_permissions=True)


def get_details_url(request) -> str:
	return get_url(
		f"/{DETAILS_FORM}/{request.references[0].link_name}/edit{get_web_form_request_query(request.key)}"
	)


def get_message(person, url: str) -> str:
	name = escape_html(person.nickname or person.first_name)
	return _(
		"Hello {0},<br><br>Please check the details the church keeps about you, and change anything "
		'that is out of date:<br><br><a href="{1}">Update Your Details</a><br><br>'
		"The link works once, for {2} days. If you did not expect this email, you can ignore it."
	).format(name, url, LINK_DAYS)


def close_details_request(request, method=None):
	"""validate on Web Form Request: a details link changes its one person, once.

	Frappe lets a key add new records as well, and reopen its record until it
	expires. A save as the key holder appends a second reference for a new
	record, so that is refused, and the first use expires the link.
	"""
	if request.web_form != DETAILS_FORM:
		return
	if len(request.references) != 1:
		frappe.throw(_("A details link changes only the person it was sent to."), frappe.PermissionError)
	if request.first_used_on:
		request.expires_on = request.first_used_on
