# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _

from churchit.church_communications.doctype.bulletin.sections import BulletinSections

no_cache = 1


def get_context(context):
	name = frappe.form_dict.get("name")
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?" + urlencode(
			{"redirect-to": "/bulletins?" + urlencode({"name": name}) if name else "/bulletins"}, safe="/"
		)
		raise frappe.Redirect

	if not name:
		raise frappe.PageDoesNotExistError

	context.no_cache = 1
	context.title = _("Bulletins")
	context.doc = get_digital_bulletin(name)


def get_digital_bulletin(name):
	"""The bulletin *name* to read in the browser, when the member may read it."""
	if not frappe.db.exists("Bulletin", name):
		raise frappe.PageDoesNotExistError
	doc: BulletinSections = frappe.get_doc("Bulletin", name)
	if not frappe.has_website_permission(doc):
		raise frappe.PageDoesNotExistError
	return doc
