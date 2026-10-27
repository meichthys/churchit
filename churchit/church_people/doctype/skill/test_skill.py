# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.doctype.skill.skill import SPIRITUAL_GIFT, STARTER_GIFTS
from churchit.patches.after_install import execute as after_install
from churchit.patches.v1_0 import add_spiritual_gifts
from churchit.tests.helpers import RollbackEachTest

GIFTS = [skill_name for skill_name, _description in STARTER_GIFTS]


class TestStarterGifts(RollbackEachTest):
	def test_a_migrated_site_gets_the_gifts_once_and_keeps_a_churchs_edits(self):
		frappe.db.delete("Skill", {"name": ("in", GIFTS)})
		add_spiritual_gifts.execute()
		frappe.db.set_value("Skill", "Teaching", "description", "_Test Our own words")

		add_spiritual_gifts.execute()

		self.assertEqual(
			frappe.db.count("Skill", {"name": ("in", GIFTS), "category": SPIRITUAL_GIFT}), len(GIFTS)
		)
		self.assertEqual(frappe.db.get_value("Skill", "Teaching", "description"), "_Test Our own words")

	def test_a_new_site_gets_the_gifts(self):
		frappe.db.delete("Skill", {"name": ("in", GIFTS)})

		after_install()

		self.assertEqual(frappe.db.count("Skill", {"name": ("in", GIFTS)}), len(GIFTS))
