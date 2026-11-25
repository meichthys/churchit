# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who may use the member app, and which of its pages are on for them."""

import frappe
from frappe import _

from churchit.church_scope import session_person
from churchit.church_website.pages import get_hidden_pages, is_page_off


def require_person() -> str:
	"""The signed-in user's Person. Raises PermissionError for a guest or a login with no Person."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please sign in to use the member portal."), frappe.PermissionError)

	person = session_person()
	if not person:
		frappe.throw(
			_("Your login is not linked to anyone in the church directory. Please ask the church office."),
			frappe.PermissionError,
		)
	return person


def require_page(page: str) -> None:
	"""Refuse when *page* (its old route, such as "household") is switched off or hidden for this member."""
	if is_page_off(page, get_hidden_pages()):
		frappe.throw(_("This part of the member portal is turned off."), frappe.PermissionError)
