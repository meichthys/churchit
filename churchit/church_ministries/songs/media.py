# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Song Media for the team members who serve at a function with the song on its schedule.

Portal members have no Song read, so an assignment opens the media: the session person's own, not
declined, at a function that ended a week ago or less.
"""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import DECLINED
from churchit.church_scope import session_person

# How long after a function its team can still open the song files, to listen back.
DAYS_AFTER_FUNCTION = 7


def get_media_link(assignment: str, media: frappe._dict) -> frappe._dict:
	"""The label of a Song Media row and the link that opens it through *assignment*."""
	query = urlencode({"assignment": assignment, "media": media.name})
	return frappe._dict(
		label=media.label or _(media.media_type),
		url=f"/api/method/churchit.church_ministries.songs.media.get_team_song_file?{query}",
	)


@frappe.whitelist(methods=["GET"])
def get_team_song_file(assignment: str, media: str):
	"""Send the Song Media file, or redirect to its link, to the team member *assignment* belongs to."""
	row = frappe.db.get_value("Song Media", media, ["parent", "parenttype", "file", "url"], as_dict=True)
	if not row or row.parenttype != "Song" or not is_serving_with_song(assignment, row.parent):
		frappe.throw(_("You cannot open this song file."), frappe.PermissionError)

	if row.file:
		# Only a file attached to the song, so a media row cannot hand out another record's file.
		file = frappe.get_doc(
			"File", {"file_url": row.file, "attached_to_doctype": "Song", "attached_to_name": row.parent}
		)
		frappe.local.response.filename = file.file_name
		frappe.local.response.filecontent = file.get_content()
		frappe.local.response.type = "download"
	elif row.url:
		frappe.local.response.type = "redirect"
		frappe.local.response.location = row.url
	else:
		raise frappe.DoesNotExistError(_("This song file has no file or link."))


def is_serving_with_song(assignment: str, song: str) -> bool:
	"""Whether *assignment* is the session person's, not declined, at a recent function with *song*."""
	person = session_person()
	values = frappe.db.get_value(
		"Ministry Team Assignment", assignment, ["person", "status", "function"], as_dict=True
	)
	if not person or not values or values.person != person or values.status == DECLINED:
		return False

	start_date, end_date = frappe.db.get_value("Function", values.function, ["start_date", "end_date"])
	if getdate(end_date or start_date) < getdate(add_days(nowdate(), -DAYS_AFTER_FUNCTION)):
		return False
	return bool(
		frappe.db.exists(
			"Function Schedule",
			{"parenttype": "Function", "parent": values.function, "item_type": "Song", "item": song},
		)
	)
