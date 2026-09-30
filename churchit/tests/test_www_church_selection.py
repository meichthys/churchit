# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Which church the public website shows once branches exist."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import church_filters, selected_church_filters
from churchit.church_website.context import before_request, update_website_context
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
)
from churchit.www import locations
from churchit.www.bulletins import get_published_bulletins
from churchit.www.calendar import get_events


def select_church(name):
	frappe.local.form_dict = frappe._dict(church=name) if name else frappe._dict()


def locations_menu(context):
	return next((item for item in context.get("top_bar_items", []) if item.label == "Locations"), None)


class TestWebsiteChurchSelection(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch = make_branch("_Test Site Branch", "TSB", publish=1)
		cls.hidden = make_branch("_Test Hidden Branch", "THB", publish=0)
		frappe.db.set_value("Church", cls.root, "publish", 1)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		select_church(None)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.no_cache = 0
		select_church(None)

	def test_the_root_church_is_the_default(self):
		self.assertEqual(selected_church_name(), self.root)

	def test_the_query_parameter_selects_a_published_branch(self):
		select_church(self.branch)
		self.assertEqual(selected_church_name(), self.branch)

	def test_an_unpublished_branch_falls_back_to_the_main_church(self):
		select_church(self.hidden)
		self.assertEqual(selected_church_name(), self.root)
		select_church("CHR-does-not-exist")
		self.assertEqual(selected_church_name(), self.root)

	def test_signed_in_members_default_to_their_own_church(self):
		user = ensure_user("_test_site_member@example.com", "Site")
		make_person("_Test Site", "Member", church=self.branch, user=user)
		frappe.set_user(user)
		self.assertEqual(selected_church_name(), self.branch)

		select_church(self.root)
		self.assertEqual(selected_church_name(), self.root)

	def test_the_calendar_follows_the_selected_church(self):
		root_event = make_function("_Test Root Event", start_date=getdate(), publish=1, church=self.root)
		branch_event = make_function(
			"_Test Branch Event", start_date=getdate(), publish=1, church=self.branch
		)

		select_church(self.branch)
		events = {event["id"] for event in get_events(add_days(getdate(), -1), add_days(getdate(), 1))}

		self.assertIn(branch_event.name, events)
		self.assertNotIn(root_event.name, events)

	def test_bulletins_follow_the_selected_church(self):
		function = make_function("_Test Branch Service", church=self.branch)
		bulletin = frappe.get_doc({"doctype": "Bulletin", "function": function.name, "publish": 1}).insert(
			ignore_permissions=True
		)
		self.assertEqual(bulletin.church, self.branch)

		self.assertNotIn(bulletin.name, [row.name for row in get_published_bulletins()])
		select_church(self.branch)
		self.assertIn(bulletin.name, [row.name for row in get_published_bulletins()])

	def test_the_navbar_offers_the_published_churches(self):
		context = frappe._dict({})
		update_website_context(context)

		menu = locations_menu(context)
		labels = [item.label for item in menu.child_items]
		self.assertIn("_Test Site Branch", labels)
		self.assertNotIn("_Test Hidden Branch", labels)
		self.assertEqual(menu.child_items[-1].url, "/locations")
		self.assertIn(
			f"?church={self.branch}",
			[item.url for item in menu.child_items][labels.index("_Test Site Branch")],
		)

	def test_the_locations_page_lists_the_published_churches(self):
		context = frappe._dict({})
		locations.get_context(context)
		names = [church.name for church in context.churches]
		self.assertIn(self.branch, names)
		self.assertNotIn(self.hidden, names)

	def test_a_shared_record_appears_on_every_church_s_pages(self):
		"""The public site scopes by the selected church, so sharing has to reach it too."""
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Shared Sermon", "publish": 1, "is_shared": 1}
		).insert(ignore_permissions=True)
		self.assertEqual(sermon.church, "")

		for church in (self.root, self.branch):
			published = frappe.get_all("Sermon", filters=church_filters(church, publish=1), pluck="name")
			self.assertIn(sermon.name, published, f"a shared sermon should show under {church}")

	def test_an_unshared_record_stays_on_its_own_pages(self):
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Branch Sermon", "publish": 1, "church": self.branch}
		).insert(ignore_permissions=True)

		self.assertNotIn(
			sermon.name, frappe.get_all("Sermon", filters=church_filters(self.root, publish=1), pluck="name")
		)

	def test_selected_church_filters_follow_the_selection(self):
		"""The Jinja method the shipped page templates scope their queries with."""
		self.assertEqual(
			selected_church_filters(publish=1), {"publish": 1, "church": ("in", [self.root, ""])}
		)

		select_church(self.branch)
		self.assertEqual(
			selected_church_filters(publish=1), {"publish": 1, "church": ("in", [self.branch, ""])}
		)

	def anonymous_request(self, title, church):
		"""A prayer request as the anonymous web form submits it, church and all."""
		frappe.set_user("Guest")
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": title,
				"type": ensure("Prayer Request Type", {"type": "_Test Site Prayer"}),
				"request": "Please pray",
				"church": church,
			}
		).insert(ignore_permissions=True)

	def test_an_anonymous_request_stays_with_the_page_s_church(self):
		request = self.anonymous_request("_Test Branch Prayer", self.branch)
		self.assertEqual(request.church, self.branch)

	def test_an_anonymous_request_cannot_name_an_unpublished_church(self):
		request = self.anonymous_request("_Test Hidden Prayer", self.hidden)
		self.assertEqual(request.church, self.root)

	def test_signed_in_visitors_skip_the_shared_page_cache(self):
		frappe.set_user("Guest")
		before_request()
		self.assertFalse(getattr(frappe.local, "no_cache", 0))

		frappe.set_user(ensure_user("_test_cached_member@example.com", "Cached"))
		before_request()
		self.assertTrue(frappe.local.no_cache)


class TestWebsiteSingleChurch(FrappeTestCase):
	def test_the_locations_page_and_menu_are_absent(self):
		ensure_root_church()
		force_single_church()
		with self.assertRaises(frappe.PageDoesNotExistError):
			locations.get_context(frappe._dict({}))

		context = frappe._dict({})
		update_website_context(context)
		self.assertIsNone(locations_menu(context))
