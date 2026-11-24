# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The manuals are written in manual/ and built into the Manual workspaces: the two must agree.

A change to a Markdown file that nobody built never reaches the desk, and a hand edit of the
workspace JSON is lost at the next build. Frappe Wiki syncs the same folder, so each page needs the
front matter that both read, a link must name another page of the manual, a callout must be one
that the wiki draws, and a picture needs its light and its dark image in churchit/public/manual,
where docs/screenshots.py writes them.
"""

import glob
import json
import os
import re

from frappe.tests.utils import FrappeTestCase

from churchit.manual_sources import (
	APP_ROOT,
	ONLINE_MANUAL,
	PICTURE,
	PICTURE_DARK,
	PICTURE_LIGHT,
	PUBLIC,
	SOURCES,
	build_all,
	get_blocks,
	get_chunks,
	get_folders,
	get_pages,
	inline,
	read_source,
	to_blocks,
)

CALLOUT_OPENER = re.compile(r"(note|tip|caution|danger)(\[[^\]]+\])?")
PICTURES = os.path.join(PUBLIC, "manual")


def get_sources() -> list[str]:
	return sorted(glob.glob(os.path.join(SOURCES, "**", "*.md"), recursive=True))


def read(path: str) -> str:
	with open(path, encoding="utf-8") as file:
		return file.read()


def get_anchors(path: str) -> set[str]:
	"""The ids that Frappe Wiki gives the headings of a page (slugify in wiki/wiki/markdown.py)."""
	anchors = set()
	for heading in re.findall(r"^#{2,6} (.+)$", read(path), re.M):
		anchor = re.sub(r"[^\w\-]", "", re.sub(r"\s+", "-", heading.lower())).strip("-")
		anchors.add(re.sub(r"-+", "-", anchor))
	return anchors


def get_picture_problem(path: str, picture: str) -> str | None:
	"""What is wrong with a <picture> on the page at *path*, or None."""
	dark, light = PICTURE_DARK.search(picture), PICTURE_LIGHT.search(picture)
	if not (dark and light and light.group(2)):
		return "needs a dark <source srcset>, and an <img src> with alt text"
	if not (dark.group(1).endswith("-dark.webp") and light.group(1).endswith("-light.webp")):
		return "names its images <picture>-dark.webp and <picture>-light.webp"
	for source in (dark.group(1), light.group(1)):
		image = os.path.normpath(os.path.join(os.path.dirname(path), source))
		if not image.startswith(PICTURES + os.sep) or not os.path.exists(image):
			return f"{source} is not in churchit/public/manual: run uv run docs/screenshots.py"
	return None


def is_link_broken(path: str, target: str) -> bool:
	"""Whether *target*, linked from the page at *path*, is neither a website nor a page of the manual."""
	if target.startswith(("https://", "mailto:")):
		return False
	page, _, anchor = target.partition("#")
	page_path = os.path.normpath(os.path.join(os.path.dirname(path), page)) if page else path
	if not page_path.endswith(".md") or not os.path.exists(page_path):
		return True
	return bool(anchor) and anchor not in get_anchors(page_path)


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

	def test_every_link_opens_a_page_of_the_manual_or_a_website(self):
		"""A site path such as /desk/person opens nothing on the wiki, which is a site of its own."""
		broken = [
			(os.path.relpath(path, SOURCES), target)
			for path in get_sources()
			for target in re.findall(r"\]\(([^)\s]+)\)", read(path))
			if is_link_broken(path, target)
		]
		self.assertEqual(broken, [])

	def test_every_callout_is_closed_and_of_a_type_that_the_wiki_draws(self):
		wrong = []
		for path in get_sources():
			fences = re.findall(r"^:::(.*)$", read(path), re.M)
			openers, closers = fences[0::2], fences[1::2]
			if (
				len(fences) % 2
				or any(closers)
				or not all(CALLOUT_OPENER.fullmatch(fence) for fence in openers)
			):
				wrong.append(os.path.relpath(path, SOURCES))
		self.assertEqual(wrong, [])

	def test_every_picture_has_a_light_and_a_dark_image_and_a_description(self):
		problems = [
			(os.path.relpath(path, SOURCES), problem)
			for path in get_sources()
			for picture in PICTURE.findall(read(path))
			if (problem := get_picture_problem(path, picture))
		]
		self.assertEqual(problems, [])

	def test_every_picture_file_is_on_a_page(self):
		used = {
			os.path.normpath(os.path.join(os.path.dirname(path), source))
			for path in get_sources()
			for source in re.findall(r'(?:src|srcset)="([^"]+)"', read(path))
		}
		files = set(glob.glob(os.path.join(PICTURES, "**", "*.webp"), recursive=True))
		self.assertEqual(sorted(os.path.relpath(path, APP_ROOT) for path in files - used), [])

	def test_a_picture_is_a_picture_element(self):
		"""A Markdown image has no dark version, and the desk build does not draw one."""
		self.assertEqual([os.path.relpath(path, SOURCES) for path in get_sources() if "![" in read(path)], [])

	def test_a_picture_shows_the_image_of_the_desks_theme(self):
		source = "../../churchit/public/manual/people/person"
		chunks = get_chunks(
			f'<picture>\n  <source srcset="{source}-dark.webp" media="(prefers-color-scheme: dark)">\n'
			f'  <img src="{source}-light.webp" alt="A Person">\n</picture>',
			1,
		)
		text = to_blocks(chunks, "people")[0]["data"]["text"]

		self.assertRegex(
			text,
			r'^<img class="manual-image manual-image-light" src="/assets/churchit/manual/people/person-light\.webp\?v=\w{8}" alt="A Person">'
			r'<img class="manual-image manual-image-dark" src="/assets/churchit/manual/people/person-dark\.webp\?v=\w{8}" alt="A Person">$',
		)

	def test_a_table_is_a_table_and_a_diagram_a_link_in_the_desk(self):
		chunks = get_chunks(
			"| Role | Meaning |\n| :--- | :--- |\n| **Adult** | A parent |\n\n```mermaid\nflowchart LR\n  A --> B\n```",
			1,
			"people/family",
		)

		self.assertEqual(
			[block["data"]["text"] for block in to_blocks(chunks, "people")],
			[
				'<table class="manual-table"><tr><th>Role</th><th>Meaning</th></tr>'
				"<tr><td><b>Adult</b></td><td>A parent</td></tr></table>",
				f'<i><a href="{ONLINE_MANUAL}/people/family" target="_blank">See the diagram in the online manual</a></i>',
			],
		)

	def test_a_callout_is_one_desk_block_led_by_its_title(self):
		chunks = get_chunks(":::caution[Careful]\nYou cannot undo it.\n:::\n\nNext.", 1)

		self.assertEqual(
			[block["data"]["text"] for block in to_blocks(chunks, "people")],
			[
				'<span class="manual-callout manual-callout-caution">Careful</span><br>You cannot undo it.',
				"Next.",
			],
		)

	def test_a_link_within_a_manual_is_plain_text_in_the_desk(self):
		"""The desk shows a whole manual on one page, so the link would open the page that is open."""
		self.assertEqual(inline("See [Groups](group.md#lead-a-group).", "people"), "See Groups.")

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
