# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

SPIRITUAL_GIFT = "Spiritual Gift"
# The starting spiritual gifts, from Romans 12, 1 Corinthians 12, Ephesians 4 and 1 Peter 4.
STARTER_GIFTS = (
	("Administration", "Organizes people and plans so that the work gets done (1 Corinthians 12:28)."),
	("Encouragement", "Strengthens and urges others on in their faith (Romans 12:8)."),
	("Evangelism", "Tells the gospel so that others come to faith (Ephesians 4:11)."),
	("Faith", "Trusts God for great things and helps others trust Him (1 Corinthians 12:9)."),
	("Giving", "Gives money and goods generously for the Lord's work (Romans 12:8)."),
	("Hospitality", "Welcomes guests and strangers and makes them feel at home (1 Peter 4:9)."),
	("Leadership", "Gives direction to a group and cares for the people in it (Romans 12:8)."),
	("Mercy", "Cares with compassion for people who suffer (Romans 12:8)."),
	("Serving", "Meets practical needs so that others can do their work (Romans 12:7)."),
	("Shepherding", "Cares for and guides a group of believers over time (Ephesians 4:11)."),
	("Teaching", "Explains the Bible clearly so that others understand and obey it (Romans 12:7)."),
	("Wisdom", "Applies God's truth to real decisions and problems (1 Corinthians 12:8)."),
)


class Skill(Document):
	"""A skill, interest or spiritual gift that a person can have, shared by every church."""


def create_spiritual_gifts():
	"""Make the starting spiritual gifts the site does not have yet."""
	for skill_name, description in STARTER_GIFTS:
		if not frappe.db.exists("Skill", skill_name):
			frappe.get_doc(
				{
					"doctype": "Skill",
					"skill_name": skill_name,
					"category": SPIRITUAL_GIFT,
					"description": description,
				}
			).insert(ignore_permissions=True)
