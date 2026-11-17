# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The church that install makes carries no text that the church did not write."""

import frappe

from churchit.patches.v1_0 import clear_install_text_from_default_church as patch
from churchit.tests.helpers import RollbackEachTest, ensure_root_church


class TestDefaultChurchText(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()

	def set_text(self, about, legal_name):
		frappe.db.set_value("Church", self.root, {"about": about, "legal_name": legal_name})

	def text(self):
		return frappe.db.get_value("Church", self.root, ["about", "legal_name"])

	def test_the_patch_clears_the_install_text_and_can_run_again(self):
		self.set_text(patch.INSTALL_ABOUT, patch.INSTALL_LEGAL_NAME)

		patch.execute()
		patch.execute()

		self.assertEqual(self.text(), (None, None))

	def test_the_patch_keeps_a_churchs_own_text(self):
		self.set_text("<p>_Test our own story.</p>", "_Test Grace Fellowship Inc.")

		patch.execute()

		self.assertEqual(self.text(), ("<p>_Test our own story.</p>", "_Test Grace Fellowship Inc."))
