# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.utils import today

from churchit.church_ministries.page.check_in.check_in import check_in
from churchit.church_ministries.page.check_in.team import get_position, get_team
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)


class TestTeam(RollbackEachTest):
	"""The station's Team tab lists who serves at a Function and checks them in as volunteers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		root, _branch_a, branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.usher = make_person("Ulric", "_Test Team Usher", church=root).name
		cls.pending = make_person("Penny", "_Test Team Pending", church=root).name
		cls.declined = make_person("Dennis", "_Test Team Declined", church=root).name
		cls.position = make_team_position(
			"_Test Station Usher",
			[cls.usher, cls.pending, cls.declined],
			ministry_name="_Test Station Team Ministry",
			church=root,
		)
		cls.function = make_function("_Test Team Sunday", start_date=today(), church=root).name
		for person, status in ((cls.usher, "Accepted"), (cls.pending, "Pending"), (cls.declined, "Declined")):
			make_team_assignment(cls.function, cls.position.name, person, status=status)
		cls.volunteer = cls.bind_volunteer("_test_team_volunteer@example.com", "TeamA", root)
		cls.other_volunteer = cls.bind_volunteer("_test_team_other@example.com", "TeamB", branch_b)

	@classmethod
	def bind_volunteer(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Check-In",))
		make_person(first_name, "_Test Team Volunteer", church=church, user=user)
		return user

	def use_volunteer_tags(self):
		settings = frappe.get_single("Check-In Settings")
		settings.update({"name_tag_printing": "Browser", "security_codes": 1})
		settings.set("tag_formats", [{"check_in_kind": "Volunteer", "name_tag_format": "Volunteer Name Tag"}])
		settings.save(ignore_permissions=True)

	def test_the_team_lists_only_accepted_assignments_with_their_position(self):
		frappe.set_user(self.volunteer)
		team = get_team(self.function)

		self.assertEqual([row.person for row in team], [self.usher])
		self.assertEqual(team[0].person_name, "Ulric _Test Team Usher")
		self.assertEqual(team[0].position, self.position.title)
		self.assertFalse(team[0].is_checked_in)

	def test_a_volunteer_checked_in_from_the_team_tab_gets_no_code_and_a_tag_with_their_position(self):
		self.use_volunteer_tags()
		frappe.set_user(self.volunteer)
		with mock.patch.object(frappe.db, "commit"):
			result = check_in(self.function, [self.usher], print_tags=1, kind="Volunteer")

		(name,) = result["check_ins"]
		self.assertIsNone(frappe.db.get_value("Function Check-In", name, "security_code"))
		tags = result["print"]["content"]
		self.assertIn('class="name-tag volunteer"', tags)
		self.assertIn(frappe.utils.escape_html(self.position.title), tags)
		self.assertNotIn("name-tag pickup", tags)
		self.assertTrue(get_team(self.function)[0].is_checked_in)

	def test_get_position_names_only_an_accepted_assignment(self):
		self.assertEqual(get_position(self.usher, self.function), self.position.title)
		self.assertIsNone(get_position(self.pending, self.function))
		self.assertIsNone(get_position(self.declined, self.function))

	def test_another_churches_volunteer_cannot_read_the_team(self):
		frappe.set_user(self.other_volunteer)
		with self.assertRaises(frappe.PermissionError):
			get_team(self.function)

	def test_a_user_who_cannot_check_people_in_cannot_read_the_team(self):
		frappe.set_user(ensure_user("_test_team_member@example.com", "TeamMember"))
		with self.assertRaises(frappe.PermissionError):
			get_team(self.function)
