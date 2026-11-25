# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.apps import get_apps, get_default_path
from frappe.auth import CookieManager, LoginManager
from frappe.desk.doctype.dock.dock import dock_key, get_app_dock
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.utils import get_home_page

from churchit.church_summary.home import add_return_to_framework_dock, land_desk_users_on_summary
from churchit.tests.helpers import RollbackEachTest, ensure_user

PASSWORD = "Home-Login-Password-1"


def default_workspace(user):
	return frappe.db.get_value("User", user, "default_workspace")


class TestLandOnSummary(RollbackEachTest):
	def test_a_new_desk_user_opens_summary(self):
		user = ensure_user("_test_home_desk@example.com", "_Test Home", roles=("Church Staff",))
		self.assertEqual(default_workspace(user), "Summary")

	def test_a_portal_member_gets_none(self):
		user = ensure_user("_test_home_member@example.com", "_Test Home")
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "Website User")
		self.assertFalse(default_workspace(user))

	def test_a_desk_user_who_cannot_open_summary_gets_none(self):
		# An ERPNext accountant on a shared site holds desk roles that Summary is not for.
		user = ensure_user("_test_home_other_app@example.com", "_Test Home", roles=("Website Manager",))
		self.assertEqual(frappe.db.get_value("User", user, "user_type"), "System User")
		self.assertFalse(default_workspace(user))

		land_desk_users_on_summary()

		self.assertFalse(default_workspace(user))

	def test_a_member_given_a_desk_role_opens_summary(self):
		user = ensure_user("_test_home_promoted@example.com", "_Test Home")
		frappe.get_doc("User", user).add_roles("Church Staff")
		self.assertEqual(default_workspace(user), "Summary")

	def test_a_desk_user_keeps_a_cleared_choice(self):
		user = ensure_user("_test_home_cleared@example.com", "_Test Home", roles=("Church Staff",))
		doc = frappe.get_doc("User", user)
		doc.default_workspace = None
		doc.save(ignore_permissions=True)
		self.assertFalse(default_workspace(user))

	def test_existing_desk_users_without_one_get_summary(self):
		unset = ensure_user("_test_home_unset@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", unset, "default_workspace", None)
		chosen = ensure_user("_test_home_chosen@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", chosen, "default_workspace", "People")

		land_desk_users_on_summary()

		self.assertEqual(default_workspace(unset), "Summary")
		self.assertEqual(default_workspace(chosen), "People")

	def test_a_desk_user_without_one_still_opens_summary(self):
		user = ensure_user("_test_home_role@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", user, "default_workspace", None)

		frappe.set_user(user)
		try:
			self.assertEqual(get_home_page(), "desk/summary")
		finally:
			frappe.set_user("Administrator")

	def test_no_role_sends_a_desk_user_out_of_the_desk(self):
		"""Administrator and the setup wizard's first user hold every role, and Frappe opens the home page of
		the first role it reads. A website page there would skip the setup wizard."""
		user = ensure_user("_test_home_every_role@example.com", "_Test Home", roles=("Church Staff",))
		frappe.db.set_value("User", user, "default_workspace", None)
		roles = frappe.get_all(
			"Role", filters={"name": ["like", "Church%"], "home_page": ["is", "set"]}, pluck="name"
		)

		frappe.set_user(user)
		self.addCleanup(frappe.set_user, "Administrator")
		# A desk session carries this; Frappe sends a desk user's "/me" to the desk by it.
		frappe.session.data.user_type = "System User"
		for role in roles:
			frappe.cache.hdel("home_page", user)
			with self.subTest(role=role), patch("frappe.get_roles", return_value=[role]):
				self.assertTrue(get_home_page().startswith("desk"))


class TestLoginLanding(FrappeTestCase):
	"""Where the login form sends each user. A login commits, so the class deletes its users at the end."""

	@classmethod
	def tearDownClass(cls):
		users = frappe.get_all("User", filters={"name": ["like", "_test_home_login_%"]}, pluck="name")
		for person in frappe.get_all("Person", filters={"user": ["in", users]}, pluck="name"):
			frappe.delete_doc("Person", person, force=True, ignore_permissions=True)
		for user in users:
			frappe.delete_doc("User", user, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	def tearDown(self):
		frappe.form_dict.clear()
		frappe.set_user("Administrator")

	def log_in(self, user):
		frappe.utils.password.update_password(user, PASSWORD)
		frappe.set_user("Guest")
		set_request(method="POST", path="/api/method/login")
		frappe.form_dict.update({"usr": user, "pwd": PASSWORD})
		# Later tests append to the test runner's response (its docs list).
		self.addCleanup(setattr, frappe.local, "response", frappe.local.response)
		frappe.local.response = frappe._dict()
		frappe.local.request_ip = "127.0.0.72"
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()
		return frappe.local.response

	def test_a_member_lands_on_the_member_portal(self):
		member = ensure_user("_test_home_login_member@example.com", "_Test Home")
		response = self.log_in(member)
		self.assertEqual(response.home_page, "/portal")
		self.assertNotIn("churchit", [app["name"] for app in get_apps()])

	def test_a_church_manager_still_gets_the_churchit_tile(self):
		manager = ensure_user("_test_home_login_manager@example.com", "_Test Home", roles=("Church Manager",))
		self.log_in(manager)
		self.assertEqual(get_default_path(), "/desk/summary")

	def test_a_volunteer_lands_on_their_own_work(self):
		"""Summary is not for them, so the role's home page opens their page or list instead."""
		check_in = ensure_user(
			"_test_home_login_check_in@example.com", "_Test Home", roles=("Church Check-In",)
		)
		self.assertEqual(self.log_in(check_in).home_page.strip("/"), "desk/check-in")
		self.assertTrue(frappe.get_doc("Page", "check-in").is_permitted())

		follow_up = ensure_user(
			"_test_home_login_follow_up@example.com", "_Test Home", roles=("Church Follow-up",)
		)
		self.assertEqual(self.log_in(follow_up).home_page.strip("/"), "desk/follow-up-card")
		self.assertTrue(frappe.has_permission("Follow-up Card", "read"))


def framework_site_dock():
	name = frappe.db.get_value("Dock", {"app": "frappe", "standard": 0, "user": ""})
	return frappe.get_doc("Dock", name) if name else None


class TestReturnToChurchit(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.db.delete("Dock", {"app": "frappe", "standard": 0, "user": ""})

	def test_framework_rail_leads_back_to_summary_first(self):
		frappe.get_doc(
			{"doctype": "Dock", "app": "frappe", "items": [{"link_type": "Sidebar", "link_to": "Users"}]}
		).insert(ignore_permissions=True)

		add_return_to_framework_dock()
		add_return_to_framework_dock()

		rows = [row.link_to for row in framework_site_dock().items]
		self.assertEqual(rows[:2], ["Summary", "Users"])
		self.assertEqual(rows.count("Summary"), 1)

	def test_the_arrangement_keeps_every_framework_entry(self):
		add_return_to_framework_dock()

		named = {dock_key(row) for row in framework_site_dock().items}
		for entry in get_app_dock("frappe"):
			self.assertIn(dock_key(entry), named)

	def test_a_hidden_return_entry_stays_hidden(self):
		add_return_to_framework_dock()
		dock = framework_site_dock()
		dock.items[0].hidden = 1
		dock.save(ignore_permissions=True)

		add_return_to_framework_dock()

		self.assertEqual(framework_site_dock().items[0].hidden, 1)
