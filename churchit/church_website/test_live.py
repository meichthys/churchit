# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re
from pathlib import Path
from unittest.mock import call, patch

import frappe

from churchit.church_ministries.attendance import save_attendance
from churchit.church_website import live
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, force_single_church, make_function

LIVE_REGION = re.compile(r'data-live="([^"]+)"')
LIVE_SCRIPT = re.compile(r"churchit\.live\.on\(\[([^\]]+)\]")


def doctypes_pages_listen_for() -> set[str]:
	"""The doctypes named by the live regions and live scripts of the www pages, the shipped Web Pages
	and the church's Web Template blocks."""
	app = Path(frappe.get_app_path("churchit"))
	folders = (
		app / "www",
		app / "patches" / "after_install" / "templates",
		app / "church_website" / "web_template",
	)
	doctypes = set()
	for folder in folders:
		for path in folder.rglob("*.html"):
			html = path.read_text()
			for listed in LIVE_REGION.findall(html):
				doctypes.update(doctype.strip() for doctype in listed.split(","))
			for listed in LIVE_SCRIPT.findall(html):
				doctypes.update(doctype.strip(" '\"") for doctype in listed.split(","))
	return doctypes


class TestLiveWebsite(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()

	def setUp(self):
		super().setUp()
		self.publish = self.enterContext(patch("churchit.church_website.live.frappe.publish_realtime"))

	def hints(self):
		"""The website hints sent; Frappe's own events (list updates, comments) also go through the mock."""
		return [sent for sent in self.publish.call_args_list if sent.args[:1] == (live.EVENT,)]

	def hinted_doctypes(self):
		return [sent.args[1]["doctype"] for sent in self.hints()]

	def make_sermon(self, publish):
		return frappe.get_doc({"doctype": "Sermon", "title": "_Test Live Sermon", "publish": publish}).insert(
			ignore_permissions=True
		)

	def test_a_published_record_hints_the_website_room_after_the_commit(self):
		self.make_sermon(publish=1)

		self.assertEqual(
			self.hints(), [call(live.EVENT, {"doctype": "Sermon"}, room="website", after_commit=True)]
		)

	def test_a_record_off_the_website_sends_no_hint(self):
		self.make_sermon(publish=0)
		self.assertEqual(self.hinted_doctypes(), [])

	def test_taking_a_record_off_the_website_hints_once_more(self):
		sermon = self.make_sermon(publish=1)
		self.publish.reset_mock()

		sermon.publish = 0
		sermon.save(ignore_permissions=True)
		self.assertEqual(self.hinted_doctypes(), ["Sermon"])

		self.publish.reset_mock()
		sermon.title = "_Test Live Sermon Draft"
		sermon.save(ignore_permissions=True)
		self.assertEqual(self.hinted_doctypes(), [], "a draft that stays off the website is nobody's news")

	def test_deleting_a_published_record_hints(self):
		sermon = self.make_sermon(publish=1)
		self.publish.reset_mock()

		sermon.delete(ignore_permissions=True)
		self.assertEqual(self.hinted_doctypes(), ["Sermon"])

	def test_a_bulletin_counts_only_while_it_shares_its_announcements(self):
		bulletin = frappe._dict(doctype="Bulletin", publish=1, share_announcements=1)
		self.assertTrue(live.is_shown(bulletin))
		self.assertFalse(live.is_shown(frappe._dict(bulletin, share_announcements=0)))

	def test_a_saved_attendance_sends_no_hint(self):
		function = make_function("_Test Live Gathering", start_date=frappe.utils.getdate(), publish=1)
		self.publish.reset_mock()

		save_attendance(frappe.get_doc("Function", function.name))
		self.assertEqual(self.hinted_doctypes(), [], "a check-in changes nothing a page shows")

	def test_a_page_listens_for_each_doctype_that_hints_and_no_other(self):
		hooked = {
			doctype
			for doctype, events in frappe.get_hooks("doc_events").items()
			if "churchit.church_website.live.notify_change" in (events.get("on_update") or [])
		}
		self.assertEqual(hooked, doctypes_pages_listen_for())

	def test_an_import_sends_no_hints(self):
		frappe.flags.in_import = True
		self.addCleanup(setattr, frappe.flags, "in_import", False)

		self.make_sermon(publish=1)
		self.assertEqual(self.hinted_doctypes(), [])
