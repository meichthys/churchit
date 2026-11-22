# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member directory in the member app."""

import frappe
from frappe.utils import cint

from churchit.church_scope import session_church
from churchit.portal.access import require_page, require_person
from churchit.www.directory import get_entries, is_directory_member


@frappe.whitelist(methods=["GET"])
def get_directory() -> dict:
	"""The households of the member's church, with only the details each person shares. Reads only.

	`status` is "not_member" when the viewer is not a directory member, and then there are no entries.
	"""
	person = require_person()
	require_page("directory")
	if not cint(frappe.db.get_single_value("People Settings", "member_directory")):
		raise frappe.DoesNotExistError

	if not is_directory_member(person):
		return {"status": "not_member", "entries": []}

	entries = [
		{
			"name": str(index),
			"title": entry.title,
			"photo": entry.photo,
			"emails": entry.emails,
			"phones": entry.phones,
			"addresses": entry.addresses,
			"birthdays": entry.birthdays,
			"vcard": entry.vcard,
			"search": entry.search,
		}
		for index, entry in enumerate(get_entries(session_church()))
	]
	return {"status": "ok", "entries": entries}
