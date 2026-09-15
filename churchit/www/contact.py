# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.www import contact

from churchit.church_foundations.doctype.church.church import ADDRESS_FIELDS, get_church_address

sitemap = 1


def get_context(context):
	"""Frappe's contact page, showing the Church record's address unless the settings say it differs."""
	out = contact.get_context(context)
	if not out.get("contact_address_differs"):
		out.update({field: None for field in ADDRESS_FIELDS})
		out.update(get_church_address() or {})
	return out
