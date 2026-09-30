# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.tests.helpers import ensure_root_church, make_branch, set_multi_church

PLACEHOLDER = "About Us has not been published yet. Please check back soon."


def about_settings(**values):
	settings = frappe.get_doc("About Us Settings")
	settings.update({"is_disabled": 0, **values})
	settings.save(ignore_permissions=True)


def serve_about():
	set_request(method="GET", path="about")
	return get_response("about").get_data(as_text=True)


def clear_church_story():
	"""Blank the Church's own About, which the page now prefers over the Single."""
	church = ensure_root_church()
	frappe.db.set_value("Church", church, {"about": None, "mission_statement": None})
	frappe.clear_document_cache("Church", church)


class TestAboutPage(FrappeTestCase):
	def setUp(self):
		clear_church_story()
		frappe.local.form_dict = frappe._dict()

	def test_says_not_published_until_the_church_writes_something(self):
		about_settings(company_introduction="", footer="", company_history=[], team_members=[])
		self.assertIn(PLACEHOLDER, serve_about())

	def test_shows_the_introduction_once_written(self):
		about_settings(company_introduction="<p>We meet on the hill.</p>")
		html = serve_about()
		self.assertIn("We meet on the hill.", html)
		self.assertNotIn(PLACEHOLDER, html)

	def test_a_team_alone_is_content_too(self):
		about_settings(
			company_introduction="",
			footer="",
			team_members=[{"full_name": "Pastor Ann", "image_link": "/x.png", "bio": "Shepherd"}],
		)
		html = serve_about()
		self.assertIn("Pastor Ann", html)
		self.assertNotIn(PLACEHOLDER, html)


class TestAboutFollowsTheChurch(FrappeTestCase):
	"""About Us Settings is one record for the site, so a branch needs its own story."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch = make_branch("_Test About Branch", "TAB", publish=1)
		frappe.db.set_value("Church", cls.root, "publish", 1)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		about_settings(company_introduction="<p>The main church story.</p>")
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()

	def serve_for(self, church):
		frappe.db.set_value("Church", church, "about", "<p>The branch story.</p>")
		frappe.db.set_value("Church", church, "mission_statement", "To serve this town.")
		frappe.clear_document_cache("Church", church)
		set_request(method="GET", path="about", query_string=f"church={church}")
		frappe.local.form_dict = frappe._dict(church=church)
		return get_response("about").get_data(as_text=True)

	def test_a_branch_tells_its_own_story(self):
		html = self.serve_for(self.branch)
		self.assertIn("The branch story.", html)
		self.assertIn("To serve this town.", html)
		self.assertNotIn("The main church story.", html)

	def test_a_church_with_nothing_written_falls_back_to_the_shared_introduction(self):
		frappe.db.set_value("Church", self.branch, "about", None)
		frappe.db.set_value("Church", self.branch, "mission_statement", None)
		frappe.clear_document_cache("Church", self.branch)
		set_request(method="GET", path="about", query_string=f"church={self.branch}")
		frappe.local.form_dict = frappe._dict(church=self.branch)

		html = get_response("about").get_data(as_text=True)
		self.assertIn("The main church story.", html)
		self.assertNotIn(PLACEHOLDER, html)
