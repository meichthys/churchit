# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's menu: the Portal Settings menu in sections, each link with an icon and a line.

The site admin owns the menu (Desk > Portal Settings). A row this module does not know, such as one
the admin added, goes to the last section, More, in menu order.
"""

import frappe
from frappe import _


def get_sections() -> tuple[tuple[str, dict[str, tuple[str, str]]], ...]:
	"""The menu sections in order, each a title and its links as route: (icon, line).

	The week's church life comes first and the member's own household last.
	"""
	return (
		(
			_("Church Life"),
			{
				"function-sign-up": ("calendar-check", _("Tell us you plan to come to a function.")),
				"attendance": ("clipboard-check", _("See the functions you signed up for and attended.")),
				"ministry-team": ("handshake", _("See when you are asked to serve, and reply.")),
				"groups": ("users-round", _("See the groups you belong to.")),
				"group-leader": ("user-round-cog", _("Record meetings and message the groups you lead.")),
				"group-files": ("folder", _("Open the files shared in your groups.")),
				"directory": ("contact", _("Find the contact details of other members.")),
				"room-request": ("door-open", _("Ask to use a room of the church.")),
			},
		),
		(
			_("Prayer and Care"),
			{
				"community-prayer-requests": ("hand-heart", _("Pray for the needs that others share.")),
				"prayer-request": ("heart", _("Share a prayer request with the church.")),
				"care-request": ("hand-helping", _("Ask for a visit, a meal or other help.")),
				"alms-request": ("gift", _("Ask the church for help with a financial need.")),
			},
		),
		(
			_("Bible and Bulletins"),
			{
				"memorize": ("bookmark", _("Learn Bible passages by heart.")),
				"bible": ("book-open", _("Read the Bible.")),
				"bulletins": ("newspaper", _("Read the church bulletins.")),
			},
		),
		(
			_("Giving"),
			{
				"pledge": ("sprout", _("Pledge to a campaign and see your progress.")),
				"statements": ("receipt", _("See and print your giving statements.")),
			},
		),
		(
			_("You and Your Household"),
			{
				"household": ("users", _("See your household and check in before you arrive.")),
				"personal-details": ("id-card", _("Check and update your contact details.")),
				"preferences": ("mail-check", _("Choose how the church may contact you.")),
			},
		),
	)


def get_portal_home_sections(items: list[dict]) -> list[frappe._dict]:
	"""*items* of the portal menu grouped into the menu sections. Leaves out empty sections."""
	by_route = {(item.get("route") or "").strip("/"): item for item in items}
	sections = []
	for title, links in get_sections():
		rows = [
			frappe._dict(by_route.pop(route), icon=icon, description=description)
			for route, (icon, description) in links.items()
			if route in by_route
		]
		sections.append(frappe._dict(title=title, links=rows))

	more = [frappe._dict(item, icon="link", description="") for item in by_route.values()]
	sections.append(frappe._dict(title=_("More"), links=more))
	return [section for section in sections if section.links]
