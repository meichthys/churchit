# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.boot import get_module_sidebars
from frappe.tests.utils import FrappeTestCase

from churchit.church_communications.staff_chat import STAFF_CHAT_ROUTE, extend_bootinfo

RAVEN_TILE = {"name": "raven", "title": "Raven", "route": STAFF_CHAT_ROUTE}
CHURCHIT_TILE = {"name": "churchit", "title": "Churchit", "route": "/desk/summary"}


class TestStaffChat(FrappeTestCase):
	def staff_chat_urls(self, app_data):
		bootinfo = frappe._dict(module_sidebars=get_module_sidebars(), app_data=app_data)
		extend_bootinfo(bootinfo)
		items = bootinfo.module_sidebars["Communications"]["items"]
		return [item["url"] for item in items if item["url"] == STAFF_CHAT_ROUTE]

	def test_the_link_shows_when_the_apps_screen_offers_raven(self):
		self.assertEqual(self.staff_chat_urls([CHURCHIT_TILE, RAVEN_TILE]), [STAFF_CHAT_ROUTE])

	def test_the_link_goes_without_raven(self):
		self.assertEqual(self.staff_chat_urls([CHURCHIT_TILE]), [])
