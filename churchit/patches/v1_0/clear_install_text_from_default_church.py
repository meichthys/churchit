# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Clear the About and Legal Name that install gave the default church, where the church never changed them.

The About named "My Church" and a founding year that no church gave, and both stayed on the public home and
/about after a church renamed itself. A church's own text stays.
"""

import frappe

INSTALL_ABOUT = (
	"<p>Welcome to My Church. We are a community of believers committed to worship, fellowship, and service. "
	"We are a congregation rooted in Scripture and passionate about sharing the grace of God with all people.</p>"
	"<p>Founded in 1990, we have grown from a small gathering into a vibrant church family. Whether you are a "
	"lifelong believer or simply curious about faith, you are welcome here.</p>"
)
INSTALL_LEGAL_NAME = "My Church"


def execute():
	root = {"parent_church": ("is", "not set")}
	frappe.db.set_value("Church", {**root, "about": INSTALL_ABOUT}, "about", None, update_modified=False)
	frappe.db.set_value(
		"Church", {**root, "legal_name": INSTALL_LEGAL_NAME}, "legal_name", None, update_modified=False
	)
