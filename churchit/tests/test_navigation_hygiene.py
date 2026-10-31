# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Churchit dock and its module sidebars must agree, because the desk drops a mismatch silently.

A sidebar no dock entry names is reachable by URL only, and an entry naming no sidebar is left off
the rail. The desk opens a workspace in the first sidebar of the workspace's module, so a module
with two sidebars shows the wrong one, and a sidebar that opens on another module's workspace
switches away from itself on arrival.

An icon that is not in a loaded sprite draws nothing, a duplicate default-module claim is settled by
install order with no warning, and a URL item opens in a new tab even for a desk route. Those rules,
the label length and the folder pattern are ratchets: each phase of the UX roadmap deletes the
exceptions it fixes, and the checks fail on a new violation and on an exception that no longer applies.
"""

import re
from urllib.parse import urlsplit

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_desk_ui_hygiene import assert_list_ratchet

# A label longer than this is cut off in the sidebar at 1440px.
MAX_LABEL_LENGTH = 24

# A section is a closed folder with an icon; its items are children and draw no icon.
FOLDER_FLAGS = ("indent", "collapsible", "keep_closed", "icon")

# Sections that stay open headings, with the reason.
OPEN_SECTIONS = {
	("Summary", "Needs Attention"): "Staff open the work queue first, so it is never folded away"
}

# Today's breaks of each rule, with the phase of the UX roadmap that fixes them.
LONG_LABELS = {
	("Communications", "Letters Not Yet Shared With Church"): "U6",
	("Finances", "Collection Bank Reconciliation"): "U6",
	("Finances", "Donations Totals by Person"): "U6",
	("Finances", "Fund Transactions By Date"): "U6",
	("Ministries", "Function Attendance Types"): "U6",
	("Ministries", "Function Attendance by Person"): "U6",
	("Ministries", "Function Attendance by Type"): "U6",
	("Ministries", "Ministry Team Assignments"): "U6",
	("Missions", "Missionary Letters Not Yet Read"): "U6",
	("Missions", "Missionary Support Frequencies"): "U6",
}

# Sidebars whose sections are not yet closed folders.
SIDEBARS_WITHOUT_FOLDERS = {
	"Communications": "U6",
	"Finances": "U6",
	"Foundations": "U6",
	"Help": "U6",
	"Ministries": "U6",
	"Missions": "U6",
	"Operations": "U6",
	"Prayers": "U6",
	"Settings": "U6",
	"Study": "U6",
	"Web Site": "U6",
}

# URL items that open a desk route.
DESK_ROUTE_URL_ITEMS = {
	("Operations", "Room Calendar"): "U6",
}


def get_sprite_symbols() -> set[str]:
	"""The symbol ids of the sprites the desk loads from Frappe and Churchit (`app_include_icons`)."""
	symbols = set()
	for app in ("frappe", "churchit"):
		for url in frappe.get_hooks("app_include_icons", app_name=app):
			_, _, owner, *path = url.split("/")
			with open(frappe.get_app_path(owner, "public", *path)) as sprite:
				symbols.update(re.findall(r'<symbol[^>]*\bid="([^"]+)"', sprite.read()))
	return symbols


def is_icon_missing(icon: str, symbols: set[str]) -> bool:
	"""An emoji draws as text; a name is the symbol `icon-<name>`, or `es-<name>` for Espresso."""
	if not icon.isascii():
		return False
	return (icon if icon.startswith("es-") else f"icon-{icon}") not in symbols


def get_folder_problems(sidebar) -> list[tuple[str, str]]:
	"""(label, rule) for each section that is no closed folder and each item that breaks the child rules."""
	problems = []
	section = None
	for item in sidebar.items:
		if item.type == "Section Break":
			section = item
			if (sidebar.name, item.label) not in OPEN_SECTIONS:
				problems += [(item.label, f"needs {flag}") for flag in FOLDER_FLAGS if not item.get(flag)]
		elif item.type == "Link" and section:
			if not item.child:
				problems.append((item.label, "needs child"))
			if item.icon and section.indent:
				problems.append((item.label, "draws no icon under a folder"))
	return problems


def is_desk_route(url: str) -> bool:
	parts = urlsplit(url or "")
	return not parts.netloc and parts.path.lstrip("/").split("/")[0] in ("app", "desk")


class TestNavigationHygiene(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.sidebars = frappe.get_all(
			"Sidebar", filters={"app": "churchit", "standard": 1}, fields=["name", "module"]
		)
		cls.documents = [frappe.get_doc("Sidebar", sidebar.name) for sidebar in cls.sidebars]

	def test_the_dock_names_every_sidebar_churchit_ships(self):
		docked = [row.link_to for row in frappe.get_doc("Dock", "churchit").items]
		self.assertEqual(sorted(docked), sorted(sidebar.name for sidebar in self.sidebars))

	def test_each_module_has_one_sidebar(self):
		modules = [sidebar.module for sidebar in self.sidebars]
		self.assertEqual(sorted({module for module in modules if modules.count(module) > 1}), [])

	def test_each_sidebar_opens_on_a_workspace_of_its_own_module(self):
		wrong = []
		for sidebar in self.sidebars:
			first = next(row for row in frappe.get_doc("Sidebar", sidebar.name).items if row.type == "Link")
			module = first.link_type == "Workspace" and frappe.db.get_value(
				"Workspace", first.link_to, "module"
			)
			if module != sidebar.module:
				wrong.append((sidebar.name, first.link_type, first.link_to))
		self.assertEqual(wrong, [])

	def test_every_icon_is_in_a_sprite_the_desk_loads(self):
		uses = [("Dock", row.title, row.icon) for row in frappe.get_doc("Dock", "churchit").items]
		for sidebar in self.documents:
			uses.append((sidebar.name, "header", sidebar.header_icon))
			uses += [(sidebar.name, item.label, item.icon) for item in sidebar.items]

		symbols = get_sprite_symbols()
		self.assertTrue(symbols, "No sprite was read")
		missing = [use for use in uses if use[2] and is_icon_missing(use[2], symbols)]
		self.assertEqual(missing, [])

	def test_labels_fit_the_sidebar(self):
		found = {
			(sidebar.name, item.label): len(item.label)
			for sidebar in self.documents
			for item in sidebar.items
			if len(item.label or "") > MAX_LABEL_LENGTH
		}
		assert_list_ratchet(self, found, LONG_LABELS, "Sidebar label over 24 characters")

	def test_sections_are_closed_folders_with_icons_and_their_items_are_children(self):
		problems = {sidebar.name: get_folder_problems(sidebar) for sidebar in self.documents}
		found = {name: problem for name, problem in problems.items() if problem}
		assert_list_ratchet(self, found, SIDEBARS_WITHOUT_FOLDERS, "Sidebar sections are not closed folders")

		sections = {
			(sidebar.name, item.label)
			for sidebar in self.documents
			for item in sidebar.items
			if item.type == "Section Break"
		}
		self.assertEqual(
			sorted(set(OPEN_SECTIONS) - sections), [], "Delete the open section from OPEN_SECTIONS"
		)

	def test_no_doctype_is_claimed_by_two_sidebar_items(self):
		"""The desk settles two claims by install order and shell name, and tells no one."""
		claims = {}
		for sidebar in self.documents:
			for item in sidebar.items:
				if item.is_default_module and item.link_to:
					claims.setdefault(item.link_to, []).append(sidebar.name)
		self.assertEqual({name: owners for name, owners in claims.items() if len(owners) > 1}, {})

	def test_no_url_item_opens_a_desk_route(self):
		"""The desk opens every URL item in a new tab; use a doctype's default view or a workspace shortcut."""
		found = {
			(sidebar.name, item.label): item.url
			for sidebar in self.documents
			for item in sidebar.items
			if item.link_type == "URL" and is_desk_route(item.url)
		}
		assert_list_ratchet(self, found, DESK_ROUTE_URL_ITEMS, "URL item opens a desk route")
