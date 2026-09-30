# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the website footer says about the church."""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import getdate

from churchit.church_foundations.doctype.church.church import (
	address_line,
	church_contact_details,
	get_church,
	get_church_address,
)


def get_footer_church():
	"""The church's name, one-line address, map link, phone and founding year for the footer, or None before setup."""
	church = get_church()
	if not church:
		return None
	address = address_line(get_church_address())
	return frappe._dict(
		name=church.church_name,
		address=address,
		map_url=map_url(address),
		phone=church_contact_details(church).phone,
		established=_("Established {0}").format(getdate(church.founding_date).year)
		if church.founding_date
		else None,
	)


def map_url(address):
	"""An OpenStreetMap search for the address, or None without one."""
	if not address:
		return None
	return "https://www.openstreetmap.org/search?" + urlencode({"query": address})
