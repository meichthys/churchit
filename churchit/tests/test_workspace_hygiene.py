# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every block on a shipped workspace must find its widget, and every shipped condition must keep its filters.

Both fail silently. A number card, chart, quick list or custom block names its widget by the label of the
workspace's row, so a row relabelled without its block leaves an empty space. Frappe 16.50 drops
the last condition of a list whose conditions carry a fifth part (frappe.utils.cleanup_filters
in public/js/frappe/utils/utils.js), so a list filtered on one condition shows every record. The same
four-part rule holds for shortcut counts and Web Form conditions. A manual link to a desk page that
was renamed or deleted opens "Page not found".

A module workspace is a dashboard, not a menu: the sidebar is the one menu, so it carries no link cards
and no quick lists, and it shows its blocks in one order so the work comes first on a phone. Those
two rules are ratchets: each phase of the UX roadmap deletes the exceptions it fixes, and the checks
fail on a new violation and on an exception that no longer applies.
"""

import glob
import json
import os
import re
from itertools import groupby
from urllib.parse import unquote, urlsplit

import frappe
from frappe.desk.utils import slug
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.giving_settings.giving_settings import SUPPORTED_GATEWAY_SETTINGS
from churchit.church_finances.payments import is_payments_on
from churchit.tests.test_desk_ui_hygiene import (
	assert_list_ratchet,
	doctype_files,
	get_default_list_filters,
	get_list_script,
)

# Which workspace rows each kind of block looks its widget up in.
BLOCK_ROWS = {
	"number_card": ("number_card_name", "number_cards"),
	"chart": ("chart_name", "charts"),
	"quick_list": ("quick_list_name", "quick_lists"),
	"custom_block": ("custom_block_name", "custom_blocks"),
}

# The order of a module workspace: verse, onboarding, attention shortcuts, number cards, charts.
# Other blocks (headers, spacers, custom blocks) go anywhere.
BLOCK_ORDER = ("paragraph", "onboarding", "shortcut", "number_card", "chart")

# A count shortcut spans every church's records, so these doctypes get none.
DOCTYPES_WITHOUT_COUNT_SHORTCUTS = ("Person", "Family")

# The most of each block a module workspace shows. A shortcut to a page (a Page or a URL, such as the
# Rolodex, a station or a map) does not count as an attention shortcut.
MAX_ATTENTION_SHORTCUTS = 6
MAX_PAGE_SHORTCUTS = 3
MAX_NUMBER_CARDS = 6
MAX_CHARTS = 4
PAGE_SHORTCUT_TYPES = ("Page", "URL")

# A JS value in a shortcut filter: frappe.session.user, frappe.datetime.add_days(frappe.datetime.get_today(), 7).
JS_VALUE = re.compile(r'(?<!["\w.])frappe(?:\.\w+)+(?:\((?:[^()]|\((?:[^()]|\([^()]*\))*\))*\))?')

# Today's breaks of each rule, with the phase of the UX roadmap that fixes them.
WORKSPACES_OUT_OF_ORDER = {}

WORKSPACES_WITH_LINK_CARDS = {}

WORKSPACES_WITH_QUICK_LISTS = {}

WORKSPACES_OVER_THEIR_CAPS = {
	"Settings": "Settings is the setup menu: no work waits there, so it shows no shortcut, card or chart",
}

COUNT_FILTER_EXCEPTIONS = {
	"Summary: My Assignments": "ToDo is Frappe's list, and a report cannot filter on the current user",
}

SUMMARY_CARD = (
	"Summary's At a Glance figures came before this rule; a click still saves the filter onto the list"
)
NUMBER_CARD_FILTER_EXCEPTIONS = {
	"Summary: Active Prayer Requests": SUMMARY_CARD,
	"Summary: Expenses This Month": SUMMARY_CARD,
	"Summary: Giving This Month": SUMMARY_CARD,
	"Summary: Prayers Answered This Month": SUMMARY_CARD,
}


def shipped(folder):
	pattern = os.path.join(frappe.get_app_path("churchit"), "*", folder, "*", "*.json")
	return [json.load(open(path)) for path in sorted(glob.glob(pattern))]


def shipped_workspaces():
	return shipped("workspace")


def get_module_workspaces():
	"""The workspaces that show a module's work: all but the manuals and Help."""
	return [
		workspace
		for workspace in shipped_workspaces()
		if not workspace["name"].startswith("Manual: ") and workspace["name"] != "Help"
	]


def get_block_types(workspace: dict) -> list[str]:
	return [block["type"] for block in json.loads(workspace["content"])]


def get_frappe_shortcut_colors() -> set[str]:
	"""The colors Frappe's shortcut dialog offers; any other value draws a gray badge."""
	path = frappe.get_app_path("frappe", "public", "js", "frappe", "widgets", "widget_dialog.js")
	with open(path) as source:
		match = re.search(
			r'fieldname: "color",\s*label: __\("Color"\),\s*options: \[([^\]]*)\]', source.read()
		)
	if not match:
		raise ValueError("Frappe moved the shortcut color options; update get_frappe_shortcut_colors")
	return set(re.findall(r'"(\w+)"', match.group(1)))


def get_conditions(conditions: str | list) -> list[list]:
	"""The [field, operator, value] conditions of a filter, written as JSON or as a JS expression, in one order."""
	if isinstance(conditions, str):
		conditions = json.loads(JS_VALUE.sub('"js"', conditions))
	return sorted((condition[-3:] for condition in conditions), key=json.dumps)


def get_cap_problems(workspace: dict) -> list[str]:
	"""How the blocks of *workspace* go over the most a module workspace shows."""
	types = get_block_types(workspace)
	rows = {row["label"]: row for row in workspace.get("shortcuts", [])}
	shortcuts = [
		rows[block["data"]["shortcut_name"]].get("type")
		for block in json.loads(workspace["content"])
		if block["type"] == "shortcut"
	]
	pages = sum(kind in PAGE_SHORTCUT_TYPES for kind in shortcuts)
	counts = {
		"attention shortcuts": (len(shortcuts) - pages, MAX_ATTENTION_SHORTCUTS),
		"page shortcuts": (pages, MAX_PAGE_SHORTCUTS),
		"number cards": (types.count("number_card"), MAX_NUMBER_CARDS),
		"charts": (types.count("chart"), MAX_CHARTS),
	}
	problems = [
		f"{count} {kind}, {limit} at most" for kind, (count, limit) in counts.items() if count > limit
	]
	if not types.count("chart"):
		problems.append("no chart")
	return problems


def has_five_parts(condition_json: str | None) -> bool:
	"""Whether a condition of the filter has a fifth part. Frappe reads the filter as a JS expression."""
	conditions = json.loads(JS_VALUE.sub('""', condition_json or "[]"))
	return isinstance(conditions, list) and any(len(condition) != 4 for condition in conditions)


def get_desk_link_problem(href: str, doctypes: dict, pages: set) -> str | None:
	"""Why a manual's desk link does not open its page, or None. Links off the desk are not checked."""
	if href.startswith(("http://app/", "https://app/")):
		return "not a site path"
	url = urlsplit(href)
	if url.scheme or url.netloc or not url.path.startswith(("/app/", "/desk/")):
		return None

	route, *rest = [unquote(part) for part in url.path.split("/")[2:] if part]
	if route == "query-report":
		is_report = frappe.db.exists("Report", {"name": rest[0], "report_type": ["!=", "Report Builder"]})
		return None if is_report else "no such report"
	if route not in doctypes and route not in pages:
		return "no such page"

	if rest[:2] == ["view", "report"] and len(rest) > 2:
		saved = {"name": rest[2], "report_type": "Report Builder", "ref_doctype": doctypes.get(route)}
		return None if frappe.db.exists("Report", saved) else "no such saved report"
	return None


class TestWorkspaceHygiene(FrappeTestCase):
	def test_every_block_finds_its_widget(self):
		missing = []
		for workspace in shipped_workspaces():
			for block in json.loads(workspace["content"]):
				if block["type"] not in BLOCK_ROWS:
					continue
				key, rows = BLOCK_ROWS[block["type"]]
				labels = {row["label"] for row in workspace.get(rows, [])}
				if block["data"][key] not in labels:
					missing.append((workspace["name"], block["data"][key]))
		self.assertEqual(missing, [])

	def test_quick_list_and_shortcut_conditions_have_four_parts(self):
		five_part = []
		for workspace in shipped_workspaces():
			for row in workspace.get("quick_lists", []):
				if has_five_parts(row["quick_list_filter"]):
					five_part.append((workspace["name"], row["label"]))
			for row in workspace.get("shortcuts", []):
				if has_five_parts(row.get("stats_filter")):
					five_part.append((workspace["name"], row["label"]))
		self.assertEqual(five_part, [])

	def test_web_form_conditions_have_four_parts(self):
		five_part = [
			form["name"] for form in shipped("web_form") if has_five_parts(form.get("condition_json"))
		]
		self.assertEqual(five_part, [])

	def test_manual_links_open_a_desk_page(self):
		doctypes = {slug(name): name for name in frappe.get_all("DocType", pluck="name")}
		if not is_payments_on():
			# The manual links the optional payments app's gateway settings.
			doctypes.update({slug(name): name for name in SUPPORTED_GATEWAY_SETTINGS})
		pages = set(frappe.get_all("Page", pluck="name")) | {
			slug(name) for name in frappe.get_all("Workspace", pluck="name")
		}
		broken = []
		for workspace in shipped_workspaces():
			if not workspace["name"].startswith("Manual: "):
				continue
			for block in json.loads(workspace["content"]):
				for href in re.findall(r'href="([^"]*)"', block["data"].get("text", "")):
					if problem := get_desk_link_problem(href, doctypes, pages):
						broken.append((workspace["name"], href, problem))
		self.assertEqual(broken, [])

	def test_conditions_with_javascript_dates_are_read(self):
		week = (
			'[["Function", "start_date", "between", '
			"[frappe.datetime.get_today(), frappe.datetime.add_days(frappe.datetime.get_today(), 7)]]]"
		)
		self.assertFalse(has_five_parts(week))
		self.assertFalse(has_five_parts('[["Care Request", "caregiver", "=", frappe.session.user]]'))
		self.assertTrue(has_five_parts('[["Function", "start_date", ">=", frappe.datetime.get_today(), 1]]'))

	def test_shortcut_colors_come_from_frappes_list(self):
		colors = get_frappe_shortcut_colors()
		self.assertIn("Orange", colors)
		wrong = [
			(workspace["name"], row["label"], row["color"])
			for workspace in shipped_workspaces()
			for row in workspace.get("shortcuts", [])
			if row.get("color") and row["color"] not in colors
		]
		self.assertEqual(wrong, [])

	def test_people_and_families_have_no_count_shortcut(self):
		"""Every DocType shortcut shows a count, except one that opens a new record."""
		counted = [
			(workspace["name"], row["label"])
			for workspace in shipped_workspaces()
			for row in workspace.get("shortcuts", [])
			if row.get("type") == "DocType"
			and row.get("link_to") in DOCTYPES_WITHOUT_COUNT_SHORTCUTS
			and row.get("doc_view") != "New"
		]
		self.assertEqual(counted, [])

	def test_module_workspaces_have_no_link_cards(self):
		"""The sidebar is the one menu."""
		found = {}
		for workspace in get_module_workspaces():
			card_blocks = get_block_types(workspace).count("card")
			if card_blocks or workspace.get("links"):
				found[workspace["name"]] = {
					"card_blocks": card_blocks,
					"link_rows": len(workspace.get("links", [])),
				}
		assert_list_ratchet(self, found, WORKSPACES_WITH_LINK_CARDS, "Module workspace has link cards")

	def test_module_workspaces_have_no_quick_lists(self):
		"""A quick list orders by creation and shows modified times; a shortcut or a report answers better."""
		found = {
			workspace["name"]: len(workspace.get("quick_lists", []))
			for workspace in get_module_workspaces()
			if workspace.get("quick_lists") or "quick_list" in get_block_types(workspace)
		}
		assert_list_ratchet(self, found, WORKSPACES_WITH_QUICK_LISTS, "Module workspace has quick lists")

	def test_module_workspaces_show_blocks_in_the_standard_order(self):
		"""Verse, onboarding, attention shortcuts, number cards, charts. Summary keeps its own order."""
		found = {}
		for workspace in get_module_workspaces():
			types = [kind for kind in get_block_types(workspace) if kind in BLOCK_ORDER]
			if workspace["name"] != "Summary" and types != sorted(types, key=BLOCK_ORDER.index):
				found[workspace["name"]] = [kind for kind, _ in groupby(types)]
		assert_list_ratchet(self, found, WORKSPACES_OUT_OF_ORDER, "Module workspace blocks are out of order")

	def test_module_workspaces_stay_within_their_caps(self):
		"""6 attention shortcuts, 3 page shortcuts and 6 number cards at most, and 1 to 4 charts."""
		found = {
			workspace["name"]: problems
			for workspace in get_module_workspaces()
			if (problems := get_cap_problems(workspace))
		}
		assert_list_ratchet(self, found, WORKSPACES_OVER_THEIR_CAPS, "Module workspace shows too many blocks")

	def test_count_shortcuts_use_the_lists_default_filter(self):
		"""A count shortcut saves its filter onto the list, so it is the filter that the list opens with."""
		scripts = {data["name"]: get_list_script(path) for path, data in doctype_files()}
		found = {}
		for workspace in shipped_workspaces():
			for row in workspace.get("shortcuts", []):
				if row.get("type") != "DocType" or row.get("doc_view") not in (None, "", "List"):
					continue
				default = get_default_list_filters(scripts.get(row["link_to"], ""))
				if row.get("stats_filter") and get_conditions(row["stats_filter"]) != get_conditions(default):
					found[f"{workspace['name']}: {row['label']}"] = row["stats_filter"]
		rule = "A count shortcut on a list uses the list's own default filter"
		assert_list_ratchet(self, found, COUNT_FILTER_EXCEPTIONS, rule)

	def test_number_cards_use_the_lists_default_filter(self):
		"""A click on a Document Type card saves the card's filter onto the list, as a count shortcut does."""
		scripts = {data["name"]: get_list_script(path) for path, data in doctype_files()}
		cards = {card["name"]: card for card in shipped("number_card")}
		found = {}
		for workspace in shipped_workspaces():
			for row in workspace.get("number_cards", []):
				card = cards.get(row["number_card_name"])
				if not card or card.get("type") != "Document Type":
					continue
				conditions = [
					condition[1:4]
					for key in ("filters_json", "dynamic_filters_json")
					for condition in json.loads(card.get(key) or "[]")
				]
				default = get_default_list_filters(scripts.get(card["document_type"], ""))
				if conditions and get_conditions(conditions) != get_conditions(default):
					found[f"{workspace['name']}: {row['label']}"] = card["name"]
		rule = "A number card with a filter uses the list's own default filter"
		assert_list_ratchet(self, found, NUMBER_CARD_FILTER_EXCEPTIONS, rule)

	def test_no_doctype_shortcut_opens_a_calendar(self):
		"""Its count saves a filter onto the calendar, which then hides the other weeks; use a URL shortcut."""
		found = [
			(workspace["name"], row["label"])
			for workspace in shipped_workspaces()
			for row in workspace.get("shortcuts", [])
			if row.get("type") == "DocType" and row.get("doc_view") == "Calendar"
		]
		self.assertEqual(found, [])
