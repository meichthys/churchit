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
from collections.abc import Iterator

import frappe
from frappe.model import table_fields
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.privacy import PERSONAL_DOCTYPES, RECORDS_ABOUT_THE_PERSON
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
STATE_LINKED_STATUSES = {
	"Group Status": {"Active", "Inactive"},
	"Missionary Status": {"Active", "Pending", "Inactive"},
	"Prayer Request Status": {"Requested", "Being Prayed For", "Answered"},
}


# List checks. Each exception maps a doctype, or "Doctype.field", to the UX roadmap phase that fixes it:
# U4 is the list sweep, U7 to U11 are the module phases.

MAX_LIST_COLUMNS = 6
MAX_STANDARD_FILTERS = 4
MAX_SEARCH_FIELDS = 3
MAX_PERSON_SEARCH_FIELDS = 5  # the Person link search reads every search field
MAX_PREVIEW_FIELDS = 6

TEXT_LIST_TYPES = {
	"Code",
	"Geolocation",
	"HTML Editor",
	"Long Text",
	"Markdown Editor",
	"Small Text",
	"Table",
	"Table MultiSelect",
	"Text",
	"Text Editor",
}
RICH_TEXT_TYPES = {"HTML Editor", "Markdown Editor", "Text Editor"}
PREVIEW_EXCLUDED_TYPES = RICH_TEXT_TYPES | {"Check", "Dynamic Link", "Geolocation"}
PRIVATE_PREVIEW_DOCTYPES = {"Background Check", "Care Request", "Counseling Case", "Person Note"}

# Staff quote these numbers, so the list keeps the ID column and filter.
ID_KEPT = {
	"Bible Translation": "the ID is the abbreviation",
	"Church Asset": "asset tags",
	"Collection": "GL journal and bank reconciliation",
	"Counseling Case": "a case has no name",
	"Expense": "GL journal and bank reconciliation",
	"Fund Transfer": "GL journal and bank reconciliation",
	"Online Donation": "GL journal and bank reconciliation",
}
ID_FILTER_KEPT = {"Room Booking": "the printed setup sheet quotes the booking number"}

QUOTED_ID = re.compile(r"\{\{\s*doc\.name\s*(?:\|[^}]*)?\}\}")
INCLUDED_TEMPLATE = re.compile(r"\{%-?\s*include\s+[\"']([^\"']+)")


def list_doctypes() -> Iterator[tuple[str, dict]]:
	"""(path, doctype JSON) for each doctype that has a list: not a child table, not a Single."""
	for path, data in doctype_files():
		if not data.get("istable") and not data.get("issingle"):
			yield path, data


def get_flagged_fields(data: dict, flag: str) -> list[str]:
	return [field["fieldname"] for field in data["fields"] if field.get(flag)]


def get_list_script(path: str) -> str:
	"""The source of the `_list.js` beside the doctype JSON at *path*, or an empty string."""
	script = os.path.join(APP_DIR, os.path.splitext(path)[0] + "_list.js")
	if not os.path.exists(script):
		return ""
	with open(script) as file:
		return file.read()


def get_default_list_filters(script: str) -> list[list]:
	"""The conditions of the `filters` a list script opens with, written as JSON on one line."""
	match = re.search(r"^\s*filters:\s*(\[.*\]),?\s*$", script, re.MULTILINE)
	return json.loads(match.group(1)) if match else []


def has_list_option(script: str, option: str) -> bool:
	"""Whether a list script sets *option*, as a method or as any value but false."""
	return bool(re.search(rf"(?:^|[{{,])\s*{option}\s*(\(|:\s*(?!\s|false\b))", script, re.MULTILINE))


def has_status_pill(data: dict) -> bool:
	"""Whether a doctype has a Select or Link `status`; a Data `status` names a record, such as a Group Status."""
	return any(
		field["fieldname"] == "status" and field["fieldtype"] in ("Link", "Select")
		for field in data["fields"]
	)


def get_id_rule(data: dict) -> tuple[bool, bool]:
	"""(hide the ID column, hide the ID filter) that the ID rule asks of a doctype."""
	hide_column = bool(data.get("title_field")) and data["name"] not in ID_KEPT
	return hide_column, hide_column and data["name"] not in ID_FILTER_KEPT


def get_title_link(data: dict) -> str | None:
	"""The Link whose `fetch_from` fills the title: its column shows the subject again.

	The title field itself is no repeat, because the desk leaves it out of the field columns.
	"""
	fields = {field["fieldname"]: field for field in data["fields"]}
	fetch_from = fields.get(data.get("title_field"), {}).get("fetch_from")
	return fetch_from.split(".")[0] if fetch_from else None


def get_search_fields(data: dict) -> list[str]:
	return [name.strip() for name in (data.get("search_fields") or "").split(",") if name.strip()]


def has_raw_id(field: dict, doctypes: dict[str, dict]) -> bool:
	"""Whether a search field prints an ID: a Dynamic Link, or a Link to a doctype with a generated name."""
	if field.get("fieldtype") == "Dynamic Link":
		return True
	target = doctypes.get(field.get("options")) if field.get("fieldtype") == "Link" else None
	if not target:
		return False
	autoname = target.get("autoname") or ""
	return not (autoname.startswith("field:") or autoname.lower() == "prompt")


def get_prints_and_notifications() -> Iterator[tuple[str, dict]]:
	"""(path, JSON) for each print format and notification churchit ships."""
	for kind in ("print_format", "notification"):
		for path in sorted(glob.glob(os.path.join(APP_DIR, "*", kind, "*", "*.json"))):
			with open(path) as file:
				yield os.path.relpath(path, APP_DIR), json.load(file)


def get_shown_text(path: str, data: dict) -> str:
	"""What a print format or notification shows: its fields, the `.md` beside it, the templates it includes."""
	text = " ".join(str(data.get(key) or "") for key in ("subject", "message", "html"))
	markdown = os.path.join(APP_DIR, os.path.splitext(path)[0] + ".md")
	if os.path.exists(markdown):
		with open(markdown) as file:
			text += file.read()
	for include in INCLUDED_TEMPLATE.findall(text):
		template = os.path.join(os.path.dirname(APP_DIR), include)
		if os.path.exists(template):
			with open(template) as file:
				text += file.read()
	return text


def assert_list_ratchet(test: FrappeTestCase, found: dict, exceptions: dict[str, str], rule: str) -> None:
	"""Fail on a break that no exception names, and on an exception that no longer breaks the rule."""
	new = {key: why for key, why in found.items() if key not in exceptions}
	test.assertEqual(new, {}, f"{rule}. Fix these: the exceptions only shrink")
	test.assertEqual(
		sorted(set(exceptions) - set(found)), [], f"{rule}. Delete these exceptions, they are fixed"
	)


# Today's breaks of each rule. A phase deletes the entries it fixes.

COLUMN_BUDGET_EXCEPTIONS = {}

TEXT_COLUMN_EXCEPTIONS = {
	"Belief.belief_statement": "U4",
	"Church Task.notes": "U4",
}

REPEATED_COLUMN_EXCEPTIONS = {}

FILTER_BUDGET_EXCEPTIONS = {
	"Church Task": "U11",
}

DEFAULT_FILTER_EXCEPTIONS = {
	"Room Booking": "U11",
}

ID_RULE_EXCEPTIONS = {
	"Belief": "U4",
	"Church": "U4",
	"Church Location": "U4",
	"Church Task": "U4",
	"Form Response": "U4",
	"Meeting Minutes": "U4",
	"Question Set": "U4",
	"Room": "U4",
}

STATUS_COLOR_EXCEPTIONS = {
	"Form Response": "U4",
	"Meeting Minutes": "U4",
	"Room Booking": "U4",
}

QUOTED_ID_EXCEPTIONS = {
	"church_people/print_format/member_qr_card/member_qr_card.json": "The card prints the Person ID beside the QR code that the Check-In Station scans",
}

PREVIEW_FIELD_EXCEPTIONS = {
	"Church Asset.notes": "U4",
	"Church Location.geolocation": "U4",
	"Church Task Item.completed": "U4",
	"Church Task Item.item": "U4",
	"Church Task Item.notes": "U4",
	"Church Task.is_group": "U4",
	"Church Task.notes": "U4",
}

PREVIEW_POPUP_EXCEPTIONS = {
	"Belief": "U4",
	"Church Asset": "U4",
	"Church Task": "U4",
	"Church Task Item": "U4",
}

SEARCH_FIELD_EXCEPTIONS = {
	"Church Asset.location": "U11",
	"Church Asset.notes": "U11",
	"Church Task.notes": "U11",
}

SEARCH_COUNT_EXCEPTIONS = {}

SORT_EXCEPTIONS = {
	"Belief": "U4",
	"Church": "U4",
	"Church Asset": "U4",
	"Church Location": "U4",
	"Church Task": "U4",
	"Follow-up Action Run": "a log of automation runs",
	"Form Response": "U4",
	"Question Set": "U4",
	"Room": "U4",
}

# R2: form checks (UX roadmap U1). Each exception maps a doctype, or "Doctype.field", to its fixing phase.

INLINE_HELP_LIMIT = 80
BLOCK_HELP_LIMIT = 120
MAX_CONTENT_TABS = 5
MAX_GRID_COLUMNS = 5
CHURCH_FIELDS_TAB = "Church Fields"
UNNAMED_TABS = {"advanced", "misc", "miscellaneous", "more", "other"}
FORM_BREAKS = ("Column Break", "Section Break", "Tab Break")
# Section and table help cannot hide behind the (i) icon, so it stays on one line.
BLOCK_HELP_FIELDTYPES = ("Section Break", "Table")
# Controls that cap their height with max_height. A Small Text box is 150px, under the 12rem cap.
LONG_TEXT_FIELDTYPES = ("Code", "HTML Editor", "Long Text", "Markdown Editor", "Text", "Text Editor")
# Frappe 16.54 maps a grid column's `columns` from 1 to 12 onto 60 to 600px and ignores any other value.
GRID_COLUMN_WIDTHS = range(1, 13)

# Doctype: a field help over 80 characters without the (i) icon, or a section or table help over 120.
LONG_HELP_EXCEPTIONS = {
	"Belief": "U11",
	"Church": "U11",
	"Church Features": "U11",
	"Church Task": "U11",
	"Question Set": "U11",
	"Question Set Question": "U11",
	"Room": "U11",
	"Room Booking": "U11",
}

# Doctype.fieldname: a text field on the first tab without max_height.
TEXT_HEIGHT_EXCEPTIONS = {
	"Belief.belief_statement": "U11",
	"Church Asset.notes": "U11",
	"Church Task.notes": "U11",
	"Church.about": "U11",
	"Meeting Minutes.minutes": "U11",
	"Room Booking.notes": "U11",
}

# Child doctype: an in_list_view field without `columns`, more than 5 grid columns, or a text column.
GRID_EXCEPTIONS = {
	"Slide": "The slide text is the only value that tells the rows apart, so it stays in the grid",
	"Church Task Item": "U11",
	"Meeting Attendee": "U11",
	"Room Setup": "U11",
}

# Doctype.fieldname: a collapsible section without collapsible_depends_on.
COLLAPSIBLE_EXCEPTIONS = {
	"Church Features.section_website_pages": "U11",
	"Meeting Minutes.section_break_3": "U11",
}

# Doctype.fieldname: collapsed sections of routine system values, which stay closed. Each has a
# one-line description of what it holds.
ROUTINE_COLLAPSED = {
	"Bible Memory Item.internal_section": "Mistake counts per word that the Bible Memory page keeps",
	"Bulletin.section_break_sections": "Print toggles that Bulletin Settings defaults, set once",
	"Missionary.location_section": "The map pin, which choosing a country places",
}

# Doctype: why its Version rows may stay after Remove Personal Data. A gap line is a leak to close in
# church_people/privacy.py. test_privacy_history.is_gap reads a line that holds " gap:" as a gap.
PERSON_HISTORY_EXCEPTIONS = {
	"Church Email": "Kept for its other recipients; anonymizing removes the person's name and email from its history",
	"Collection": "Kept for its other donors; anonymizing removes the person's name and email from its history",
	"Family": "Kept for its other members; anonymizing removes the person's name, email and first name from its history and from its members' histories",
	"Function": "Kept for its other attendees; anonymizing removes the person's name and email from its history",
	"Group": "Kept for its other members; anonymizing removes the person's name and email from its history",
	"Ministry": "Kept for the ministry; anonymizing removes the coordinator's name and email from its history",
	"Ministry Team Position": "Kept for its other people; anonymizing removes the person's name and email from its history",
	"Missionary": "Kept for the missionary; anonymizing removes the person's name and email from its history",
	"Sermon": "Kept for the sermon; anonymizing removes the preacher's name and email from its history",
	"Sermon Series": "Kept for the series; anonymizing removes the person's name and email from its history",
}

# Doctype: why a record keeps a viewed row for every open.
TRACK_VIEWS_AUDITED = {
	"Person": "Shows who opened a record that holds health and family details",
	"Prayer Request": "Shows who read a private prayer request",
}


def get_fields_in_form_order(data: dict) -> list[dict]:
	"""The fields of *data* as the form lays them out, by `field_order`, which `fields` need not follow."""
	fields = {field["fieldname"]: field for field in data["fields"]}
	return [fields[fieldname] for fieldname in data["field_order"]]


def get_words(text: str | None) -> list[str]:
	return re.findall(r"\w+", (text or "").lower())


def get_help_problems(field: dict) -> list[str]:
	"""How the help of *field* is too long for where the desk draws it."""
	length = len(re.sub(r"<[^>]*>", "", field.get("description") or ""))
	name, fieldtype = field["fieldname"], field["fieldtype"]
	if fieldtype in BLOCK_HELP_FIELDTYPES and length > BLOCK_HELP_LIMIT:
		return [f"{name}: help is {length} characters, keep it to one line of {BLOCK_HELP_LIMIT}"]
	is_input = fieldtype not in FORM_BREAKS and fieldtype not in BLOCK_HELP_FIELDTYPES
	if is_input and length > INLINE_HELP_LIMIT and not field.get("show_description_on_click"):
		return [f"{name}: help is {length} characters, set show_description_on_click or shorten it"]
	return []


def get_tab_name_problems(tab: dict) -> list[str]:
	problems = []
	if not tab["fieldname"].endswith("_tab"):
		problems.append(f"{tab['fieldname']}: a tab fieldname is <noun>_tab")
	if (tab.get("label") or "").lower() in UNNAMED_TABS:
		problems.append(f"{tab['label']}: name a tab by its content, not Other, More, Misc or Advanced")
	return problems


def get_tab_layout_problems(data: dict, tabs: list[dict]) -> list[str]:
	"""How the tabs of *data* are ordered and counted. Frappe puts a Details tab ahead of fields in no tab."""
	problems = []
	first_visible = next((field for field in get_fields_in_form_order(data) if not field.get("hidden")), {})
	has_first_tab = first_visible.get("fieldtype") == "Tab Break"
	if has_first_tab and not data.get("issingle") and first_visible.get("label") != "Details":
		problems.append(f"The first tab is {first_visible.get('label')}, it must be Details")
	content = [tab for tab in tabs if not tab.get("show_dashboard") and tab.get("label") != CHURCH_FIELDS_TAB]
	content_tabs = len(content) + (not has_first_tab)
	if content_tabs > MAX_CONTENT_TABS:
		problems.append(f"{content_tabs} content tabs, at most {MAX_CONTENT_TABS}")
	if any(tab.get("label") == CHURCH_FIELDS_TAB for tab in tabs[:-1]):
		problems.append(f"{CHURCH_FIELDS_TAB} must be the last tab")
	return problems


def get_tab_problems(data: dict) -> list[str]:
	tabs = [field for field in get_fields_in_form_order(data) if field["fieldtype"] == "Tab Break"]
	if not tabs:
		return []

	problems = [problem for tab in tabs for problem in get_tab_name_problems(tab)]
	return problems + get_tab_layout_problems(data, tabs)


def get_collapsible_sections() -> dict[str, dict]:
	"""Every collapsible Section Break of a churchit doctype, by Doctype.fieldname."""
	return {
		f"{data['name']}.{field['fieldname']}": field
		for _path, data in doctype_files()
		for field in data["fields"]
		if field["fieldtype"] == "Section Break" and field.get("collapsible")
	}


def get_collapsible_problems(key: str, section: dict) -> list[str]:
	problems = []
	if not section.get("label"):
		problems.append("name the section by its content")
	if key in ROUTINE_COLLAPSED and not section.get("description"):
		problems.append("describe in one line what the routine section holds")
	if key not in ROUTINE_COLLAPSED and not section.get("collapsible_depends_on"):
		problems.append(
			"set collapsible_depends_on so it opens when it holds data, or add it to ROUTINE_COLLAPSED"
		)
	return problems


def get_first_tab_fields(data: dict) -> list[dict]:
	"""The fields before the first Tab Break that follows a field, so the whole form when it has no tab."""
	fields = []
	for field in get_fields_in_form_order(data):
		if field["fieldtype"] == "Tab Break" and any(
			earlier["fieldtype"] not in FORM_BREAKS for earlier in fields
		):
			break
		fields.append(field)
	return fields


def get_grid_problems(data: dict) -> list[str]:
	"""How the columns of the grid that child doctype *data* draws break the width, count and type rules."""
	columns = [
		field
		for field in data["fields"]
		if field.get("in_list_view") and not field.get("hidden") and field["fieldtype"] not in FORM_BREAKS
	]
	problems = [
		f"{field['fieldname']}: set `columns` from 1 to 12"
		for field in columns
		if field.get("columns") not in GRID_COLUMN_WIDTHS
	]
	problems += [
		f"{field['fieldname']}: a {field['fieldtype']} stays in the row form, not the grid"
		for field in columns
		if field["fieldtype"] in LONG_TEXT_FIELDTYPES
	]
	if len(columns) > MAX_GRID_COLUMNS:
		problems.append(f"{len(columns)} grid columns, at most {MAX_GRID_COLUMNS}")
	return problems


def get_grid_doctypes() -> set[str]:
	"""The child doctypes that a form or a web form draws as a grid. A Table MultiSelect draws tags instead."""
	fields = [field for _path, data in doctype_files() for field in data["fields"]]
	for path in glob.glob(os.path.join(APP_DIR, "*", "web_form", "*", "*.json")):
		with open(path) as file:
			fields += json.load(file).get("web_form_fields", [])
	return {field["options"] for field in fields if field["fieldtype"] == "Table"}


def has_person_link(data: dict, doctypes: dict[str, dict]) -> bool:
	"""Whether *data*, or a child table of it, has a Link field to Person."""
	for field in data["fields"]:
		if field["fieldtype"] == "Link" and field.get("options") == "Person":
			return True
		child = doctypes.get(field.get("options")) if field["fieldtype"] in table_fields else None
		if child and has_person_link(child, doctypes):
			return True
	return False


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

	def test_list_columns_stay_within_the_budget(self):
		"""At 1440px a list shows the subject, a status pill and 4 fields; 2 more wait at the end of the scroll."""
		found = {}
		for _, data in list_doctypes():
			columns = get_flagged_fields(data, "in_list_view")
			if len(columns) > MAX_LIST_COLUMNS:
				found[data["name"]] = f"{len(columns)} list columns: {', '.join(columns)}"
		rule = f"A list has {MAX_LIST_COLUMNS} columns at most"
		assert_list_ratchet(self, found, COLUMN_BUDGET_EXCEPTIONS, rule)

	def test_lists_have_no_text_columns(self):
		"""A text, map or table column is clipped to a few words and adds no fact."""
		found = {
			f"{data['name']}.{field['fieldname']}": field["fieldtype"]
			for _, data in list_doctypes()
			for field in data["fields"]
			if field.get("in_list_view") and field["fieldtype"] in TEXT_LIST_TYPES
		}
		rule = "A list column is never a text, code, map or table field"
		assert_list_ratchet(self, found, TEXT_COLUMN_EXCEPTIONS, rule)

	def test_lists_never_repeat_the_title(self):
		"""The subject column shows the title, so a Link that fills the title adds nothing.

		The title field itself is no repeat: the desk leaves it out of the field columns.
		"""
		found = {
			f"{data['name']}.{field['fieldname']}": "repeats the title"
			for _, data in list_doctypes()
			for field in data["fields"]
			if field.get("in_list_view") and field["fieldname"] == get_title_link(data)
		}
		rule = "A list column never repeats the title"
		assert_list_ratchet(self, found, REPEATED_COLUMN_EXCEPTIONS, rule)

	def test_list_filters_stay_within_the_budget(self):
		"""More than 4 filter boxes wrap to a second row and push the list down.

		The budget counts the flags in the JSON. A multi-church site adds the church and sharing filters.
		"""
		found = {}
		for _, data in list_doctypes():
			filters = get_flagged_fields(data, "in_standard_filter")
			if len(filters) > MAX_STANDARD_FILTERS:
				found[data["name"]] = f"{len(filters)} standard filters: {', '.join(filters)}"
		rule = f"A list has {MAX_STANDARD_FILTERS} standard filters at most"
		assert_list_ratchet(self, found, FILTER_BUDGET_EXCEPTIONS, rule)

	def test_default_list_filters_are_not_standard_filters(self):
		"""Frappe adds a standard filter on top of the default filter, so picking Resolved would show nothing.

		An = condition is the exception: Frappe puts it in the standard filter box, unless it is = 0 on a Check.
		"""
		found = {}
		for path, data in list_doctypes():
			# A condition is [field, operator, value] or [doctype, field, operator, value].
			fields = {
				condition[-3]
				for condition in get_default_list_filters(get_list_script(path))
				if condition[-2] != "=" or condition[-1] in (0, "0")
			}
			if both := sorted(fields & set(get_flagged_fields(data, "in_standard_filter"))):
				found[data["name"]] = f"{', '.join(both)} is a default filter and a standard filter"
		rule = "The field of a list's default filter is not also a standard filter"
		assert_list_ratchet(self, found, DEFAULT_FILTER_EXCEPTIONS, rule)

	def test_lists_with_a_title_hide_the_id(self):
		"""The title is the subject, so the ID column and ID filter repeat it; staff who quote an ID keep them."""
		found = {}
		for path, data in list_doctypes():
			script = get_list_script(path)
			actual = (
				has_list_option(script, "hide_name_column"),
				has_list_option(script, "hide_name_filter"),
			)
			wanted = get_id_rule(data)
			if actual != wanted:
				found[data["name"]] = (
					f"(hide_name_column, hide_name_filter) is {actual}, the rule wants {wanted}"
				)
		rule = "A list with a title field hides the ID in its _list.js, except the lists in ID_KEPT"
		assert_list_ratchet(self, found, ID_RULE_EXCEPTIONS, rule)

	def test_list_script_options_are_read_as_the_desk_reads_them(self):
		"""The ID and status checks read `_list.js` text, so a false value or a comment is not an option."""
		self.assertTrue(has_list_option("x = {\n\thide_name_column: true,\n};", "hide_name_column"))
		self.assertTrue(has_list_option("x = { hide_name_filter: true };", "hide_name_filter"))
		self.assertTrue(has_list_option("x = {\n\tget_indicator(doc) {},\n};", "get_indicator"))
		for script in ("hide_name_column: false", "hide_name_column:  false", "// hide_name_column: true"):
			self.assertFalse(has_list_option(script, "hide_name_column"), script)

	def test_every_status_has_a_color(self):
		"""A Select or Link `status` shows as a colored pill, from DocType `states` or `get_indicator` in `_list.js`.

		A Data `status` names a record of a status doctype, such as Group Status, and has no pill.
		"""
		found = {}
		for path, data in list_doctypes():
			has_color = data.get("states") or has_list_option(get_list_script(path), "get_indicator")
			if has_status_pill(data) and not has_color:
				found[data["name"]] = "no DocType states and no get_indicator"
		rule = "A status has a color"
		assert_list_ratchet(self, found, STATUS_COLOR_EXCEPTIONS, rule)

	def test_prints_and_notifications_never_quote_a_hidden_id(self):
		"""A list that hides the ID gives staff no way to look up the number that a printout or email quotes."""
		doctypes = {data["name"]: data for _, data in doctype_files()}
		found = {}
		for path, data in get_prints_and_notifications():
			doctype = doctypes.get(data.get("doc_type") or data.get("document_type"))
			if doctype and get_id_rule(doctype)[1] and QUOTED_ID.search(get_shown_text(path, data)):
				found[path] = f"quotes the ID of a {doctype['name']}, which the list hides"
		rule = "A print format or notification quotes no ID that its list hides"
		assert_list_ratchet(self, found, QUOTED_ID_EXCEPTIONS, rule)

	def test_previews_show_only_short_facts(self):
		"""A map, tick box, rich text or raw Dynamic Link value is no fact to read on a hover card."""
		found = {
			f"{data['name']}.{field['fieldname']}": field["fieldtype"]
			for _, data in doctype_files()
			for field in data["fields"]
			if field.get("in_preview") and field["fieldtype"] in PREVIEW_EXCLUDED_TYPES
		}
		rule = "A preview field is never a map, tick box, rich text or Dynamic Link"
		assert_list_ratchet(self, found, PREVIEW_FIELD_EXCEPTIONS, rule)

	def test_previews_need_the_popup_and_skip_private_records(self):
		"""A preview popup names 1 to 6 `in_preview` fields, and never shows a private record.

		With no `in_preview` field Frappe previews every required field, whatever its type.
		"""
		found = {}
		for _, data in doctype_files():
			fields = get_flagged_fields(data, "in_preview")
			if fields and not data.get("show_preview_popup"):
				found[data["name"]] = "in_preview fields without show_preview_popup"
			elif data.get("show_preview_popup") and data["name"] in PRIVATE_PREVIEW_DOCTYPES:
				found[data["name"]] = "a preview on private records"
			elif data.get("show_preview_popup") and not fields:
				found[data["name"]] = "a preview with no in_preview field shows every required field"
			elif len(fields) > MAX_PREVIEW_FIELDS:
				found[data["name"]] = f"{len(fields)} preview fields: {', '.join(fields)}"
		rule = f"A preview has {MAX_PREVIEW_FIELDS} fields at most, and never shows a private record"
		assert_list_ratchet(self, found, PREVIEW_POPUP_EXCEPTIONS, rule)

	def test_search_fields_hold_no_rich_text_or_raw_ids(self):
		"""A Link dropdown prints each search field under the title: rich text is noise, a Link prints its raw ID."""
		doctypes = {data["name"]: data for _, data in doctype_files()}
		found = {}
		for _, data in doctype_files():
			fields = {field["fieldname"]: field for field in data["fields"]}
			for fieldname in get_search_fields(data):
				field = fields.get(fieldname, {})
				if field.get("fieldtype") in RICH_TEXT_TYPES:
					found[f"{data['name']}.{fieldname}"] = f"{field['fieldtype']} is rich text"
				elif has_raw_id(field, doctypes):
					found[f"{data['name']}.{fieldname}"] = (
						f"{field['fieldtype']} to {field['options']} prints an ID"
					)
		rule = "A search field is never rich text, a Dynamic Link or a Link to a record with a generated name"
		assert_list_ratchet(self, found, SEARCH_FIELD_EXCEPTIONS, rule)

	def test_search_fields_stay_short(self):
		"""A dropdown row with more than 3 extra values is hard to read; Person has 5 because its search reads them all."""
		found = {}
		for _, data in doctype_files():
			fields = get_search_fields(data)
			limit = MAX_PERSON_SEARCH_FIELDS if data["name"] == "Person" else MAX_SEARCH_FIELDS
			if len(fields) > limit:
				found[data["name"]] = f"{len(fields)} search fields: {', '.join(fields)}"
		rule = f"A doctype has {MAX_SEARCH_FIELDS} search fields at most, Person {MAX_PERSON_SEARCH_FIELDS}"
		assert_list_ratchet(self, found, SEARCH_COUNT_EXCEPTIONS, rule)

	def test_lists_never_sort_by_modified(self):
		"""Sorting by last change reshuffles the list on every edit; sort by the record's own date or its name."""
		found = {
			data["name"]: "sorts by modified"
			for _, data in list_doctypes()
			if data.get("sort_field", "modified") == "modified"
		}
		rule = "A list sorts by modified only when it is a log"
		assert_list_ratchet(self, found, SORT_EXCEPTIONS, rule)

	def test_long_help_sits_behind_the_info_icon(self):
		"""Help over 80 characters sits behind the (i) icon, and a section or table help is one line.

		Set `show_description_on_click` on the field, or shorten the help.
		"""
		found = {
			data["name"]: "; ".join(problems)
			for _path, data in doctype_files()
			if (problems := [problem for field in data["fields"] for problem in get_help_problems(field)])
		}
		rule = f"Help over {INLINE_HELP_LIMIT} characters sits behind the (i) icon; other help is one line"
		assert_list_ratchet(self, found, LONG_HELP_EXCEPTIONS, rule)

	def test_help_never_repeats_the_label(self):
		"""Help that says only what the label says adds nothing."""
		repeats = [
			(path, field["fieldname"])
			for path, data in doctype_files()
			for field in data["fields"]
			if field.get("description") and get_words(field["description"]) == get_words(field.get("label"))
		]
		self.assertEqual(repeats, [], "Delete this help, or say more than the label does")

	def test_tabs_follow_the_naming_rules(self):
		"""The first tab is Details, a form has 5 content tabs at most, and Church Fields comes last.

		A tab fieldname is <noun>_tab, and no tab is called Other, More, Misc or Advanced. A Single may
		start on another tab.
		"""
		found = {
			data["name"]: problems for _path, data in doctype_files() if (problems := get_tab_problems(data))
		}
		self.assertEqual(found, {}, "Rename or regroup the tabs of these doctypes")

	def test_collapsible_sections_open_when_they_hold_data(self):
		"""A collapsible section opens by itself when staff typed something in it.

		Set `collapsible_depends_on`. A section of routine system values may stay closed when it is in
		ROUTINE_COLLAPSED with a one-line description.
		"""
		sections = get_collapsible_sections()
		found = {
			key: "; ".join(problems)
			for key, section in sections.items()
			if (problems := get_collapsible_problems(key, section))
		}
		rule = "A collapsible section opens by itself when it holds data"
		assert_list_ratchet(self, found, COLLAPSIBLE_EXCEPTIONS, rule)

		stale = [
			key
			for key in ROUTINE_COLLAPSED
			if key not in sections or sections[key].get("collapsible_depends_on")
		]
		self.assertEqual(
			stale, [], "These open by themselves or are gone. Delete them from ROUTINE_COLLAPSED"
		)

	def test_first_tab_text_fields_have_a_max_height(self):
		"""A long text box on the first tab pushes the fields below it off the screen.

		Set `max_height` to 12rem.
		"""
		found = {
			f"{data['name']}.{field['fieldname']}": field["fieldtype"]
			for _path, data in doctype_files()
			if not data.get("istable")
			for field in get_first_tab_fields(data)
			if field["fieldtype"] in LONG_TEXT_FIELDTYPES
			and not field.get("hidden")
			and not field.get("max_height")
		}
		rule = "A long text field on the first tab sets max_height"
		assert_list_ratchet(self, found, TEXT_HEIGHT_EXCEPTIONS, rule)

	def test_grids_set_their_column_widths(self):
		"""Every grid column has a width, a grid has 5 columns at most, and none is a text box.

		Set `columns` on each in_list_view field, widest on the column that identifies the row, and keep
		long text in the row form. A child doctype that only a Table MultiSelect uses has no grid, so it
		is not checked.
		"""
		grids = get_grid_doctypes()
		found = {
			data["name"]: "; ".join(problems)
			for _path, data in doctype_files()
			if data["name"] in grids and (problems := get_grid_problems(data))
		}
		rule = f"A grid has {MAX_GRID_COLUMNS} columns at most, each with a width, and none is a text box"
		assert_list_ratchet(self, found, GRID_EXCEPTIONS, rule)

	def test_track_views_only_where_an_audit_is_needed(self):
		"""A viewed row for every open fills the timeline, so only TRACK_VIEWS_AUDITED doctypes log views."""
		tracked = {data["name"] for _path, data in doctype_files() if data.get("track_views")}
		self.assertEqual(sorted(tracked - set(TRACK_VIEWS_AUDITED)), [], "Turn track_views off on these")
		self.assertEqual(
			sorted(set(TRACK_VIEWS_AUDITED) - tracked),
			[],
			"These log no views now. Delete them from TRACK_VIEWS_AUDITED",
		)

	def test_doctypes_set_no_timeline_field(self):
		"""`timeline_field` has no visible effect in Frappe 16.54."""
		flagged = [data["name"] for _path, data in doctype_files() if data.get("timeline_field")]
		self.assertEqual(flagged, [], "Clear timeline_field on these doctypes")

	def test_tracked_records_about_a_person_are_forgotten_with_them(self):
		"""Version rows hold the old values of a record, a person's name among them.

		A doctype with track_changes that links to a Person loses its Version rows when the person is
		anonymized (church_people/privacy.py), or sits in PERSON_HISTORY_EXCEPTIONS with the reason.

		This reads only the PERSONAL_DOCTYPES and RECORDS_ABOUT_THE_PERSON tuples. A doctype whose history
		anonymizing scrubs rather than deletes (privacy.scrub_history) keeps a line with that reason.
		church_people/test_privacy_history.py proves the lines by behavior.
		"""
		doctypes = {data["name"]: data for _path, data in doctype_files()}
		forgotten = {"Person"} | {doctype for doctype, _field in PERSONAL_DOCTYPES + RECORDS_ABOUT_THE_PERSON}
		found = {
			name: "Version rows may keep the person's name"
			for name, data in doctypes.items()
			if data.get("track_changes")
			and not data.get("istable")
			and name not in forgotten
			and has_person_link(data, doctypes)
		}
		rule = "A tracked record about a person loses its Version rows when the person is anonymized"
		assert_list_ratchet(self, found, PERSON_HISTORY_EXCEPTIONS, rule)
