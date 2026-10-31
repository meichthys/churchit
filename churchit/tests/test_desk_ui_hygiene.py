# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Desk lists and forms keep the rules in AGENTS.md, because a broken one fails with no error.

Each check is a ratchet. It starts with today's exceptions, a change deletes the ones it fixes, and
the check fails on a new violation and on an exception that is no longer needed.
"""

import glob
import json
import os
import re

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_setup.multi_church import revealed_fields

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def doctype_files():
	"""(path relative to the app, doctype JSON) for every doctype churchit ships."""
	for path in sorted(glob.glob(os.path.join(APP_DIR, "*", "doctype", "*", "*.json"))):
		folder = os.path.basename(os.path.dirname(path))
		if os.path.basename(path) != f"{folder}.json":
			continue
		with open(path) as file:
			data = json.load(file)
		if data.get("doctype") == "DocType":
			yield os.path.relpath(path, APP_DIR), data


def get_enclosing_breaks(meta, fieldname):
	"""The Tab, Section and Column Break that hold *fieldname* on the form, outermost first."""
	tab = section = column = None
	for field in meta.fields:
		if field.fieldtype == "Tab Break":
			tab, section, column = field, None, None
		elif field.fieldtype == "Section Break":
			section, column = field, None
		elif field.fieldtype == "Column Break":
			column = field
		elif field.fieldname == fieldname:
			return [container for container in (tab, section, column) if container]
	return []


# The inline tags the desk draws in field help. Anything else in angle brackets, such as <name>,
# is an unknown tag that the browser drops, or block markup that does not suit one line of help.
HELP_TEXT_TAGS = {"a", "b", "br", "code", "em", "i", "strong"}

# The records patches/after_install seeds for each Link status doctype. A church may rename or
# delete them, so the check reads this copy, not the site.
STATE_LINKED_STATUSES = {"Prayer Request Status": {"Requested", "Being Prayed For", "Answered"}}


class TestDeskUiHygiene(FrappeTestCase):
	def test_is_shared_is_never_a_list_column_or_filter(self):
		"""Single-church sites would get an empty Shared column; multi-church adds the filter itself."""
		flagged = [
			(path, flag)
			for path, data in doctype_files()
			for field in data["fields"]
			if field["fieldname"] == "is_shared"
			for flag in ("in_list_view", "in_standard_filter")
			if field.get(flag)
		]
		self.assertEqual(flagged, [], "Clear these flags; Church Features reveals the filter")

	def test_revealed_fields_are_not_in_a_hidden_section(self):
		"""Church Features unhides these fields on multi-church sites, not the tab, section or column around them."""
		buried = [
			(doctype, fieldname, container.fieldname)
			for doctype, fieldname in revealed_fields()
			for container in get_enclosing_breaks(frappe.get_meta(doctype), fieldname)
			if container.hidden
		]
		self.assertEqual(buried, [], "Move these fields near the top of the form, after the title")

	def test_help_text_has_no_angle_brackets(self):
		"""The desk draws help as HTML, so a placeholder such as <name> vanishes as an unknown tag.

		Write CHANNEL_ID instead, and put an example in the field's `placeholder`.
		"""
		dropped = [
			(path, field["fieldname"], tag)
			for path, data in doctype_files()
			for field in data["fields"]
			for tag in re.findall(r"</?([A-Za-z][\w-]*)", field.get("description") or "")
			if tag.lower() not in HELP_TEXT_TAGS
		]
		self.assertEqual(dropped, [], f"Only these tags belong in help text: {sorted(HELP_TEXT_TAGS)}")

	def test_every_state_title_is_an_option_of_its_field(self):
		"""The desk colors a record by the state titled with its `status`, so any other title never shows.

		A Select status offers its options. A Link status offers the records that install seeds,
		copied in STATE_LINKED_STATUSES.
		"""
		unmatched = []
		for path, data in doctype_files():
			if not data.get("states"):
				continue
			status = next((field for field in data["fields"] if field["fieldname"] == "status"), {})
			if status.get("fieldtype") == "Link":
				values = STATE_LINKED_STATUSES.get(status["options"], set())
			else:
				values = set((status.get("options") or "").split("\n"))
			unmatched += [(path, state["title"]) for state in data["states"] if state["title"] not in values]
		self.assertEqual(unmatched, [], "Rename each state to the status value it colors")
