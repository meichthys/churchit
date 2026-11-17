# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member portal home page: the Portal Settings menu in sections, each link with an icon and a line.

The site admin owns the menu (Desk > Portal Settings). A row this module does not know, such as one
the admin added, goes to the last section, More, in menu order.
"""

import frappe
from frappe import _


def get_sections() -> tuple[tuple[str, dict[str, tuple[str, str]]], ...]:
	"""The home page sections in order, each a title and its links as route: (icon, line)."""
	return (
		(
			_("You and Your Household"),
			{
				"personal-details": ("id-card", _("Check and update your contact details.")),
				"household": ("users", _("See your household and check in before you arrive.")),
				"preferences": ("mail-check", _("Choose how the church may contact you.")),
				"directory": ("contact", _("Find the contact details of other members.")),
			},
		),
		(
			_("Functions and Serving"),
			{
				"function-sign-up": ("calendar-check", _("Tell us you plan to come to a function.")),
				"attendance": ("clipboard-check", _("See the functions you signed up for and attended.")),
				"ministry-team": ("handshake", _("See when you are asked to serve, and reply.")),
				"room-request": ("door-open", _("Ask to use a room of the church.")),
			},
		),
		(
			_("Groups"),
			{
				"groups": ("users-round", _("See the groups you belong to.")),
				"group-leader": ("user-round-cog", _("Record meetings and message the groups you lead.")),
				"group-files": ("folder", _("Open the files shared in your groups.")),
			},
		),
		(
			_("Prayer and Care"),
			{
				"prayer-request": ("heart", _("Share a prayer request with the church.")),
				"community-prayer-requests": ("hand-heart", _("Pray for the needs that others share.")),
				"care-request": ("hand-helping", _("Ask for a visit, a meal or other help.")),
				"alms-request": ("gift", _("Ask the church for help with a financial need.")),
			},
		),
		(
			_("Giving"),
			{
				"statements": ("receipt", _("See and print your giving statements.")),
				"pledge": ("sprout", _("Pledge to a campaign and see your progress.")),
			},
		),
		(
			_("Bible and Bulletins"),
			{
				"bible": ("book-open", _("Read the Bible.")),
				"memorize": ("bookmark", _("Learn Bible passages by heart.")),
				"bulletins": ("newspaper", _("Read the church bulletins.")),
			},
		),
	)


def get_portal_home_sections(items: list[dict]) -> list[frappe._dict]:
	"""*items* of the portal menu grouped into the home page sections. Leaves out empty sections."""
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
