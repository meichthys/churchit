# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.followup import CARD, ON_SMART_LIST, OPEN
from churchit.church_scope import default_church, has_church_access

BOARD = "Kanban Board"


class FollowupWorkflow(Document):
	"""The steps a follow-up card moves through, who takes each one, and what starts a card by itself.

	Saving keeps the workflow's Kanban Board in step: one column per step, showing the open cards that
	are not snoozed.
	"""

	def _validate_links(self):
		# Frappe checks a Dynamic Link before any controller method runs, so each row needs its doctype first.
		for row in self.triggers:
			row.set_value_type()
		super()._validate_links()

	def validate(self):
		self.validate_steps()
		self.refuse_removing_steps_with_open_cards()
		for row in self.triggers:
			if row.trigger == ON_SMART_LIST:
				row.validate_smart_list()
		for row in self.actions:
			row.validate_action(self)

	def on_update(self):
		self.sync_board()

	def after_delete(self):
		if self.kanban_board:
			frappe.delete_doc(BOARD, self.kanban_board, ignore_permissions=True)

	def validate_steps(self):
		names = self.steps_in_order()
		repeated = sorted({name for name in names if names.count(name) > 1})
		if repeated:
			frappe.throw(
				_("Give each step its own name. Used more than once: {0}.").format(", ".join(repeated))
			)
		church = self.church or default_church()
		for row in self.steps:
			if row.assign_to:
				validate_step_user(row, church)

	def refuse_removing_steps_with_open_cards(self):
		before = self.get_doc_before_save()
		if not before:
			return
		removed = {row.step for row in before.steps} - set(self.steps_in_order())
		if not removed:
			return

		# church-scope: the cards of this one workflow
		in_use = frappe.get_all(
			CARD,
			filters={"workflow": self.name, "status": OPEN, "step": ("in", sorted(removed))},
			pluck="step",
			distinct=True,
		)
		if in_use:
			frappe.throw(
				_("Move the open cards off {0} before you remove it.").format(", ".join(sorted(in_use)))
			)

	def steps_in_order(self) -> list[str]:
		return [row.step for row in self.steps]

	def sync_board(self):
		"""Create or update the workflow's board, so its columns follow the steps."""
		board = frappe.get_doc(BOARD, self.kanban_board) if self.kanban_board else self.new_board()
		board.filters = json.dumps(
			[
				[CARD, "workflow", "=", self.name],
				[CARD, "status", "=", OPEN],
				[CARD, "snoozed_until", "is", "not set"],
			]
		)
		self.set_board_columns(board)
		# The workflow's own rights were checked; a board is writable only by whoever made it.
		board.save(ignore_permissions=True)
		if board.name != self.kanban_board:
			self.db_set("kanban_board", board.name, update_modified=False)

	def new_board(self) -> Document:
		return frappe.get_doc(
			{
				"doctype": BOARD,
				"kanban_board_name": self.name,
				"reference_doctype": CARD,
				"field_name": "step",
				"private": 0,
				"use_kanban_v2": 1,
				"title_field": "person_name",
				"show_assigned_to": 1,
				"card_fields": [{"fieldname": "due_on", "label": "Due On"}],
				"preview_fields": [{"fieldname": "reason", "label": "Reason"}],
			}
		)

	def set_board_columns(self, board: Document):
		"""A column per step, in order. A removed step's column is archived, keeping its colour and card order."""
		existing = {column.column_name: column for column in board.columns}
		board.set("columns", [])
		for step in self.steps_in_order():
			board.append("columns", existing.pop(step, None) or {"column_name": step}).status = "Active"
		for column in existing.values():
			board.append("columns", column).status = "Archived"
		for idx, column in enumerate(board.columns, start=1):
			column.idx = idx


def validate_step_user(row, church: str | None):
	"""A step's user must be able to take the card: an enabled login that can see the workflow's church."""
	if not frappe.db.get_value("User", row.assign_to, "enabled"):
		frappe.throw(
			_("Row {0}: {1} cannot sign in, so they cannot take this step.").format(row.idx, row.assign_to)
		)
	if not has_church_access(row.assign_to, church):
		frappe.throw(
			_("Row {0}: {1} cannot see {2}'s records, so they cannot take this step.").format(
				row.idx, row.assign_to, church
			),
			frappe.PermissionError,
		)
