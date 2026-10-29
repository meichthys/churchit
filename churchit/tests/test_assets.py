# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Frappe's bundle names that Churchit loads by name.

`www/calendar.html`, `public/js/church_utils.js` (the Map view), the MissionaryMap block and
`church_website/context.py` (/missions) ask for these bundles by name. A Frappe upgrade that renames
one breaks that page with no error on the server.
"""

from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_assets_json

FRAPPE_BUNDLES = ("calendar.bundle.js", "leaflet.bundle.js", "leaflet.bundle.css")


class TestFrappeBundles(FrappeTestCase):
	def test_frappe_builds_every_bundle_churchit_loads(self):
		assets = get_assets_json()
		self.assertEqual([name for name in FRAPPE_BUNDLES if name not in assets], [])
