# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, set_request
from frappe.website.serve import get_response

from churchit.church_website.published_fields import PUBLIC, published_field_map
from churchit.tests.helpers import (
	RollbackEachTest,
	force_single_church,
	make_function,
	make_two_churches,
)
from churchit.www.announcements import get_context

ROUTE = "announcements"
FIRST_DATE = "2031-06-01"
PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="


class TestAnnouncementsPage(RollbackEachTest):
	"""A guest reads the announcements a church chose to share, and nothing else from its bulletins."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.church_a, cls.church_b):
			frappe.db.set_value("Church", church, "publish", 1)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def make_bulletin(self, title, church=None, start_date=FIRST_DATE, **values):
		function = make_function(title, church=church or self.church_a, start_date=start_date)
		values = {"publish": 1, "share_announcements": 1, "announcements": f"<p>{title} news</p>", **values}
		return frappe.get_doc({"doctype": "Bulletin", "function": function.name, **values}).insert(
			ignore_permissions=True
		)

	def serve(self, church):
		frappe.set_user("Guest")
		set_request(method="GET", path=ROUTE, query_string=f"church={church}")
		frappe.local.form_dict = frappe._dict(church=church)
		return get_response(ROUTE).get_data(as_text=True)

	def test_a_guest_sees_only_the_shared_announcements_of_the_selected_church(self):
		self.make_bulletin("_Test Shared A", welcome="<p>_Test Welcome Text</p>")
		self.make_bulletin("_Test Shared B", church=self.church_b)
		self.make_bulletin("_Test Not Shared A", share_announcements=0)
		self.make_bulletin("_Test Unpublished A", publish=0)

		html = self.serve(self.church_a)

		self.assertIn("_Test Shared A news", html)
		for absent in ("_Test Welcome Text", "_Test Shared B", "_Test Not Shared A", "_Test Unpublished A"):
			self.assertNotIn(absent, html)

	def test_only_the_five_newest_bulletins_show(self):
		for week in range(6):
			self.make_bulletin(f"_Test Week {week}", start_date=add_days(FIRST_DATE, 7 * week))

		frappe.local.form_dict = frappe._dict(church=self.church_a)
		context = frappe._dict()
		get_context(context)

		titles = [bulletin.function_name for bulletin in context.bulletins]
		self.assertEqual(titles, [f"_Test Week {week}" for week in (5, 4, 3, 2, 1)])

	def test_an_image_pasted_into_shared_announcements_is_public(self):
		image = f"data:image/png;base64,{PIXEL}"
		bulletin = self.make_bulletin("_Test Flyer", announcements=f'<p>Flyer <img src="{image}"></p>')

		html = self.serve(self.church_a)

		self.assertNotIn("/private/files/", html)
		self.assertRegex(html, r'<img src="/files/[^"]+\.png"')
		self.assertEqual(
			frappe.get_all(
				"File",
				filters={"attached_to_doctype": "Bulletin", "attached_to_name": bulletin.name},
				pluck="is_private",
			),
			[0],
		)

	def test_announcements_and_their_switch_carry_the_public_badge(self):
		published = published_field_map()["Bulletin"]
		source = {"title": "Announcements", "route": ROUTE, "access": PUBLIC}
		for fieldname in ("announcements", "share_announcements"):
			self.assertIn(source, published[fieldname], fieldname)
		self.assertNotIn(ROUTE, [source["route"] for source in published.get("welcome", [])])


class TestAnnouncementsOnOneChurch(RollbackEachTest):
	def test_a_single_church_site_lists_its_shared_announcements(self):
		force_single_church()
		function = make_function("_Test Single Church News", start_date=FIRST_DATE)
		bulletin = frappe.get_doc(
			{
				"doctype": "Bulletin",
				"function": function.name,
				"publish": 1,
				"share_announcements": 1,
				"announcements": "<p>News</p>",
			}
		).insert(ignore_permissions=True)

		context = frappe._dict()
		get_context(context)

		self.assertIn(bulletin.name, [row.name for row in context.bulletins])
