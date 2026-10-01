# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_foundations.doctype.church.church import ADDRESS_FIELDS
from churchit.church_scope import is_multi_church

no_cache = 1
sitemap = 1


def get_context(context):
	"""Every published church, for the public Locations page; only exists once branches are on."""
	if not is_multi_church():
		raise frappe.PageDoesNotExistError
	context.no_cache = 1
	context.title = _("Locations")
	context.churches = get_published_churches()


def get_published_churches():
	churches = frappe.get_all(
		"Church",
		filters={"publish": 1},
		fields=["name", "church_name", "founding_date", "mission_statement", "about", "image", "address"],
		order_by="lft asc",
	)
	for church in churches:
		church.address_fields = (
			frappe.db.get_value("Address", church.address, ADDRESS_FIELDS, as_dict=True)
			if church.address
			else None
		)
	return churches
