# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe

from churchit.church_ministries.report.ministry_team_grid import ministry_team_grid
from churchit.church_ministries.report.ministry_team_schedule import ministry_team_schedule
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)

RANGE = {"from_date": "2031-07-01", "to_date": "2031-07-31"}


class TestMinistryTeamGrid(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		people = [make_person("_Test Grid", name).name for name in ("Ann", "Ben", "Cal")]
		cls.singer = make_team_position("_Test Grid Singer", people, ministry_name="_Test Grid Music")
		cls.usher = make_team_position("_Test Grid Usher", people, ministry_name="_Test Grid Care")
		cls.first = make_function(
			"_Test Grid First",
			start_date="2031-07-06",
			team_needs=[
				{"position": cls.usher.name, "quantity": 2},
				{"position": cls.singer.name, "quantity": 1},
			],
		)
		cls.second = make_function(
			"_Test Grid Second",
			start_date="2031-07-13",
			team_needs=[{"position": cls.usher.name, "quantity": 1}],
		)
		for person, status in zip(people, ("Accepted", "Pending", "Declined"), strict=True):
			make_team_assignment(cls.first.name, cls.usher.name, person, status=status)
		make_team_assignment(cls.second.name, cls.singer.name, people[0])

	def run_grid(self, **filters):
		columns, data, message = ministry_team_grid.execute({**RANGE, **filters})
		return columns, {row.position: row for row in data}, message

	def test_a_row_for_each_position_and_a_column_for_each_function(self):
		columns, rows, message = self.run_grid()

		labels = [column["label"] for column in columns[2:]]
		self.assertEqual(len(labels), 2)
		self.assertIn("_Test Grid First", labels[0])
		self.assertIn("_Test Grid Second", labels[1])
		self.assertIsNone(message)

		first, second = (column["fieldname"] for column in columns[2:])
		usher, singer = rows[self.usher.name], rows[self.singer.name]
		self.assertEqual(
			usher[first], "_Test Grid Ann (Accepted), _Test Grid Ben (Pending), _Test Grid Cal (Declined)"
		)
		self.assertEqual(usher[second], "1 open")
		self.assertEqual(singer[first], "1 open")
		self.assertEqual(singer[second], "_Test Grid Ann (Pending)")
		self.assertEqual((usher._cells[second].function, usher._cells[second].open), (self.second.name, 1))
		self.assertEqual(
			[person["status"] for person in usher._cells[first].people], ["Accepted", "Pending", "Declined"]
		)

	def test_positions_are_grouped_by_ministry(self):
		_columns, data, _message = ministry_team_grid.execute(RANGE)
		ours = [
			(row.ministry, row.position)
			for row in data
			if row.position in (self.usher.name, self.singer.name)
		]
		self.assertEqual(
			ours, [(self.usher.ministry, self.usher.name), (self.singer.ministry, self.singer.name)]
		)

	def test_the_open_places_add_up_to_the_schedule_reports(self):
		for filters in ({}, {"ministry": self.usher.ministry}):
			_columns, data, _message = ministry_team_grid.execute({**RANGE, **filters})
			grid_open = sum(cell.open for row in data for cell in row._cells.values())
			_columns, schedule = ministry_team_schedule.execute({**RANGE, **filters})
			self.assertEqual(grid_open, sum(row.open for row in schedule))
			self.assertTrue(grid_open)

	def test_a_long_range_shows_the_first_columns_with_a_message(self):
		with mock.patch.object(ministry_team_grid, "MAX_COLUMNS", 1):
			columns, rows, message = self.run_grid()

		self.assertEqual(len(columns), 3)
		self.assertIn("_Test Grid First", columns[2]["label"])
		self.assertIn("2", message)
		self.assertEqual(list(rows[self.usher.name]._cells), [columns[2]["fieldname"]])


class TestMinistryTeamGridChurches(RollbackEachTest):
	def test_a_church_sees_only_its_own_functions(self):
		_root, branch_a, branch_b = make_two_churches()
		manager_b = ensure_user("_test_grid_b@example.com", "Grid B", roles=("Church Manager",))
		make_person("_Test Grid", "Manager B", church=branch_b, user=manager_b)
		functions = {}
		for key, church in (("A", branch_a), ("B", branch_b)):
			ministry = f"_Test Grid {key}"
			ensure("Ministry", {"ministry_name": ministry}, {"ministry_name": ministry, "church": church})
			position = make_team_position(ministry, [], ministry_name=ministry).name
			functions[key] = make_function(
				ministry,
				church=church,
				start_date="2031-07-06",
				team_needs=[{"position": position, "quantity": 1}],
			)

		frappe.set_user(manager_b)
		columns, _data, _message = ministry_team_grid.execute(RANGE)

		labels = [column["label"] for column in columns[2:]]
		self.assertTrue(any(functions["B"].title in label for label in labels), labels)
		self.assertFalse(any(functions["A"].title in label for label in labels), labels)
