# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The manuals are written in manual/ and built into the Manual workspaces: the two must agree.

A change to a Markdown file that nobody built never reaches the desk, and a hand edit of the
workspace JSON is lost at the next build. Frappe Wiki syncs the same folder, so each page needs the
front matter that both read.
"""

import glob
import json
import os

from frappe.tests.utils import FrappeTestCase

from churchit.manual_sources import (
	APP_ROOT,
	SOURCES,
	build_all,
	get_blocks,
	get_folders,
	get_pages,
	inline,
	read_source,
)


class TestManualHygiene(FrappeTestCase):
	def test_every_workspace_is_built_from_its_markdown(self):
		self.assertEqual(build_all(check=True), [], "Run: python docs/build_manuals.py")

	def test_every_manual_workspace_has_a_folder(self):
		built = {read_source(os.path.join(folder, "README.md"))[0]["workspace"] for folder in get_folders()}
		manuals = glob.glob(
			os.path.join(APP_ROOT, "churchit", "*", "workspace", "manual:_*", "manual:_*.json")
		)

		self.assertEqual({os.path.relpath(path, APP_ROOT) for path in manuals} - built, set())

	def test_every_page_has_a_title_and_a_position(self):
		for folder in get_folders():
			pages = glob.glob(os.path.join(folder, "*.md"))
			missing = [
				os.path.relpath(path, SOURCES)
				for path in pages
				if not path.endswith("README.md")
				and not {"title", "sidebar_position"} <= set(read_source(path)[0])
			]
			self.assertEqual(missing, [])

	def test_page_titles_are_unique_in_a_manual(self):
		for folder in get_folders():
			titles = [page["title"] for page, _ in get_pages(folder)]
			self.assertEqual(len(titles), len(set(titles)), folder)

	def test_the_wiki_sidebar_lists_every_folder(self):
		with open(os.path.join(SOURCES, ".wiki.json"), encoding="utf-8") as file:
			sidebar = json.load(file)["sidebar"]
		listed = {entry["autogenerate"]["directory"] for entry in sidebar if isinstance(entry, dict)}

		self.assertEqual({os.path.basename(folder) for folder in get_folders()}, listed)

	def test_a_link_to_another_page_opens_its_manual_in_the_desk(self):
		self.assertEqual(
			inline("See [Groups](../people/group.md#joining-a-group).", "missions"),
			'See <a href="/desk/manual%3A-people">Groups</a>.',
		)

	def test_code_shows_its_text(self):
		self.assertEqual(
			inline("Type `<Response>` and `&amp;`.", "finances"),
			"Type <code>&lt;Response&gt;</code> and <code>&amp;amp;</code>.",
		)

	def test_block_ids_stay_while_the_text_does(self):
		folder = os.path.join(SOURCES, "missions")

		self.assertEqual(
			[block["id"] for block in get_blocks(folder)], [block["id"] for block in get_blocks(folder)]
		)
