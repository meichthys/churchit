# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import update_doc
from frappe.utils import add_days, getdate

from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_person,
	make_team_position,
	make_two_churches,
)

POSITION = "Ministry Team Position"


class TestMinistryTeamPosition(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.clear_messages()

	def warned_about(self):
		return [
			str(message) for message in frappe.message_log if "checks this position needs" in str(message)
		]

	def test_the_title_names_the_ministry(self):
		person = make_person("_Test Position", "Person").name
		position = make_team_position("_Test Sound", [person], ministry_name="_Test Worship")
		self.assertEqual(position.title, "_Test Sound (_Test Worship)")

	def test_roster_rows_from_the_old_multiselect_field_load_in_the_table(self):
		person = make_person("_Test Roster", "Kept").name
		position = make_team_position("_Test Kept Roster", [])
		# A row as the Table MultiSelect field saved it, before Most Times a Month existed.
		frappe.db.sql(
			"""insert into `tabMinistry Team Position Person` (name, parent, parenttype, parentfield, idx, person)
			values (%s, %s, %s, 'people', 1, %s)""",
			(frappe.generate_hash(length=10), position.name, POSITION, person),
		)
		frappe.clear_cache(doctype=POSITION)

		[row] = frappe.get_doc(POSITION, position.name).people
		self.assertEqual((row.person, row.max_times_per_month), (person, 0))

	def test_adding_someone_without_the_checks_warns_but_is_kept(self):
		training = ensure("Background Check Type", {"type": "_Test Roster Training"})
		trained = make_person("_Test Roster", "Trained").name
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": trained,
				"check_type": training,
				"status": "Cleared",
				"completed_on": getdate(),
				"expires_on": add_days(getdate(), 365),
			}
		).insert(ignore_permissions=True)
		untrained = make_person("_Test Roster", "Untrained").name

		position = make_team_position(
			"_Test Nursery",
			[trained, untrained],
			needs_background_check=1,
			required_checks=[{"check_type": training}],
		)

		self.assertEqual(len(position.people), 2)
		warnings = self.warned_about()
		self.assertTrue(any("_Test Roster Untrained" in warning for warning in warnings), warnings)
		self.assertFalse(any("_Test Roster Trained" in warning for warning in warnings), warnings)

	def test_only_people_newly_added_are_warned_about(self):
		first = make_person("_Test Roster", "First").name
		position = make_team_position("_Test Usher", [first], needs_background_check=1)
		frappe.clear_messages()

		position.append("people", {"person": make_person("_Test Roster", "Second").name})
		position.save(ignore_permissions=True)

		warnings = self.warned_about()
		self.assertTrue(any("_Test Roster Second" in warning for warning in warnings), warnings)
		self.assertFalse(any("_Test Roster First" in warning for warning in warnings), warnings)

	def test_a_position_without_checks_warns_about_nobody(self):
		make_team_position("_Test Greeter", [make_person("_Test Roster", "Greeter").name])
		self.assertEqual(self.warned_about(), [])


class TestMinistryTeamPositionChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_position_a@example.com", "Coordinator", roles=("Church Manager",))
		make_person("_Test Position", "Coordinator", church=cls.branch_a, user=cls.manager_a)
		cls.ministry_a, cls.ministry_b, cls.shared = (
			ensure("Ministry", {"ministry_name": name}, {"ministry_name": name, **values})
			for name, values in (
				("_Test Position A", {"church": cls.branch_a}),
				("_Test Position B", {"church": cls.branch_b}),
				("_Test Position Shared", {"church": cls.branch_b, "is_shared": 1}),
			)
		)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_only_the_ministrys_church_adds_a_position_or_moves_one(self):
		"""Frappe checks the church the caller sends, before the position takes the ministry's church."""
		theirs = make_team_position("_Test Their Usher", [], ministry_name="_Test Position B").name
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc(POSITION, position_name="_Test Usher", ministry=self.ministry_b).insert()
		for ministry in (self.ministry_a, self.shared):
			frappe.new_doc(POSITION, position_name="_Test Usher", ministry=ministry).insert()

		frappe.local.form_dict = frappe._dict(
			data=json.dumps({"ministry": self.ministry_a, "church": self.branch_a})
		)
		with self.assertRaises(frappe.PermissionError):
			update_doc(POSITION, theirs)
		self.assertEqual(frappe.db.get_value(POSITION, theirs, "church"), self.branch_b)
