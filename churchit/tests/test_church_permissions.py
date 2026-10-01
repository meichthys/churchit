# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The multi-church access model: Person-driven User Permissions and what they scope."""

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from churchit.church_communications.doctype.bulletin.bulletin import get_defaults as bulletin_defaults
from churchit.church_finances.doctype.budget.budget import get_expense_totals
from churchit.church_finances.doctype.giving_statement.giving_statement import (
	generate_statements,
	get_givers,
)
from churchit.church_foundations.church_access import (
	set_church_filter_expansion,
	set_include_branches,
	user_church_permissions,
)
from churchit.church_foundations.doctype.church.church import church_name
from churchit.church_ministries.doctype.function.function import create_scheduled_functions
from churchit.church_ministries.page.check_in import check_in as check_in_station
from churchit.church_missions.doctype.missionary.missionary import create_missionary_expenses
from churchit.church_people.group_api import joinable_public_groups
from churchit.church_people.report.church_directory_report import church_directory_report as directory
from churchit.church_prayers.report.active_prayer_list import active_prayer_list
from churchit.church_prayers.web_form.community_prayer_requests import (
	community_prayer_requests as prayer_form,
)
from churchit.church_scope import SHARED, extend_bootinfo, scoped
from churchit.tests.helpers import (
	assert_scoped,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
	set_private_people,
)


def make_prayer_request(title, church):
	request_type = ensure("Prayer Request Type", {"type": "_Test Scope"})
	return frappe.get_doc(
		{"doctype": "Prayer Request", "title": title, "type": request_type, "church": church}
	).insert(ignore_permissions=True)


class TestChurchPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch_a = make_branch("_Test Branch A", "TBA")
		cls.branch_b = make_branch("_Test Branch B", "TBB")
		cls.manager_a = cls.bind_manager("_test_manager_a@example.com", "ManagerA", cls.branch_a)
		cls.manager_b = cls.bind_manager("_test_manager_b@example.com", "ManagerB", cls.branch_b)
		cls.parent_manager = cls.bind_manager("_test_parent_manager@example.com", "Parent", cls.root)
		cls.request_a = make_prayer_request("_Test Request A", cls.branch_a)
		cls.request_b = make_prayer_request("_Test Request B", cls.branch_b)
		cls.function_a = make_function("_Test Function A", church=cls.branch_a)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def bind_manager(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Manager",))
		make_person(first_name, "Manager", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_user_added_in_the_desk_takes_the_adders_church(self):
		"""No Church permission means no restriction, so a new login cannot be left without one."""
		frappe.set_user(self.manager_a)
		user = frappe.get_doc(
			{"doctype": "User", "email": "_test_desk_made@example.com", "first_name": "DeskMade"}
		)
		user.flags.no_welcome_mail = True
		user.insert(ignore_permissions=True)

		(permission,) = user_church_permissions(user.name)
		self.assertEqual(permission.for_value, self.branch_a)
		self.assertEqual(permission.hide_descendants, 1)

	def test_a_user_signing_up_on_a_branchs_page_takes_that_church(self):
		frappe.db.set_value("Church", self.branch_b, "publish", 1)
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.branch_b)
		try:
			user = frappe.get_doc(
				{"doctype": "User", "email": "_test_signed_up@example.com", "first_name": "SignedUp"}
			)
			user.flags.no_welcome_mail = True
			user.insert(ignore_permissions=True)
		finally:
			frappe.local.form_dict = frappe._dict()

		(permission,) = user_church_permissions(user.name)
		self.assertEqual(permission.for_value, self.branch_b)

	def request_made_on_the_page_of(self, church, title):
		"""A prayer request naming no church, saved as though a page for *church* took it."""
		frappe.db.set_value("Church", church, "publish", 1)
		frappe.local.form_dict = frappe._dict(church=church)
		try:
			request = make_prayer_request(title, None)
		finally:
			frappe.local.form_dict = frappe._dict()
		# One transaction spans the class, so leave the prayer lists as they were.
		self.addCleanup(
			frappe.delete_doc, "Prayer Request", request.name, ignore_permissions=True, force=True
		)
		return request

	def test_a_record_made_on_a_branchs_page_belongs_to_that_branch(self):
		"""An anonymous prayer request used to land on the main church whatever page took it."""
		frappe.set_user("Guest")

		request = self.request_made_on_the_page_of(self.branch_b, "_Test Request From A Branch Page")

		self.assertEqual(request.church, self.branch_b)

	def test_a_readers_own_church_wins_over_the_page_they_are_on(self):
		"""Their own church, or Frappe would refuse a record they cannot see."""
		frappe.set_user(self.manager_a)

		request = self.request_made_on_the_page_of(self.branch_b, "_Test Request From Another Page")

		self.assertEqual(request.church, self.branch_a)

	def test_a_greeting_is_signed_by_the_church_of_whoever_it_is_about(self):
		person = make_person("_Test Signed", "Greeting", church=self.branch_b)
		person.append(
			"life_events", {"event_type": ensure("Life Event Type", {"type": "Birth"}), "date": "1990-05-01"}
		)
		person.save(ignore_permissions=True)
		branch_name = frappe.db.get_value("Church", self.branch_b, "church_name")

		self.assertEqual(church_name(person), branch_name)
		# The birthday greeting is sent on the Life Event row, which carries no church of its own.
		self.assertEqual(church_name(person.life_events[0]), branch_name)

	def test_linking_a_person_afterwards_repoints_the_guess(self):
		user = ensure_user("_test_guess_then_person@example.com", "Guess")
		make_person("_Test Guess", "Person", church=self.branch_b, user=user)

		(permission,) = user_church_permissions(user)
		self.assertEqual(permission.for_value, self.branch_b)

	def test_linking_a_user_creates_the_church_permission(self):
		(permission,) = user_church_permissions(self.manager_a)
		self.assertEqual(permission.for_value, self.branch_a)
		self.assertEqual(permission.hide_descendants, 1)

	def test_changing_the_church_repoints_the_permission(self):
		user = ensure_user("_test_mover@example.com", "Mover")
		person = make_person("_Test Mover", "Person", church=self.branch_a, user=user)

		person.church = self.branch_b
		person.save()

		self.assertEqual([p.for_value for p in user_church_permissions(user)], [self.branch_b])

	def test_an_unrelated_save_keeps_administrator_edits(self):
		(permission,) = user_church_permissions(self.parent_manager)
		frappe.db.set_value("User Permission", permission.name, "hide_descendants", 0)

		person = frappe.get_doc("Person", {"user": self.parent_manager})
		person.last_name = "Renamed"
		person.save()

		self.assertEqual(user_church_permissions(self.parent_manager)[0].hide_descendants, 0)
		frappe.db.set_value("User Permission", permission.name, "hide_descendants", 1)

	def test_branch_manager_sees_only_their_own_church(self):
		frappe.set_user(self.manager_a)

		requests = frappe.get_list("Prayer Request", pluck="name")
		self.assertIn(self.request_a.name, requests)
		self.assertNotIn(self.request_b.name, requests)
		self.assertTrue(frappe.has_permission("Prayer Request", "read", doc=self.request_a.name))
		self.assertFalse(frappe.has_permission("Prayer Request", "read", doc=self.request_b.name))
		self.assertIn(self.function_a.name, frappe.get_list("Function", pluck="name"))

		frappe.set_user(self.manager_b)
		self.assertNotIn(self.function_a.name, frappe.get_list("Function", pluck="name"))

	def test_parent_manager_sees_branches_only_when_included(self):
		frappe.set_user(self.parent_manager)
		self.assertNotIn(self.request_a.name, frappe.get_list("Prayer Request", pluck="name"))

		self.assertTrue(set_include_branches("true"))
		requests = frappe.get_list("Prayer Request", pluck="name")
		self.assertIn(self.request_a.name, requests)
		self.assertIn(self.request_b.name, requests)

		self.assertFalse(set_include_branches(False))
		self.assertNotIn(self.request_a.name, frappe.get_list("Prayer Request", pluck="name"))

	def test_branch_manager_cannot_include_branches(self):
		frappe.set_user(self.manager_a)
		with self.assertRaises(ValidationError):
			set_include_branches(True)

	def test_confirmed_transfer_moves_the_person_and_their_permission(self):
		user = ensure_user("_test_transfer@example.com", "Transfer")
		person = make_person("_Test Transfer", "Person", church=self.branch_a, user=user)
		transfer = frappe.get_doc(
			{
				"doctype": "Member Transfer",
				"person": person.name,
				"direction": "Out",
				"to_church": self.branch_b,
			}
		).insert(ignore_permissions=True)

		transfer.status = "Confirmed"
		transfer.save()

		self.assertEqual(frappe.db.get_value("Person", person.name, "church"), self.branch_b)
		self.assertEqual([p.for_value for p in user_church_permissions(user)], [self.branch_b])

	def test_transfer_to_the_same_church_is_refused(self):
		person = make_person("_Test Stayer", "Person", church=self.branch_a)
		with self.assertRaises(ValidationError):
			frappe.get_doc(
				{
					"doctype": "Member Transfer",
					"person": person.name,
					"direction": "Out",
					"to_church": self.branch_a,
					"status": "Confirmed",
				}
			).insert(ignore_permissions=True)

	def test_reports_only_show_the_users_churches(self):
		frappe.set_user(self.manager_a)
		names = [row.name for row in active_prayer_list.execute({})[1]]
		self.assertIn(self.request_a.name, names)
		self.assertNotIn(self.request_b.name, names)

	def test_asking_a_report_for_another_church_is_refused(self):
		frappe.set_user(self.manager_a)
		with self.assertRaises(frappe.PermissionError):
			active_prayer_list.execute({"church": self.branch_b})

	def test_unrestricted_users_can_pick_any_church_in_a_report(self):
		names = [row.name for row in active_prayer_list.execute({"church": self.branch_b})[1]]
		self.assertEqual(names, [self.request_b.name])

	def test_notifications_skip_managers_of_other_churches(self):
		notification = frappe.get_doc("Notification", "Prayer Request New")
		recipients, _cc, _bcc = notification.get_list_of_recipients(self.request_a, {"doc": self.request_a})
		self.assertIn(self.manager_a, recipients)
		self.assertNotIn(self.manager_b, recipients)
		self.assertNotIn(self.parent_manager, recipients)

	def test_notifications_on_child_rows_follow_the_parent(self):
		person = make_person("_Test Positioned", "Person", church=self.branch_b)
		person.append(
			"positions",
			{
				"position": ensure("Position Type", {"position": "_Test Scope Role"}),
				"start_date": "2030-01-01",
			},
		)
		person.save()
		notification = frappe.get_doc("Notification", "Position Term Ending")

		recipients, _cc, _bcc = notification.get_list_of_recipients(
			person.positions[0], {"doc": person.positions[0]}
		)

		self.assertIn(self.manager_b, recipients)
		self.assertNotIn(self.manager_a, recipients)

	def test_scheduled_functions_keep_the_templates_church(self):
		template = make_function(
			"_Test Branch Weekly",
			church=self.branch_b,
			start_date=add_days(getdate(), -10),
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
		)
		create_scheduled_functions()
		occurrences = frappe.get_all("Function", filters={"source_template": template.name}, pluck="church")
		self.assertEqual(occurrences, [self.branch_b])

	def test_missionary_expenses_keep_the_missionarys_church(self):
		fund = ensure(
			"Fund",
			{"fund": "_Test Scope Missions Fund"},
			{"fund": "_Test Scope Missions Fund", "is_shared": 1},
		)
		expense_type = ensure(
			"Expense Type", {"type": "_Test Scope Support"}, {"type": "_Test Scope Support", "fund": fund}
		)
		missionary = frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Scope Missionary",
				"church": self.branch_b,
				"support_amount": 50,
				"support_frequency": "Monthly",
				"support_start_date": add_days(getdate(), -40),
				"auto_create_expenses": 1,
				"expense_type": expense_type,
			}
		).insert(ignore_permissions=True)

		create_missionary_expenses()

		churches = set(frappe.get_all("Expense", filters={"missionary": missionary.name}, pluck="church"))
		self.assertEqual(churches, {self.branch_b})

	def test_portal_community_requests_stay_within_the_members_church(self):
		frappe.set_user(self.manager_a)
		context = prayer_form.get_list_context(frappe._dict())
		names = [row.name for row in context.get_list("Prayer Request", "", [], 0, 500)]
		self.assertIn(self.request_a.name, names)
		self.assertNotIn(self.request_b.name, names)

	def test_portal_joinable_groups_stay_within_the_members_church(self):
		group_a = ensure(
			"Group",
			{"group_name": "_Test Group A"},
			{"group_name": "_Test Group A", "public": 1, "show_in_portal": 1, "church": self.branch_a},
		)
		group_b = ensure(
			"Group",
			{"group_name": "_Test Group B"},
			{"group_name": "_Test Group B", "public": 1, "show_in_portal": 1, "church": self.branch_b},
		)
		frappe.set_user(self.manager_a)
		names = [row.name for row in joinable_public_groups()]
		self.assertIn(group_a, names)
		self.assertNotIn(group_b, names)

	def test_a_family_follows_its_head_of_household(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Mover Family", "church": self.branch_a}
		).insert(ignore_permissions=True)
		head = make_person(
			"_Test Head", "Mover", church=self.branch_a, family=family.name, is_head_of_household=1
		)
		self.assertEqual(frappe.db.get_value("Family", family.name, "church"), self.branch_a)

		head.church = self.branch_b
		head.save()

		self.assertEqual(frappe.db.get_value("Family", family.name, "church"), self.branch_b)
		family.reload()
		family.save()
		self.assertEqual(family.church, self.branch_b)

	def test_directory_lists_families_of_members_who_moved(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Split Family", "church": self.root}
		).insert(ignore_permissions=True)
		make_person("_Test Staying", "Head", church=self.root, family=family.name, is_head_of_household=1)
		moved = make_person("_Test Moved", "Member", church=self.branch_a, family=family.name)
		self.assertEqual(frappe.db.get_value("Family", family.name, "church"), self.root)

		frappe.set_user(self.manager_a)
		rows = directory.execute({"group_by_family": 1})[1]
		by_family = {row["family"]: row for row in rows}
		self.assertIn(family.name, by_family)
		self.assertEqual(by_family[family.name]["member_count"], 1)
		self.assertIn(moved.name, [row["person"] for row in directory.execute({"group_by_family": 0})[1]])

	def test_a_requested_church_narrows_like_a_list_filter(self):
		"""With branches included, a blank filter shows them all; a picked church shows only itself."""
		frappe.set_user(self.parent_manager)
		set_include_branches(True)
		names = [row.name for row in active_prayer_list.execute({})[1]]
		self.assertIn(self.request_a.name, names)
		self.assertIn(self.request_b.name, names)

		names = [row.name for row in active_prayer_list.execute({"church": self.root})[1]]
		self.assertNotIn(self.request_a.name, names)
		self.assertNotIn(self.request_b.name, names)
		set_include_branches(False)

	def test_branch_expansion_is_a_per_user_choice(self):
		frappe.set_user(self.parent_manager)
		set_include_branches(True)
		self.assertTrue(set_church_filter_expansion("true"))
		names = [row.name for row in active_prayer_list.execute({"church": self.root})[1]]
		self.assertIn(self.request_a.name, names)
		self.assertIn(self.request_b.name, names)

		self.assertFalse(set_church_filter_expansion(False))
		names = [row.name for row in active_prayer_list.execute({"church": self.root})[1]]
		self.assertNotIn(self.request_a.name, names)
		set_include_branches(False)

	def test_branch_expansion_never_reaches_past_the_users_scope(self):
		frappe.set_user(self.parent_manager)
		set_church_filter_expansion(True)
		names = [row.name for row in active_prayer_list.execute({"church": self.root})[1]]
		self.assertNotIn(self.request_a.name, names)
		set_church_filter_expansion(False)

	def test_unrestricted_users_get_exactly_the_requested_church(self):
		names = [row.name for row in active_prayer_list.execute({"church": self.root})[1]]
		self.assertNotIn(self.request_a.name, names)
		self.assertNotIn(self.request_b.name, names)

	def test_check_in_station_stays_within_the_operators_church(self):
		"""With a private directory: the station's raw queries carry no permission filter of their own."""
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		mine = make_person("_Test Station", "Local", church=self.branch_a)
		theirs = make_person("_Test Station", "Foreign", church=self.branch_b)
		make_function("_Test Station Service", church=self.branch_b, start_date=getdate())

		frappe.set_user(self.manager_a)
		found = [
			member.name
			for group in check_in_station.search_people("_Test Station")
			for member in group["members"]
		]

		self.assertIn(mine.name, found)
		self.assertNotIn(theirs.name, found)
		functions = [f.name for f in check_in_station.get_station_context()["functions"]]
		self.assertNotIn("_Test Station Service", functions)

	def test_a_bulletin_only_carries_its_own_churchs_content(self):
		"""The bulletin fills itself from site-wide lists, which carry no permission filter."""
		function = make_function("_Test Bulletin Service", church=self.branch_a, start_date=getdate())

		defaults = bulletin_defaults(function.name)

		titles = [row["title"] for row in defaults["prayer_requests"]]
		self.assertIn(self.request_a.title, titles)
		self.assertNotIn(self.request_b.title, titles)

	def test_bulletin_defaults_refuse_another_churchs_function(self):
		"""Naming a function reads its church's prayer requests and missionaries."""
		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			bulletin_defaults(self.function_a.name)

	def test_the_shared_helper_proves_a_doctype_is_scoped(self):
		"""The one-liner new features should use; see AGENTS.md."""
		assert_scoped(self, "Prayer Request", self.manager_a, self.request_a.name, self.request_b.name)

	def share(self, doctype, name):
		"""Hand a record to every church, the way the checkbox does."""
		doc = frappe.get_doc(doctype, name)
		doc.is_shared = 1
		doc.save(ignore_permissions=True)
		return doc

	def test_a_shared_record_reaches_every_church(self):
		mine = ensure("Song", {"title": "_Test Branch Song"}, {"title": "_Test Branch Song"})
		frappe.db.set_value("Song", mine, "church", self.branch_a)
		shared = self.share(
			"Song", ensure("Song", {"title": "_Test Shared Song"}, {"title": "_Test Shared Song"})
		)
		self.assertEqual(shared.church, "")
		self.assertEqual(shared.shared_by_church, self.root)

		born_shared = frappe.get_doc(
			{"doctype": "Song", "title": "_Test Born Shared", "is_shared": 1}
		).insert(ignore_permissions=True)
		self.assertEqual(born_shared.church, "")
		self.assertEqual(born_shared.shared_by_church, self.root, "a record shared from birth still says who")

		frappe.set_user(self.manager_b)
		songs = frappe.get_list("Song", pluck="name")
		self.assertIn(shared.name, songs, "a shared song should reach every church")
		self.assertNotIn(mine, songs, "another church's own song should stay hidden")

	def test_a_shared_record_reaches_reports_as_well_as_lists(self):
		"""Reports run raw, so sharing has to be widened there by hand."""
		shared = self.share(
			"Song", ensure("Song", {"title": "_Test Shared In Report"}, {"title": "_Test Shared In Report"})
		)
		Song = frappe.qb.DocType("Song")

		frappe.set_user(self.manager_a)
		query = frappe.qb.from_(Song).select(Song.name)
		self.assertIn(shared.name, scoped(query, Song, {}).run(pluck=True))

	def test_a_branch_can_share_upward(self):
		song = ensure("Song", {"title": "_Test Upward Song"}, {"title": "_Test Upward Song"})
		frappe.db.set_value("Song", song, "church", self.branch_a)

		frappe.set_user(self.manager_a)
		shared = self.share("Song", song)
		self.assertEqual(shared.shared_by_church, self.branch_a)

		frappe.set_user(self.parent_manager)
		self.assertIn(shared.name, frappe.get_list("Song", pluck="name"))

	def test_only_the_owning_church_may_stop_sharing(self):
		"""A recipient unticking the box would pull the record from everyone, itself included."""
		song = ensure("Song", {"title": "_Test Owned Song"}, {"title": "_Test Owned Song"})
		frappe.db.set_value("Song", song, "church", self.branch_a)
		self.share("Song", song)

		frappe.set_user(self.manager_b)
		doc = frappe.get_doc("Song", song)
		doc.is_shared = 0
		with self.assertRaises(frappe.PermissionError):
			doc.save()

		frappe.set_user(self.manager_a)
		owner_copy = frappe.get_doc("Song", song)
		owner_copy.is_shared = 0
		owner_copy.save()
		self.assertEqual(owner_copy.church, self.branch_a)

	def test_a_shared_function_and_its_sign_ups_reach_every_church(self):
		"""A joint service is one occasion, so its sign-ups are one roster."""
		function = make_function("_Test Joint Service", church=self.branch_a, allow_sign_ups=1)
		self.share("Function", function.name)

		sign_up = frappe.get_doc(
			{
				"doctype": "Function Sign-Up",
				"function": function.name,
				"person": make_person("_Test Joint", "Volunteer", church=self.branch_b).name,
			}
		).insert(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Function", function.name, "church"), "")
		self.assertEqual(sign_up.church, "", "a sign-up for a shared function is shared with it")

		frappe.set_user(self.manager_b)
		self.assertIn(function.name, frappe.get_list("Function", pluck="name"))
		self.assertIn(sign_up.name, frappe.get_list("Function Sign-Up", pluck="name"))

	def test_shared_minutes_reach_every_church(self):
		minutes = frappe.get_doc(
			{
				"doctype": "Meeting Minutes",
				"title": "_Test Board Meeting",
				"meeting_date": "2033-04-02",
				"church": self.branch_a,
			}
		).insert(ignore_permissions=True)
		self.share("Meeting Minutes", minutes.name)

		frappe.set_user(self.manager_b)
		self.assertIn(minutes.name, frappe.get_list("Meeting Minutes", pluck="name"))

	def test_a_belief_is_shared_by_default_and_can_be_kept_to_one_church(self):
		"""Branches normally hold one statement of faith, so the box starts ticked."""
		frappe.set_user(self.manager_a)
		shared = frappe.get_doc(
			{"doctype": "Belief", "title": "_Test Shared Belief", "belief_statement": "We believe."}
		).insert()
		self.assertTrue(shared.is_shared, "a new belief starts shared")
		self.assertEqual(shared.church, "")

		own = frappe.get_doc(
			{
				"doctype": "Belief",
				"title": "_Test Branch Belief",
				"belief_statement": "We also believe.",
				"is_shared": 0,
			}
		).insert()
		self.assertEqual(own.church, self.branch_a)

		frappe.set_user(self.manager_b)
		visible = frappe.get_list("Belief", pluck="name")
		self.assertIn(shared.name, visible)
		self.assertNotIn(own.name, visible, "a belief kept to one church stays there")

	def test_a_shared_ministry_reaches_every_church_with_its_joint_total(self):
		"""Sharing a ministry shares what it costs, which is the point of running one together.

		``total_expenses`` is the combined figure by design; which church spent
		what comes from the Expense rows, each of which keeps its own church.
		"""
		ministry = ensure(
			"Ministry",
			{"ministry_name": "_Test Joint Ministry"},
			{"ministry_name": "_Test Joint Ministry", "church": self.branch_a},
		)
		fund = ensure("Fund", {"fund": "_Test Joint Fund"}, {"fund": "_Test Joint Fund", "is_shared": 1})
		expense_type = ensure(
			"Expense Type", {"type": "_Test Joint Type"}, {"type": "_Test Joint Type", "fund": fund}
		)
		for church, amount in ((self.branch_a, 30), (self.branch_b, 12)):
			frappe.get_doc(
				{
					"doctype": "Expense",
					"title": f"_Test Joint Spend {church}",
					"type": expense_type,
					"amount": amount,
					"date": "2032-02-02",
					"church": church,
					"ministry": ministry,
				}
			).insert(ignore_permissions=True).submit()

		shared = self.share("Ministry", ministry)
		self.assertEqual(shared.church, SHARED)
		self.assertEqual(shared.shared_by_church, self.branch_a)
		self.assertEqual(frappe.db.get_value("Ministry", ministry, "total_expenses"), 42)

		frappe.set_user(self.manager_b)
		self.assertIn(ministry, frappe.get_list("Ministry", pluck="name"))

	def test_unsharing_returns_the_record_to_the_church_that_shared_it(self):
		song = ensure("Song", {"title": "_Test Returned Song"}, {"title": "_Test Returned Song"})
		frappe.db.set_value("Song", song, "church", self.branch_a)
		self.share("Song", song)

		# a manager of a different church puts it back
		frappe.set_user(self.manager_b)
		doc = frappe.get_doc("Song", song)
		doc.is_shared = 0
		doc.save(ignore_permissions=True)

		self.assertEqual(doc.church, self.branch_a, "the record should go home, not to whoever saved it")

	def test_sharing_is_refused_where_it_is_not_offered(self):
		"""A doctype outside SHAREABLE_DOCTYPES keeps its church whatever is set on it."""
		request = make_prayer_request("_Test Not Shareable", self.branch_a)
		request.set("is_shared", 1)
		request.save(ignore_permissions=True)
		self.assertEqual(request.church, self.branch_a)

	def test_a_new_record_arrives_with_its_church_filled_in(self):
		"""An empty church means shared, so it must never also mean "not saved yet"."""
		frappe.set_user(self.manager_a)
		song = frappe.get_doc({"doctype": "Song", "title": "_Test Defaulted Song"}).insert()
		self.assertEqual(song.church, self.branch_a)
		self.assertFalse(song.is_shared)

	def book(self, room, hour, person):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": person,
				"purpose": "_Test Booking",
				"start_datetime": f"2031-03-01 {hour:02d}:00:00",
				"end_datetime": f"2031-03-01 {hour + 1:02d}:00:00",
			}
		).insert(ignore_permissions=True)

	def test_bookings_of_a_shared_room_are_visible_to_every_church(self):
		"""Otherwise a branch reads an empty diary and learns of the clash only on save."""
		room = ensure(
			"Room", {"room_name": "_Test Shared Hall"}, {"room_name": "_Test Shared Hall", "is_bookable": 1}
		)
		self.share("Room", room)
		person = make_person("_Test Booker", "One", church=self.branch_a)
		booking = self.book(room, 9, person.name)
		self.assertEqual(booking.church, "", "a booking of a shared room is shared with it")

		frappe.set_user(self.manager_b)
		self.assertIn(booking.name, frappe.get_list("Room Booking", pluck="name"))

	def test_a_second_church_cannot_book_over_a_shared_room(self):
		room = ensure(
			"Room", {"room_name": "_Test Clash Hall"}, {"room_name": "_Test Clash Hall", "is_bookable": 1}
		)
		self.share("Room", room)
		self.book(room, 14, make_person("_Test Booker", "Two", church=self.branch_a).name)

		with self.assertRaises(ValidationError):
			self.book(room, 14, make_person("_Test Booker", "Three", church=self.branch_b).name)

	def test_bookings_of_an_unshared_room_stay_with_their_church(self):
		room = ensure(
			"Room",
			{"room_name": "_Test Private Hall"},
			{"room_name": "_Test Private Hall", "is_bookable": 1, "church": self.branch_a},
		)
		booking = self.book(room, 11, make_person("_Test Booker", "Four", church=self.branch_a).name)
		self.assertEqual(booking.church, self.branch_a)

		frappe.set_user(self.manager_b)
		self.assertNotIn(booking.name, frappe.get_list("Room Booking", pluck="name"))

	def give(self, church, first_name):
		"""A submitted Collection with one donation, so the giver has a statement to issue."""
		person = make_person("_Test Giver", first_name, church=church)
		fund = ensure(
			"Fund", {"fund": "_Test Statement Fund"}, {"fund": "_Test Statement Fund", "is_shared": 1}
		)
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": "2033-03-05",
				"church": church,
				"expected_total": 50,
				"donations": [
					{
						"person": person.name,
						"fund": fund,
						"amount": 50,
						"payment_type": frappe.db.get_value("Payment Type", {}, "name"),
					}
				],
			}
		).insert(ignore_permissions=True)
		collection.submit()
		return person.name

	def test_statements_are_issued_only_for_the_issuers_own_givers(self):
		"""A branch issuing statements used to issue every church's, under its own church.

		The statement takes its church from its person, which a branch cannot
		read, so another church's statement landed in the branch that issued it,
		carrying a stranger's giving history with it.
		"""
		mine = self.give(self.branch_a, "Mine")
		theirs = self.give(self.branch_b, "Theirs")

		frappe.set_user(self.manager_a)
		self.assertEqual(get_givers("2033-01-01", "2033-12-31"), [mine])

		generate_statements("2033-01-01", "2033-12-31")
		issued = frappe.get_all(
			"Giving Statement", filters={"from_date": "2033-01-01"}, fields=["person", "church"]
		)
		self.assertEqual([row.person for row in issued], [mine])
		self.assertNotIn(theirs, [row.person for row in issued])
		self.assertEqual([row.church for row in issued], [self.branch_a])

	def test_a_budget_is_not_warned_about_another_church_s_dates(self):
		"""The overlap warning names the budgets it found, so it has to stay in scope."""
		fund = ensure("Fund", {"fund": "_Test Overlap Fund"})
		expense_type = ensure(
			"Expense Type", {"type": "_Test Overlap Type"}, {"type": "_Test Overlap Type", "fund": fund}
		)
		lines = [{"expense_type": expense_type, "budgeted_amount": 10}]
		frappe.get_doc(
			{
				"doctype": "Budget",
				"title": "_Test Overlap B",
				"start_date": "2032-01-01",
				"end_date": "2032-12-31",
				"church": self.branch_b,
				"lines": lines,
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self.manager_a)
		frappe.clear_messages()
		frappe.get_doc(
			{
				"doctype": "Budget",
				"title": "_Test Overlap A",
				"start_date": "2032-06-01",
				"end_date": "2032-09-30",
				"lines": lines,
			}
		).insert()

		warnings = [str(message.get("message")) for message in frappe.local.message_log]
		self.assertEqual(
			[warning for warning in warnings if "overlap" in warning],
			[],
			"branch A was warned about a budget belonging to branch B",
		)

	def test_a_budget_counts_branches_only_when_asked(self):
		"""A budget tracks its own church until someone ticks Include Branch Churches."""
		fund = ensure("Fund", {"fund": "_Test Roll Up Fund"}, {"fund": "_Test Roll Up Fund", "is_shared": 1})
		expense_type = ensure(
			"Expense Type", {"type": "_Test Roll Up"}, {"type": "_Test Roll Up", "fund": fund}
		)
		for church, amount in ((self.root, 100), (self.branch_a, 40)):
			frappe.get_doc(
				{
					"doctype": "Expense",
					"title": f"_Test Roll Up {church}",
					"type": expense_type,
					"amount": amount,
					"date": "2031-06-15",
					"church": church,
				}
			).insert(ignore_permissions=True).submit()

		own = get_expense_totals("2031-01-01", "2031-12-31", church=self.root)
		self.assertEqual(own.get(expense_type), 100, "by default a budget tracks only its own church")

		consolidated = get_expense_totals("2031-01-01", "2031-12-31", church=self.root, include_branches=True)
		self.assertEqual(consolidated.get(expense_type), 140, "asked to, it counts the branches too")

		branch = get_expense_totals("2031-01-01", "2031-12-31", church=self.branch_a, include_branches=True)
		self.assertEqual(branch.get(expense_type), 40, "a branch with no branches of its own counts itself")


class TestSingleChurchDesk(FrappeTestCase):
	"""What the desk is told while the switch is off, which every `!single_church` field reads."""

	def setUp(self):
		ensure_root_church()
		force_single_church()

	def boot(self):
		bootinfo = frappe._dict()
		extend_bootinfo(bootinfo)
		return bootinfo.churchit

	def test_one_church_is_reported_so_no_per_church_field_shows(self):
		boot = self.boot()
		self.assertFalse(boot["multi_church"])
		self.assertTrue(
			boot["single_church"],
			"with the switch off the per-church rows of a settings page would show",
		)
		self.assertIsNone(boot["church"])
		self.assertIsNone(boot["churches"])

	def test_the_switch_on_stops_reporting_one_church_to_an_unrestricted_user(self):
		set_multi_church(True)

		self.assertFalse(self.boot()["single_church"])


class TestMultiChurchTransition(FrappeTestCase):
	"""The one-way switch: it stamps every existing record and scopes every user.

	Untested until now, and it is the step that cannot be undone.
	"""

	def setUp(self):
		force_single_church()
		self.root = ensure_root_church()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_it_stamps_the_root_church_on_records_saved_before_the_switch(self):
		person = make_person("_Test Before", "Switch")
		fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Before Switch"}).insert(
			ignore_permissions=True
		)
		self.assertFalse(person.church)

		set_multi_church(True)

		self.assertEqual(frappe.db.get_value("Person", person.name, "church"), self.root)
		self.assertEqual(frappe.db.get_value("Fund", fund.name, "church"), self.root)

	def test_a_record_shared_before_the_switch_ends_up_shared_not_unstamped(self):
		"""An empty church means shared, and the app compares it against the empty string."""
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Shared Before Switch", "is_shared": 1}
		).insert(ignore_permissions=True)

		set_multi_church(True)

		self.assertEqual(frappe.db.get_value("Sermon", sermon.name, "church"), SHARED)

	def test_every_enabled_user_is_scoped_to_the_root_with_branches_hidden(self):
		user = ensure_user("_test_transition_user@example.com", "Transition")

		set_multi_church(True)

		(permission,) = user_church_permissions(user)
		self.assertEqual(permission.for_value, self.root)
		self.assertEqual(permission.hide_descendants, 1)

	def test_it_cannot_be_switched_off_once_a_branch_exists(self):
		set_multi_church(True)
		make_branch("_Test Locking Branch", "TLB")

		with self.assertRaises(ValidationError):
			set_multi_church(False)
