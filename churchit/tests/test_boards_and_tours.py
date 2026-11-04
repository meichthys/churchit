# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Kanban boards and 'Take the Tour' are shipped by file, and both fail silently when a file is wrong.

Frappe 16.54 syncs a board only from `<module>/doctype/<doctype>/kanban_board/`, and a status that
has no column leaves its cards off the board. One shared script adds 'Take the Tour' to every form
that has a tour, so a second menu item or a second tour for one doctype would show twice or never.
"""

import glob
import json
import os
from collections import Counter
from itertools import chain

import frappe
from frappe.desk.doctype.kanban_board.kanban_board import get_kanban_board_data
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches
from churchit.tests.test_desk_ui_hygiene import (
	APP_DIR,
	TEXT_LIST_TYPES,
	assert_list_ratchet,
	doctype_files,
	get_default_list_filters,
	get_list_script,
)
from churchit.tests.test_workspace_hygiene import get_conditions, shipped_workspaces

TOUR_SCRIPT = os.path.join("public", "js", "help_icon_on_form.js")

TOURS_THAT_ASK_FOR_A_MISSING_NAME = {}


def shipped_boards() -> list[tuple[str, dict]]:
	"""(path relative to the app, board JSON) for every Kanban Board file under the app."""
	paths = sorted(glob.glob(os.path.join(APP_DIR, "**", "kanban_board", "*.json"), recursive=True))
	return [(os.path.relpath(path, APP_DIR), json.load(open(path))) for path in paths]


def get_board_fieldnames(board: dict) -> list[str]:
	return [
		row["fieldname"]
		for table in ("card_fields", "preview_fields", "group_by_fields")
		for row in board[table]
	]


class TestShippedBoards(FrappeTestCase):
	def test_there_are_boards_for_care_and_tasks(self):
		self.assertEqual(
			sorted(board["name"] for _path, board in shipped_boards()), ["Care Requests", "Church Tasks"]
		)

	def test_a_board_sits_where_frappe_syncs_it(self):
		"""`sync.get_doc_files` globs `doctype/*/kanban_board/*.json` in each module folder and nowhere else."""
		for path, board in shipped_boards():
			module = frappe.scrub(board["module"])
			expected = os.path.join(
				module,
				"doctype",
				frappe.scrub(board["reference_doctype"]),
				"kanban_board",
				f"{frappe.scrub(board['name'])}.json",
			)
			self.assertEqual(path, expected)
			self.assertEqual(
				frappe.db.get_value("DocType", board["reference_doctype"], "module"), board["module"]
			)

	def test_a_board_is_standard_public_and_v2(self):
		"""Frappe refuses to sync a standard board that is private, classic or has no module."""
		for _path, board in shipped_boards():
			self.assertEqual(
				(board["is_standard"], board["use_kanban_v2"], board["private"]), ("Yes", 1, 0), board["name"]
			)
			self.assertEqual(board["name"], board["kanban_board_name"])

	def test_every_status_has_a_column(self):
		"""A status without a column leaves its cards off the board; a column that is no status never fills."""
		for _path, board in shipped_boards():
			field = frappe.get_meta(board["reference_doctype"]).get_field(board["field_name"])
			options = [option for option in field.options.split("\n") if option]
			self.assertEqual([column["column_name"] for column in board["columns"]], options, board["name"])

	def test_cards_show_short_fields_the_doctype_has(self):
		for _path, board in shipped_boards():
			meta = frappe.get_meta(board["reference_doctype"])
			for fieldname in get_board_fieldnames(board):
				field = meta.get_field(fieldname)
				self.assertTrue(field, f"{board['name']}: no field {fieldname}")
				self.assertNotIn(
					field.fieldtype, TEXT_LIST_TYPES, f"{board['name']}: {fieldname} is long text"
				)

	def test_a_card_is_titled_by_a_text_field(self):
		"""Kanban v2 skips a title field that is not Data, Text, Small Text or Text Editor."""
		for _path, board in shipped_boards():
			field = frappe.get_meta(board["reference_doctype"]).get_field(board["title_field"])
			self.assertIn(field.fieldtype, ("Data", "Text", "Small Text", "Text Editor"), board["name"])

	def test_a_board_shortcut_counts_what_the_list_and_the_board_open_on(self):
		"""The count beside 'Care Board' matches the 'Open Care Requests' beside it and the cards on the board.

		Kanban v2 clears the route options of a shortcut and reads only the board's own filters.
		"""
		scripts = {data["name"]: get_list_script(path) for path, data in doctype_files()}
		boards = {board["name"]: board for _path, board in shipped_boards()}
		found = {}
		for workspace in shipped_workspaces():
			for row in workspace.get("shortcuts", []):
				if row.get("doc_view") != "Kanban":
					continue
				board = boards[row["kanban_board"]]
				self.assertEqual(board["reference_doctype"], row["link_to"], row["label"])
				default = get_conditions(get_default_list_filters(scripts.get(row["link_to"], "")))
				if get_conditions(row["stats_filter"]) != default:
					found[row["label"]] = row["stats_filter"]
				if get_conditions(board["filters"]) != default:
					found[board["name"]] = board["filters"]
		self.assertEqual(found, {})

	def test_each_board_has_a_workspace_shortcut(self):
		shortcuts = {
			row["kanban_board"]
			for workspace in shipped_workspaces()
			for row in workspace.get("shortcuts", [])
			if row.get("doc_view") == "Kanban"
		}
		self.assertEqual(shortcuts, {board["name"] for _path, board in shipped_boards()})


def load_board(user: str, name: str, doctype: str) -> dict:
	"""{column: card names} that *user* gets from the board, as the page asks for it."""
	frappe.set_user(user)
	frappe.local.form_dict = frappe._dict(
		board_name=name, doctype=doctype, fields=json.dumps(["name", "status"]), filters="[]"
	)
	try:
		columns = get_kanban_board_data()["columns"]
	finally:
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	return {column: get_card_names(data["cards"]) for column, data in columns.items()}


def get_card_names(cards: dict | None) -> list[str]:
	"""The names in the compressed cards that Frappe sends: {"keys": [...], "values": [[...], ...]}."""
	if not cards:
		return []
	return [row[cards["keys"].index("name")] for row in cards["values"]]


class TestCareBoard(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.category = ensure("Care Request Type", {"type": "_Test Board Need"})
		cls.manager = ensure_user("_test_board_manager@example.com", "Board Manager", ["Church Manager"])
		cls.check_in = ensure_user("_test_board_check_in@example.com", "Board Check In", ["Church Check-In"])

	def make_request(self, person, status="Requested", **values):
		return frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": person.name,
				"category": self.category,
				"description": "_Test board need",
				"status": status,
				**values,
			}
		).insert(ignore_permissions=True)

	def test_cards_sit_in_the_column_of_their_status_and_a_finished_request_is_off_the_board(self):
		person = make_person("_Test Board", "Person")
		requested = self.make_request(person)
		working = self.make_request(person, "In Progress")
		finished = [self.make_request(person, "Resolved").name, self.make_request(person, "Closed").name]

		columns = load_board(self.manager, "Care Requests", "Care Request")

		self.assertEqual(list(columns), ["Requested", "Triaged", "In Progress", "Resolved"])
		self.assertIn(requested.name, columns["Requested"])
		self.assertIn(working.name, columns["In Progress"])
		self.assertFalse(set(finished) & set(chain.from_iterable(columns.values())))

	def test_a_role_that_cannot_read_care_requests_gets_no_cards(self):
		self.make_request(make_person("_Test Board", "Hidden"))

		with self.assertRaises(frappe.PermissionError):
			load_board(self.check_in, "Care Requests", "Care Request")

	def test_a_branch_user_sees_only_the_cards_of_their_church(self):
		_root, branch_a, branch_b = make_two_churches()
		manager_a = ensure_user("_test_board_manager_a@example.com", "Board A", ["Church Manager"])
		set_user_church(manager_a, branch_a)
		mine = self.make_request(make_person("_Test Board", "Mine", church=branch_a), church=branch_a)
		theirs = self.make_request(make_person("_Test Board", "Theirs", church=branch_b), church=branch_b)

		cards = list(chain.from_iterable(load_board(manager_a, "Care Requests", "Care Request").values()))

		self.assertIn(mine.name, cards)
		self.assertNotIn(theirs.name, cards)


class TestTakeTheTour(FrappeTestCase):
	def test_a_doctype_has_one_tour(self):
		"""The shared script picks a tour by the doctype it explains, so two tours would hide one."""
		counts = Counter(
			tour.reference_doctype
			for tour in frappe.get_all(
				"Form Tour",
				filters={
					"ui_tour": 0,
					"reference_doctype": ["is", "set"],
					"module": ["in", frappe.get_module_list("churchit")],
				},
				fields=["name", "reference_doctype"],
			)
		)
		self.assertEqual({doctype: count for doctype, count in counts.items() if count > 1}, {})

	def test_a_tour_asks_for_a_name_only_where_the_form_has_a_name_field(self):
		"""Frappe draws the name field on a new form named by Prompt or `name`, so on any other form that first step shows nothing."""
		found = {
			tour.name: tour.reference_doctype
			for tour in frappe.get_all(
				"Form Tour",
				filters={
					"ui_tour": 0,
					"include_name_field": 1,
					"module": ["in", frappe.get_module_list("churchit")],
				},
				fields=["name", "reference_doctype"],
			)
			if (frappe.get_meta(tour.reference_doctype).autoname or "").lower() not in ("prompt", "name")
		}
		assert_list_ratchet(
			self,
			found,
			TOURS_THAT_ASK_FOR_A_MISSING_NAME,
			"A tour asks for a document name on a form that has none",
		)

	def test_one_script_adds_take_the_tour(self):
		"""A form script that adds its own item would give the menu two."""
		found = []
		for path in glob.glob(os.path.join(APP_DIR, "**", "*.js"), recursive=True):
			relative = os.path.relpath(path, APP_DIR)
			if relative.startswith(("public/dist", "node_modules")):
				continue
			if "Take the Tour" in open(path).read():
				found.append(relative)
		self.assertEqual(found, [TOUR_SCRIPT])
