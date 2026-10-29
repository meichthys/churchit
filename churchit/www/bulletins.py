# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _

from churchit.church_communications.doctype.bulletin.sections import BulletinSections
from churchit.church_scope import church_query_filters

no_cache = 1


def get_context(context):
	name = frappe.form_dict.get("name")
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?" + urlencode(
			{"redirect-to": "/bulletins?" + urlencode({"name": name}) if name else "/bulletins"}, safe="/"
		)
		raise frappe.Redirect

	context.no_cache = 1
	context.title = _("Bulletins")
	if name:
		context.doc = get_digital_bulletin(name)
		return
	context.show_sidebar = 1
	context.bulletins = get_published_bulletins()


def get_published_bulletins():
	"""Published bulletins of the churches the member reads, newest function first.

	The member's own scope decides, not ``?church=``, so another church's bulletins never list.
	"""
	return frappe.get_all(
		"Bulletin",
		filters={"publish": 1, **church_query_filters({})},
		fields=["name", "function_name", "function_date"],
		order_by="function_date desc",
	)


def get_digital_bulletin(name):
	"""The bulletin *name* to read in the browser, when the member may read it."""
	if not frappe.db.exists("Bulletin", name):
		raise frappe.PageDoesNotExistError
	doc: BulletinSections = frappe.get_doc("Bulletin", name)
	if not frappe.has_website_permission(doc):
		raise frappe.PageDoesNotExistError
	return doc
