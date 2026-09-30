# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.www.about import get_context as frappe_context

from churchit.church_foundations.doctype.church.church import get_church

sitemap = 1


def get_context(context):
	"""Frappe's About Us page, telling the selected church's own story where it has one.

	About Us Settings is one record for the whole site, so every branch used to
	show the main church's introduction. The Church's own About and Mission
	Statement come first, which is what its field description promises; the
	history and team on the Single are shared by every church.
	"""
	context = frappe_context(context)
	church = get_church()
	if church and (church.about or church.mission_statement):
		context.church_introduction = church.about
		context.church_mission_statement = church.mission_statement
	return context
