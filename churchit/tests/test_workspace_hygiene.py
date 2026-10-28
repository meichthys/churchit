# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every block on a shipped workspace must find its widget, and every shipped condition must keep its filters.

Both fail silently. A number card, chart, quick list or custom block names its widget by the label of the
workspace's row, so a row relabelled without its block leaves an empty space. Frappe 16.50 drops
the last condition of a list whose conditions carry a fifth part (frappe.utils.cleanup_filters
in public/js/frappe/utils/utils.js), so a list filtered on one condition shows every record. The same
four-part rule holds for shortcut counts and Web Form conditions. A manual link to a desk page that
was renamed or deleted opens "Page not found".
"""

import glob
import json
import os
import re
from urllib.parse import unquote, urlsplit

import frappe
from frappe.desk.utils import slug
from frappe.tests.utils import FrappeTestCase

# Which workspace rows each kind of block looks its widget up in.
BLOCK_ROWS = {
	"number_card": ("number_card_name", "number_cards"),
	"chart": ("chart_name", "charts"),
	"quick_list": ("quick_list_name", "quick_lists"),
	"custom_block": ("custom_block_name", "custom_blocks"),
}


def shipped(folder):
	pattern = os.path.join(frappe.get_app_path("churchit"), "*", folder, "*", "*.json")
	return [json.load(open(path)) for path in sorted(glob.glob(pattern))]


def shipped_workspaces():
	return shipped("workspace")


def has_five_parts(condition_json: str | None) -> bool:
	# The filter is a JS expression; this is the only one it uses.
	conditions = json.loads((condition_json or "[]").replace("frappe.session.user", '""'))
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
