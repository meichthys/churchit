# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website.published_fields import MEMBERS, published_field_map
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.www.bulletins import get_context, get_published_bulletins

ROUTE = "bulletins"


class TestBulletinsPage(FrappeTestCase):
	def make_bulletin(self, function_name, publish):
		function = make_function(function_name)
		return frappe.get_doc({"doctype": "Bulletin", "function": function.name, "publish": publish}).insert(
			ignore_permissions=True
		)

	def test_lists_only_published_bulletins(self):
		shared = self.make_bulletin("_Test Shared Service", publish=1)
		private = self.make_bulletin("_Test Draft Service", publish=0)

		names = [row.name for row in get_published_bulletins()]

		self.assertIn(shared.name, names)
		self.assertNotIn(private.name, names)

	def test_guests_are_sent_to_log_in(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.Redirect, get_context, frappe._dict())
			self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/bulletins")
		finally:
			frappe.set_user("Administrator")

	def test_a_guest_returns_to_the_digital_bulletin_after_logging_in(self):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(name="BLTN-0001")
		try:
			self.assertRaises(frappe.Redirect, get_context, frappe._dict())
			self.assertEqual(
				frappe.local.flags.redirect_location, "/login?redirect-to=/bulletins%3Fname%3DBLTN-0001"
			)
		finally:
			frappe.set_user("Administrator")
			frappe.local.form_dict = frappe._dict()


class TestBulletinsPageChurches(RollbackEachTest):
	"""A member of church A reads A's bulletins, whatever church the page is asked for."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.church_a, cls.church_b):
			frappe.db.set_value("Church", church, "publish", 1)
		cls.member = ensure_user("_test_bulletins_member_a@example.com", "Reader")
		make_person("_Test Bulletins", "Reader", church=cls.church_a, user=cls.member)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def make_bulletin(self, function_name, church, publish=1, **values):
		function = make_function(function_name, church=church)
		return frappe.get_doc(
			{"doctype": "Bulletin", "function": function.name, "publish": publish, **values}
		).insert(ignore_permissions=True)

	def serve(self, **query):
		frappe.set_user(self.member)
		set_request(method="GET", path=ROUTE, query_string="&".join(f"{k}={v}" for k, v in query.items()))
		frappe.local.form_dict = frappe._dict(query)
		return get_response(ROUTE)

	def test_the_list_holds_only_the_members_church_even_when_another_is_asked_for(self):
		mine = self.make_bulletin("_Test Bulletins Mine", self.church_a)
		theirs = self.make_bulletin("_Test Bulletins Theirs", self.church_b)

		html = self.serve(church=self.church_b).get_data(as_text=True)

		self.assertIn("_Test Bulletins Mine", html)
		self.assertIn(f"/bulletins?name={mine.name}", html)
		self.assertNotIn("_Test Bulletins Theirs", html)
		self.assertNotIn(theirs.name, html)

	def test_a_digital_bulletin_shows_the_bulletin_and_its_pdf_link(self):
		bulletin = self.make_bulletin(
			"_Test Bulletins Digital",
			self.church_a,
			welcome="<p>Welcome home</p>",
			announcements="<p>Potluck</p>",
		)

		response = self.serve(name=bulletin.name)
		html = response.get_data(as_text=True)

		self.assertEqual(response.status_code, 200)
		self.assertIn("_Test Bulletins Digital", html)
		self.assertIn("Welcome home", html)
		self.assertIn("Potluck", html)
		self.assertIn(f"download_pdf?name={bulletin.name}", html)

	def test_an_image_link_cannot_add_an_attribute(self):
		bulletin = self.make_bulletin(
			"_Test Bulletins Image", self.church_a, cover_image='/files/x.png" onerror="alert(1)'
		)

		html = self.serve(name=bulletin.name).get_data(as_text=True)

		self.assertNotIn('onerror="alert(1)"', html)
		self.assertIn("/files/x.png&#34; onerror=&#34;alert(1)", html)

	def test_another_churchs_or_an_unpublished_bulletin_is_not_found(self):
		theirs = self.make_bulletin("_Test Bulletins Other", self.church_b)
		draft = self.make_bulletin("_Test Bulletins Draft", self.church_a, publish=0)

		for name in (theirs.name, draft.name, "BLTN-does-not-exist"):
			response = self.serve(name=name)
			self.assertEqual(response.status_code, 404, name)
			self.assertNotIn("_Test Bulletins", response.get_data(as_text=True))

	def test_the_digital_bulletin_is_members_only(self):
		published = published_field_map()["Bulletin"]
		for fieldname in ("welcome", "announcements", "cover_image"):
			self.assertIn(
				{"title": "Bulletins", "route": ROUTE, "access": MEMBERS}, published[fieldname], fieldname
			)
