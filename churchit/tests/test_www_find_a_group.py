# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import quote

import frappe
from frappe.utils import add_days, set_request, today
from frappe.website.serve import get_response

from churchit.church_website.context import update_website_context
from churchit.church_website.published_fields import published_field_map
from churchit.patches.v1_0 import add_find_a_group_to_navbar
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_address,
	make_function,
	make_person,
	make_two_churches,
)

ROUTE = "find-a-group"


class TestFindAGroup(RollbackEachTest):
	"""A guest finds the selected church's open groups, with a city and a rough pin but no street."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.church, cls.other_church):
			frappe.db.set_value("Church", church, "publish", 1)
		ensure("Group Type", {"type": "_Test Finder Type"})
		ensure("Group Role", {"role": "Member"})

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def make_group(self, name, church=None, **values):
		return frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": name,
				"church": church or self.church,
				"public": 1,
				"show_in_portal": 1,
				**values,
			}
		).insert(ignore_permissions=True)

	def make_schedule(self, group, **values):
		address = make_address("_Test Finder Home", address_line1="12 Hidden Lane", city="Shelbyville")
		frappe.db.set_value("Address", address.name, {"latitude": 40.12345, "longitude": -88.98765})
		return make_function(
			"_Test Finder Meeting",
			church=self.church,
			group=group.name,
			address=address.name,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week="Tuesday",
			start_date=today(),
			start_time="19:00:00",
			**values,
		)

	def serve(self, user="Guest", **query):
		frappe.set_user(user)
		query = {"church": self.church, **query}
		set_request(method="GET", path=ROUTE, query_string="&".join(f"{k}={v}" for k, v in query.items()))
		frappe.local.form_dict = frappe._dict(query)
		return get_response(ROUTE).get_data(as_text=True)

	def test_a_guest_sees_only_the_selected_churchs_open_groups(self):
		self.make_group("_Test Finder Mine", group_type="_Test Finder Type")
		self.make_group("_Test Finder Theirs", church=self.other_church)
		self.make_group("_Test Finder Private", public=0)
		self.make_group("_Test Finder Off Portal", show_in_portal=0)
		self.make_group("_Test Finder Inactive", status="Inactive")

		html = self.serve()
		self.assertIn("_Test Finder Mine", html)
		self.assertIn("_Test Finder Type", html)
		for absent in (
			"_Test Finder Theirs",
			"_Test Finder Private",
			"_Test Finder Off Portal",
			"_Test Finder Inactive",
		):
			self.assertNotIn(absent, html)

	def test_the_meeting_shows_its_day_time_and_city_but_no_street(self):
		group = self.make_group("_Test Finder Meets")
		self.make_schedule(group)

		html = self.serve()
		self.assertIn("Weekly on Tuesday at", html)
		self.assertIn('data-days="Tuesday"', html)
		self.assertIn("Shelbyville", html)
		self.assertNotIn("12 Hidden Lane", html)
		self.assertIn("[40.12, -88.99]", html)
		self.assertNotIn("40.123", html)

	def test_a_guests_join_signs_in_and_comes_back_to_the_group(self):
		group = self.make_group("_Test Finder Guest Join")
		target = quote(f"/find-a-group?group={group.name}&church={self.church}", safe="")

		self.assertIn(f'href="/login?redirect-to={target}"', self.serve())

	def test_a_member_joins_on_the_page(self):
		self.make_group("_Test Finder Member Join", requires_approval=1)
		user = ensure_user("_test_finder_member@example.com", "_Test Finder Member")
		make_person("_Test Finder", "Member", church=self.church, user=user)
		html = self.serve(user)
		self.assertIn("find-group-join", html)
		self.assertIn("Ask to Join", html)
		self.assertNotIn("/login?redirect-to=", html)

	def test_full_and_closed_groups_say_so(self):
		person = make_person("_Test Finder", "Member Two", church=self.church).name
		self.make_group("_Test Finder Full", capacity=1, members=[{"person": person}])
		self.make_group("_Test Finder Closed", close_enrollment_on=add_days(today(), -1))

		html = self.serve()
		self.assertIn(">Full<", html)
		self.assertIn(">Closed<", html)
		self.assertNotIn("Member Two", html)

	def test_the_page_loads_leaflet_once(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.local.path = ROUTE
		hooks = frappe.get_hooks()
		context = frappe._dict(web_include_js=hooks.web_include_js, web_include_css=hooks.web_include_css)
		update_website_context(context)
		update_website_context(context)

		self.assertEqual(context.web_include_js.count("leaflet.bundle.js"), 1)
		self.assertEqual(context.web_include_css.count("leaflet.bundle.css"), 1)

	def test_the_badges_mark_the_group_fields_public_and_no_street(self):
		published = published_field_map()

		def access(doctype, fieldname):
			return {
				source["access"]
				for source in published.get(doctype, {}).get(fieldname, [])
				if source["route"] == ROUTE
			}

		self.assertEqual(access("Group", "group_name"), {"public"})
		self.assertEqual(access("Group", "description"), {"public"})
		self.assertEqual(access("Address", "city"), {"public"})
		self.assertEqual(access("Address", "address_line1"), set())
		self.assertEqual(access("Group", "meets"), set())


class TestFindAGroupNavbar(RollbackEachTest):
	def test_the_patch_adds_the_item_after_ministries_once(self):
		settings = frappe.get_doc("Website Settings")
		settings.top_bar_items = []
		for url in ("/home", "/ministries", "/calendar"):
			settings.append("top_bar_items", {"label": url.strip("/").title(), "url": url, "right": 1})
		settings.save(ignore_permissions=True)

		add_find_a_group_to_navbar.execute()
		add_find_a_group_to_navbar.execute()

		urls = [row.url for row in frappe.get_doc("Website Settings").top_bar_items]
		self.assertEqual(urls, ["/home", "/ministries", "/find-a-group", "/calendar"])
