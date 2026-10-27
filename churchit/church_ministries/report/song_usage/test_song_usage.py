# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.report.song_usage.song_usage import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


def make_song(title, ccli=None):
	return (
		frappe.get_doc({"doctype": "Song", "title": title, "ccli": ccli}).insert(ignore_permissions=True).name
	)


def sung(*songs):
	return [{"item_type": "Song", "item": song} for song in songs]


class TestSongUsage(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.hymn = make_song("_Test Usage Hymn", "1234567")
		cls.chorus = make_song("_Test Usage Chorus")
		make_function(
			"_Test Usage Sunday", start_date="2031-03-02", schedule=sung(cls.hymn, cls.chorus, cls.hymn)
		)
		make_function("_Test Usage Next Sunday", start_date="2031-03-09", schedule=sung(cls.hymn))
		make_function("_Test Usage Later", start_date="2031-04-06", schedule=sung(cls.chorus))

	def rows(self, **filters):
		_columns, data = execute({"from_date": "2031-03-01", "to_date": "2031-03-31", **filters})
		return [
			(row.song, row.ccli, row.times_used, str(row.last_used))
			for row in data
			if row.song in (self.hymn, self.chorus)
		]

	def test_counts_each_use_of_a_song_in_the_range_most_used_first(self):
		self.assertEqual(
			self.rows(),
			[(self.hymn, "1234567", 3, "2031-03-09"), (self.chorus, None, 1, "2031-03-02")],
		)

	def test_a_church_sees_only_the_songs_sung_at_its_own_functions(self):
		_root, branch, _other = make_two_churches()
		make_function(
			"_Test Usage Branch Sunday", start_date="2031-03-16", church=branch, schedule=sung(self.chorus)
		)

		self.assertEqual(self.rows(church=branch), [(self.chorus, None, 1, "2031-03-16")])


class TestSongUsageCopyTypes(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.song = make_song("_Test Copy Types Hymn")
		in_a = {"church": cls.branch_a}
		make_function(
			"_Test Copy Streamed", start_date="2031-07-06", streamed=1, schedule=sung(cls.song), **in_a
		)
		make_function(
			"_Test Copy Printed",
			start_date="2031-07-13",
			schedule=[{"item_type": "Song", "item": cls.song, "printed": 1}],
			**in_a,
		)
		make_function("_Test Copy Plain", start_date="2031-07-20", schedule=sung(cls.song), **in_a)
		cls.manager_a = ensure_user("_test_copy_manager_a@example.com", "CopyA", roles=("Church Manager",))
		make_person("CopyA", "Usage", church=cls.branch_a, user=cls.manager_a)
		cls.manager_b = ensure_user("_test_copy_manager_b@example.com", "CopyB", roles=("Church Manager",))
		make_person("CopyB", "Usage", church=cls.branch_b, user=cls.manager_b)

	def usage(self):
		_columns, data = execute({"from_date": "2031-07-01", "to_date": "2031-07-31"})
		return [
			(row.times_used, row.displayed, row.printed, row.streamed, row.recorded)
			for row in data
			if row.song == self.song
		]

	def test_counts_the_uses_of_each_copy_type(self):
		self.assertEqual(self.usage(), [(3, 3, 1, 1, 0)])

	def test_a_manager_sees_only_the_usage_of_their_own_church(self):
		frappe.set_user(self.manager_a)
		self.assertEqual(self.usage(), [(3, 3, 1, 1, 0)])

		frappe.set_user(self.manager_b)
		self.assertEqual(self.usage(), [])
