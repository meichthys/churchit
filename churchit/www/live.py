# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_foundations.doctype.church.church import get_church, inherited_value
from churchit.church_study.media import get_embed_url

no_cache = 1
sitemap = 0


def get_context(context):
	"""The selected church's live stream in a player, or a redirect to a link that has no player.

	A branch without its own link uses its parent church's.
	"""
	frappe.local.no_cache = 1  # Frappe stores a 404 by URL; a link saved later must show
	church = get_church()
	url = church and (church.live_stream_url or inherited_value(church.name, "live_stream_url"))
	if not url:
		raise frappe.PageDoesNotExistError

	context.embed_url = get_embed_url(url)
	if not context.embed_url:
		frappe.local.flags.redirect_location = url
		raise frappe.Redirect(302)

	context.title = _("Watch Live")
	context.church_name = church.church_name
