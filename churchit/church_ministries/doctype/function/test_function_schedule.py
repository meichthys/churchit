# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Service plan details on a Function's schedule: song keys, arrangements, headers and team notes."""

import frappe
from frappe.utils import add_days, getdate

from churchit.church_ministries.doctype.function.function import (
	apply_template,
	get_schedule_rows,
	get_team_schedule,
)
from churchit.church_ministries.recurrence import create_occurrence
from churchit.church_website.published_fields import published_field_map
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)


def make_planned_song(title, **values):
	return frappe.get_doc(
		{
			"doctype": "Song",
			"title": title,
			"default_key": "G",
			"arrangements": [
				{"arrangement_name": "_Test Acoustic", "song_key": "D"},
				{"arrangement_name": "_Test Full Band"},
			],
			**values,
		}
	).insert(ignore_permissions=True)


class TestScheduleSongs(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.song = make_planned_song("_Test Plan Hymn")

	def plan(self, **row):
		return make_function(
			"_Test Plan Service", schedule=[{"item_type": "Song", "item": self.song.name, **row}]
		)

	def test_an_arrangement_the_song_does_not_have_fails_to_save(self):
		with self.assertRaises(frappe.ValidationError):
			self.plan(arrangement="_Test Unknown Arrangement")

	def test_the_key_comes_from_the_arrangement_then_the_songs_default(self):
		self.assertEqual(self.plan(arrangement="_Test Acoustic").schedule[0].song_key, "D")
		self.assertEqual(self.plan(arrangement="_Test Full Band").schedule[0].song_key, "G")
		self.assertEqual(self.plan().schedule[0].song_key, "G")

	def test_a_key_set_on_the_row_is_kept(self):
		self.assertEqual(self.plan(arrangement="_Test Acoustic", song_key="E").schedule[0].song_key, "E")

	def test_a_row_that_is_not_a_song_is_left_alone(self):
		function = make_function(
			"_Test Plan Welcome", schedule=[{"description": "Welcome", "arrangement": "_Test Anything"}]
		)
		self.assertFalse(function.schedule[0].song_key)

	def test_an_unchanged_row_is_not_checked_again(self):
		function = self.plan(arrangement="_Test Full Band")
		song = frappe.get_doc("Song", self.song.name)
		song.arrangements[1].arrangement_name = "_Test Renamed Band"
		song.save(ignore_permissions=True)

		# An attendance save must not trip on a song edited since.
		function.headcount = 40
		function.save(ignore_permissions=True)

		function.schedule[0].song_key = None
		with self.assertRaises(frappe.ValidationError):
			function.save(ignore_permissions=True)

	def test_a_new_arrangement_or_song_takes_its_own_key(self):
		function = self.plan(arrangement="_Test Acoustic")

		function.schedule[0].arrangement = "_Test Full Band"
		function.save(ignore_permissions=True)
		self.assertEqual(function.schedule[0].song_key, "G")

		function.schedule[0].item = make_planned_song("_Test Plan Other Hymn", default_key="Bb").name
		function.save(ignore_permissions=True)
		self.assertEqual(function.schedule[0].song_key, "Bb")

	def test_a_key_typed_with_the_new_arrangement_is_kept(self):
		function = self.plan(arrangement="_Test Acoustic")

		function.schedule[0].arrangement = "_Test Full Band"
		function.schedule[0].song_key = "A"
		function.save(ignore_permissions=True)
		self.assertEqual(function.schedule[0].song_key, "A")

	def test_a_recurring_series_continues_after_an_arrangement_is_renamed(self):
		template = self.plan(arrangement="_Test Full Band")
		song = frappe.get_doc("Song", self.song.name)
		song.arrangements[1].arrangement_name = "_Test Renamed Band"
		song.save(ignore_permissions=True)

		occurrence = create_occurrence(template, add_days(getdate(template.start_date), 7))

		self.assertEqual(occurrence.schedule[0].arrangement, "_Test Full Band")


class TestScheduleSongChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.song_of_a = make_planned_song("_Test Church A Hymn", church=cls.branch_a)
		cls.manager_b = ensure_user("_test_plan_manager_b@example.com", "PlanB", roles=("Church Manager",))
		make_person("PlanB", "Manager", church=cls.branch_b, user=cls.manager_b)

	def plan_in_b(self, song):
		frappe.set_user(self.manager_b)
		try:
			return make_function(
				"_Test Plan B Service",
				church=self.branch_b,
				schedule=[{"item_type": "Song", "item": song, "arrangement": "_Test Acoustic"}],
			)
		finally:
			frappe.set_user("Administrator")

	def test_another_churches_song_fails_to_save(self):
		with self.assertRaises(frappe.PermissionError):
			self.plan_in_b(self.song_of_a.name)

	def test_a_saved_row_of_another_type_cannot_become_another_churches_song(self):
		if not frappe.db.exists("Tag", self.song_of_a.name):
			frappe.get_doc({"doctype": "Tag", "name": self.song_of_a.name}).insert(ignore_permissions=True)
		frappe.set_user(self.manager_b)
		try:
			function = make_function(
				"_Test Plan B Tag Row",
				church=self.branch_b,
				schedule=[{"item_type": "Tag", "item": self.song_of_a.name}],
			)
			function.schedule[0].item_type = "Song"
			with self.assertRaises(frappe.PermissionError):
				function.save()
		finally:
			frappe.set_user("Administrator")

	def test_a_shared_song_saves(self):
		self.song_of_a.db_set("is_shared", 1)
		self.song_of_a.db_set("church", "")

		self.assertEqual(self.plan_in_b(self.song_of_a.name).schedule[0].song_key, "D")


class TestScheduleRows(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.song = make_planned_song("_Test Rows Hymn")
		cls.function = make_function(
			"_Test Rows Service",
			start_date="2031-06-01",
			schedule=[
				{"start": "2031-06-01 10:00:00", "description": "_Test Opening", "is_header": 1},
				{
					"start": "2031-06-01 10:05:00",
					"item_type": "Song",
					"item": cls.song.name,
					"arrangement": "_Test Acoustic",
					"notes": "_Test team note: capo 2",
				},
				{"description": "Prayer", "notes": "_Test team note: dim the lights"},
			],
		)

	def test_the_default_rows_hold_no_team_details(self):
		rows = get_schedule_rows(self.function)

		self.assertEqual(
			[(row.time, row.title, row.detail, row.is_header) for row in rows],
			[
				("10:00 AM", "_Test Opening", None, 1),
				("10:05 AM", "_Test Rows Hymn", "Song", 0),
				(None, "Prayer", None, 0),
			],
		)
		self.assertTrue(all(set(row) == {"time", "title", "detail", "is_header"} for row in rows))

	def test_the_team_schedule_adds_the_key_arrangement_and_notes(self):
		member = make_person("_Test Rows", "Member")
		position = make_team_position("_Test Rows Singer", [member.name])
		make_team_assignment(self.function.name, position.name, member.name)

		rows = get_team_schedule(self.function, member.name).rows

		self.assertEqual(
			[(row.key, row.arrangement, row.notes) for row in rows],
			[
				(None, None, None),
				("D", "_Test Acoustic", "_Test team note: capo 2"),
				(None, None, "_Test team note: dim the lights"),
			],
		)

	def test_the_bulletin_prints_headers_as_headings_and_never_team_notes(self):
		bulletin = frappe.get_doc(
			{"doctype": "Bulletin", "function": self.function.name, "show_order_of_worship": 1}
		).insert(ignore_permissions=True)

		html = frappe.get_print("Bulletin", bulletin.name, "Bulletin")

		self.assertIn('<th colspan="2">_Test Opening</th>', html)
		self.assertIn("_Test Rows Hymn", html)
		self.assertNotIn("_Test team note", html)


class TestTeamSchedule(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.member = make_person("_Test Plan", "Member")
		cls.greeter = make_team_position("_Test Plan Greeter", [cls.member.name])
		cls.usher = make_team_position("_Test Plan Usher", [cls.member.name])
		cls.function = make_function(
			"_Test Plan Team Service",
			start_date=add_days(getdate(), 3),
			schedule=[{"description": "Welcome", "notes": "_Test doors open early"}],
			team_needs=[
				{"position": cls.greeter.name, "quantity": 2, "notes": "_Test greeter note"},
				{"position": cls.usher.name, "quantity": 1, "notes": "_Test usher note"},
			],
		)

	def test_a_member_sees_team_notes_and_only_the_need_note_of_their_own_position(self):
		make_team_assignment(self.function.name, self.greeter.name, self.member.name)

		schedule = get_team_schedule(self.function, self.member.name)

		self.assertEqual(schedule.rows[0].notes, "_Test doors open early")
		self.assertEqual(
			[(note.position, note.notes) for note in schedule.need_notes],
			[(self.greeter.title, "_Test greeter note")],
		)

	def test_a_declined_position_shows_no_need_note_and_no_team_details(self):
		make_team_assignment(self.function.name, self.usher.name, self.member.name, status="Declined")

		schedule = get_team_schedule(self.function, self.member.name)

		self.assertEqual(schedule.need_notes, [])
		self.assertEqual(schedule.rows, get_schedule_rows(self.function))
		self.assertNotIn("notes", schedule.rows[0])

	def test_the_team_details_carry_the_members_badge(self):
		published = published_field_map()

		for doctype, fieldname in (
			("Function Schedule", "song_key"),
			("Function Schedule", "arrangement"),
			("Function Schedule", "notes"),
			("Song Media", "file"),
		):
			sources = published.get(doctype, {}).get(fieldname, [])
			self.assertIn(("ministry-team", "members"), [(row["route"], row["access"]) for row in sources])

	def test_fill_from_template_copies_the_need_notes(self):
		copied = apply_template(self.function.name, start_date=str(add_days(getdate(), 10)))

		self.assertEqual(
			[need["notes"] for need in copied["team_needs"]], ["_Test greeter note", "_Test usher note"]
		)

	def test_the_ministry_team_page_shows_the_plan_details(self):
		song = make_planned_song("_Test Plan Page Hymn")
		function = make_function(
			"_Test Plan Page Service",
			start_date=add_days(getdate(), 3),
			schedule=[
				{"description": "_Test Plan Heading", "is_header": 1},
				{
					"item_type": "Song",
					"item": song.name,
					"arrangement": "_Test Acoustic",
					"notes": "_Test capo 2",
				},
			],
			team_needs=[{"position": self.greeter.name, "notes": "_Test greeters by the door"}],
		)
		make_team_assignment(function.name, self.greeter.name, self.member.name)
		schedules = {function.name: get_team_schedule(function, self.member.name)}

		html = frappe.render_template(
			"templates/includes/ministry_team_schedule.html",
			{"schedules": schedules, "row": frappe._dict(function=function.name)},
		)

		for shown in ("<strong>_Test Plan Heading</strong>", "_Test Acoustic", "Key of D", "_Test capo 2"):
			self.assertIn(shown, html)
		self.assertIn("_Test greeters by the door", html)
