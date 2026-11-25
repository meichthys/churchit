# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0", "pillow"]
# ///
"""Take the screenshots shown on churchit.app/screenshots.html and in the manuals.

Each Shot is one feature on that page, and build_docs.py renders the page from
SHOTS. Each ManualShot is one picture in manual/, cropped to the part of the page
that the text talks about. Run it against a site that holds only the sample data,
from the app root:

    uvx --from playwright==1.63.0 playwright install chromium     # once
    uv run docs/screenshots.py                                    # every shot and picture
    uv run docs/screenshots.py rolodex check-in                   # some shots
    uv run docs/screenshots.py people                             # the pictures of one manual
    uv run docs/screenshots.py people/family                      # one picture
    uv run docs/screenshots.py --url https://demo.example.org     # another site
    python docs/screenshots.py --stale <changed files>            # the pictures to look at again

Every shot is taken in both themes, and the reader sees the one that matches theirs.
Shots are written to docs/assets/screenshots/<slug>-<desktop|mobile>-<light|dark>.webp,
and manual pictures to churchit/public/manual/<manual>/<picture>-<light|dark>.webp.
A picture keeps its file name when it is taken again: the wiki and the desk both
notice that its content changed. --stale names the pictures whose doctype, page or
report a change touches: the pre-commit hook and the manual-pictures workflow run it.
"""

import argparse
import glob
import io
import itertools
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import unquote

DOCS = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(DOCS)
MANUAL_PICTURES = os.path.join(APP_ROOT, "churchit", "public", "manual")

# The files of a doctype, page or report that change what its screen looks like.
SCREEN_FILES = (".json", ".js", ".html", ".css")
DEFAULT_URL = "http://churchit.localhost:8000"

# Sample data logins. Each password is the account's own email address.
MANAGER = "mary.johnson@example.com"
MEMBER = "james.wilson@example.com"

DEVICES = {
	"desktop": {"viewport": {"width": 1280, "height": 800}, "device_scale_factor": 2},
	"mobile": {
		"viewport": {"width": 390, "height": 844},
		"device_scale_factor": 2,
		"is_mobile": True,
		"has_touch": True,
	},
}

THEMES = ("light", "dark")

# Frappe opens its Getting Started panel over every workspace for a new login.
HIDE_ONBOARDING = ".onb-panel { display: none !important; }"

# A manual picture leaves out the form's side panel, which the text does not talk about, and the
# handle on the edge of the sidebar.
MANUAL_STYLE = HIDE_ONBOARDING + " .layout-side-section, .sidebar-edge { display: none !important; }"

# Page around the parts of a manual picture, in CSS pixels. It stays inside the desk's page column.
PADDING = 8
PAGE_COLUMN = ".main-section"


@dataclass
class View:
	"""A page to open, and what to do on it before the picture is taken."""

	path: str
	prepare: Callable | None = None
	height: int | None = None  # shorter than the device, for pages with nothing lower down


@dataclass
class Shot:
	slug: str
	title: str
	module: str
	caption: str
	manual: str = ""  # page of the online manual, as <folder>/<page>
	desktop: View | None = None
	mobile: View | None = None
	user: str = MANAGER

	@property
	def views(self):
		return {device: view for device, view in (("desktop", self.desktop), ("mobile", self.mobile)) if view}

	def get_image_path(self, device, theme):
		return f"assets/screenshots/{self.slug}-{device}-{theme}.webp"

	def get_viewport(self, device):
		viewport = dict(DEVICES[device]["viewport"])
		viewport["height"] = self.views[device].height or viewport["height"]
		return viewport


@dataclass
class ManualShot:
	"""A picture for a manual page: the box around the parts of a page that the text talks about."""

	name: str  # <manual>/<picture>, such as people/family
	path: str
	parts: tuple[str, ...]  # Playwright selectors; every element that one matches is in the picture
	prepare: Callable | None = None
	user: str = MANAGER
	height: int = 900  # the window, which also cuts a part that runs further down
	frame: str | None = PAGE_COLUMN  # the picture stays inside it; None for a dialog over the page

	def get_image_path(self, theme):
		return os.path.join(MANUAL_PICTURES, f"{self.name}-{theme}.webp")

	@property
	def screen_folders(self):
		"""The folders of the doctype, page or report whose screen the picture shows, from the app root."""
		route = [unquote(part) for part in self.path.split("?")[0].strip("/").split("/")]
		if route[0] != "desk" or len(route) < 2:
			return []
		kinds, name = (
			(("report",), route[2]) if route[1] == "query-report" else (("doctype", "page"), route[1])
		)
		folder = name.lower().replace(" ", "_").replace("-", "_")
		return sorted(
			os.path.relpath(path, APP_ROOT)
			for kind in kinds
			for path in glob.glob(os.path.join(APP_ROOT, "churchit", "*", kind, folder))
		)


def select_two_wilsons(page):
	page.fill(".station-search", "Wilson")
	members = page.locator(".station-results .member")
	members.first.click()
	members.nth(1).click()


def present_sermon(page):
	"""Open the sample sermon's presentation at its Psalm 23 slide."""
	filters = json.dumps([["title", "=", "The Good Shepherd"]])
	sermons = page.request.get("/api/resource/Sermon", params={"filters": filters}).json()["data"]
	page.goto(f"/sermon_presentation?name={sermons[0]['name']}")
	page.keyboard.press("ArrowRight")


def blur_psalm(page):
	page.locator(".list-group-item").filter(has_text="Psalms 23").get_by_role("link", name="Blur").click()
	for _ in range(3):
		page.click("#blur-plus")


def search_room_bookings(page):
	page.keyboard.press("Control+k")
	page.locator(".modal.show input").wait_for()
	page.keyboard.type("room book")
	page.wait_for_timeout(1000)


def open_shortcuts(page):
	page.keyboard.press("Shift+?")
	page.wait_for_timeout(800)


def hide_directory_cover(page):
	"""Show the families of the preview right under the choices, without its cover page."""
	preview = page.locator("iframe[srcdoc]").element_handle().content_frame()
	preview.wait_for_load_state()
	preview.add_style_tag(content=".cover { display: none !important; }")


def scroll_to_families(page):
	preview = page.locator("iframe[srcdoc]").element_handle().content_frame()
	preview.wait_for_load_state()
	preview.evaluate("window.scrollTo(0, 620)")


SHOTS = [
	Shot(
		slug="desk",
		title="The desk",
		module="Desk",
		caption="The dock on the left holds every part of churchit: people, finances, ministries, missions "
		"and the rest. Open one to see its sidebar and workspace, or search for anything from the bar.",
		desktop=View("/desk/summary", height=600),
		mobile=View("/desk/summary"),
	),
	Shot(
		slug="rolodex",
		title="Rolodex",
		module="People",
		caption="Every person is a card, sorted by last name. Search by name, family, phone or email, call or "
		"text from the card, and save cards to the tray to email or print them together.",
		manual="people/rolodex",
		desktop=View("/desk/rolodex?view=people"),
		mobile=View("/desk/rolodex?view=people"),
	),
	Shot(
		slug="check-in",
		title="Check-In Station",
		module="Ministries",
		caption="Type part of a name or a phone number and the whole family comes up together. Tap the "
		"people who have arrived, and a name tag prints for each of them.",
		manual="ministries/function-check-ins",
		desktop=View("/desk/check-in", select_two_wilsons),
		mobile=View("/desk/check-in", select_two_wilsons),
	),
	Shot(
		slug="sermon",
		title="Sermon slides",
		module="Study",
		caption="A sermon is a list of slides: passages of Scripture, beliefs, songs, missionaries and people "
		"to pray for. Click Present on the sermon and move through it with the arrow keys.",
		manual="study/sermons",
		desktop=View("/desk/sermon", present_sermon),
	),
	Shot(
		slug="bible-memory",
		title="Bible memory",
		module="Study",
		caption="Members keep a list of passages to learn in the portal. Blur hides a few more words each "
		"round, and Type checks the first letter of every word and records the progress.",
		manual="study/bible-memory",
		desktop=View("/memorize", blur_psalm),
	),
	Shot(
		slug="directory",
		title="Church directory",
		module="People",
		caption="Choose what goes in, watch the preview change, and print a directory of your families with "
		"photos, positions, phone numbers and email addresses.",
		manual="people/church-directory",
		desktop=View(
			"/desk/query-report/Church Directory Report?show_photos=1&show_roles=1", scroll_to_families
		),
	),
	Shot(
		slug="bible",
		title="Bible reader",
		module="Study",
		caption="Read one chapter at a time in the desk or on the church website. Every chapter has its own "
		"address, so you can bookmark it or send it to someone.",
		manual="study/bible-reader",
		desktop=View("/desk/bible"),
		mobile=View("/bible"),
	),
	Shot(
		slug="portal",
		title="Member portal",
		module="Website",
		caption="Members sign in on the church website to sign up for events, share prayer requests, download "
		"giving statements and bulletins, and practise their memory verses.",
		manual="website/member-portal",
		desktop=View("/portal"),
		mobile=View("/portal"),
		user=MEMBER,
	),
]


# The parts that most manual pictures show: a form's header and first section, a list, or a page.
FORM_TOP = (".page-head", ".form-section:visible >> nth=0")
FORM_TWO_SECTIONS = (*FORM_TOP, ".form-section:visible >> nth=1")
LIST = (".page-head", ".frappe-list")
PAGE = (".page-head", ".layout-main-section")
DIALOG = ".modal.show .modal-dialog"

MANUAL_SHOTS = [
	ManualShot("people/person", "/desk/person/PRSN-0001", (".page-head", ".form-section:visible >> nth=0")),
	ManualShot(
		"people/family",
		"/desk/family/FAM-0001",
		(".page-head", ".form-section:visible >> nth=0", ".form-section:visible >> nth=1"),
	),
	ManualShot(
		"people/group",
		"/desk/group/GRP-0002",
		(".form-section:visible >> nth=1",),
	),
	ManualShot(
		"people/rolodex",
		"/desk/rolodex?view=people",
		(".rolodex-toolbar", ".rolodex-card >> nth=0", ".rolodex-card >> nth=1"),
	),
	ManualShot(
		"people/care-requests",
		"/desk/care-request/view/kanban/Care Requests",
		(".kanban-v2-container",),
		height=430,
	),
	ManualShot(
		"people/follow-up",
		"/desk/follow-up-card/view/kanban/Newcomer Follow-up",
		(".kanban-v2-container",),
		height=400,
	),
	ManualShot(
		"people/church-directory",
		"/desk/query-report/Church Directory Report?show_photos=1&show_roles=1",
		(".page-form", "iframe[srcdoc]"),
		hide_directory_cover,
		height=700,
	),
	ManualShot(
		"people/connection-cards",
		"/desk/connection-card/CONN-00001",
		(".page-head", ".form-section:visible >> nth=0"),
	),
	ManualShot("foundations/churches", "/desk/church/CHR-01", FORM_TOP),
	ManualShot("foundations/beliefs", "/desk/belief/god", FORM_TOP),
	ManualShot("foundations/sample-data", "/desk/sample-data", PAGE, height=560),
	ManualShot("foundations/weekly-metrics", "/desk/weekly-metrics/CHR-01-2026-11-01", FORM_TOP),
	ManualShot("finances/collections", "/desk/collection/COLL-0001", FORM_TWO_SECTIONS),
	ManualShot("finances/funds", "/desk/fund/FUND-0002", FORM_TOP),
	ManualShot("finances/expenses", "/desk/expense/EXP-0001", FORM_TOP),
	ManualShot("finances/budgets", "/desk/church-budget/BUDGET%202026-01-01%20to%202026-12-31", FORM_TOP),
	ManualShot("finances/pledges", "/desk/pledge-campaign/PCMP-0001", FORM_TOP),
	ManualShot("finances/vendors", "/desk/vendor", LIST, height=480),
	ManualShot("finances/alms", "/desk/alms-request/ALMS-0001", FORM_TOP),
	ManualShot("ministries/functions", "/desk/function/FUNC-0001", FORM_TOP),
	ManualShot("ministries/function-check-ins", "/desk/check-in", (".check-in-station",), select_two_wilsons),
	ManualShot("ministries/function-sign-ups", "/desk/function-sign-up/FSU-000001", FORM_TOP),
	ManualShot("ministries/ministries", "/desk/ministry/MIN-002", FORM_TOP),
	ManualShot("ministries/question-sets", "/desk/question-set/QSET-0001", FORM_TWO_SECTIONS),
	ManualShot("ministries/songs", "/desk/song/SONG-0001", FORM_TOP),
	ManualShot("ministries/counseling-cases", "/desk/counseling-case/CC-0001", FORM_TOP),
	ManualShot("missions/missionaries", "/desk/missionary/MISS-001", FORM_TOP),
	ManualShot("missions/missionary-agencies", "/desk/missionary-agency/MA-001", FORM_TOP),
	ManualShot("prayers/prayer-request", "/desk/prayer-request/PREQ-0001", FORM_TOP),
	ManualShot("prayers/prayers", "/desk/prayer/PRAY-0001", FORM_TOP),
	ManualShot("study/sermons", "/desk/sermon/SRMN-0001", FORM_TOP),
	ManualShot("study/sermon-handouts", "/desk/sermon-handout/HAND-0001", FORM_TOP),
	ManualShot("study/bible-memory", "/desk/bible-memory-item/BMEM-000001", FORM_TOP),
	ManualShot("study/bible-reader", "/desk/bible", PAGE, height=640),
	ManualShot("study/translations", "/desk/bible-translation", LIST, height=480),
	ManualShot("communications/church-emails", "/desk/church-email/EML-0001", FORM_TOP),
	ManualShot("communications/bulletins", "/desk/bulletin/BUL-0001", FORM_TOP),
	ManualShot("communications/consent", "/desk/communication-consent/CONS-00001", FORM_TOP),
	ManualShot("operations/rooms", "/desk/room/ROOM-0001", FORM_TOP),
	ManualShot("operations/room-bookings", "/desk/room-booking/BK-0001", FORM_TOP),
	ManualShot("operations/assets", "/desk/church-asset/ASSET-0001", FORM_TOP),
	ManualShot(
		"operations/tasks",
		"/desk/church-task/view/kanban/Church Tasks",
		(".kanban-v2-container",),
		height=430,
	),
	ManualShot("operations/meeting-minutes", "/desk/meeting-minutes/MM-0001", FORM_TOP),
	ManualShot("operations/locations", "/desk/church-location/view/tree", PAGE, height=480),
	ManualShot("website/website", "/desk/web-page", LIST, height=480),
	ManualShot("help/search", "/desk/people", (DIALOG,), search_room_bookings, frame=DIALOG),
	ManualShot("help/keyboard-shortcuts", "/desk/people", (DIALOG,), open_shortcuts, frame=DIALOG),
]


def capture(base_url, shots, manual_shots):
	from playwright.sync_api import sync_playwright

	os.makedirs(os.path.join(DOCS, "assets", "screenshots"), exist_ok=True)
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch()
		for shot in shots:
			for device, theme in itertools.product(shot.views, THEMES):
				take(browser, base_url, shot, device, theme)
		for shot, theme in itertools.product(manual_shots, THEMES):
			take_manual(browser, base_url, shot, theme)
		browser.close()


def take(browser, base_url, shot, device, theme):
	context = browser.new_context(
		base_url=base_url,
		color_scheme=theme,
		**{**DEVICES[device], "viewport": shot.get_viewport(device)},
	)
	page = context.new_page()
	log_in(page, shot.user)
	open_view(page, shot.views[device], theme)
	png = page.screenshot(animations="disabled", caret="hide")
	save(png, os.path.join(DOCS, shot.get_image_path(device, theme)))
	context.close()


def take_manual(browser, base_url, shot, theme):
	context = browser.new_context(
		base_url=base_url,
		color_scheme=theme,
		viewport={"width": DEVICES["desktop"]["viewport"]["width"], "height": shot.height},
		device_scale_factor=2,
	)
	page = context.new_page()
	log_in(page, shot.user)
	open_view(page, View(shot.path, shot.prepare), theme, MANUAL_STYLE)
	png = page.screenshot(clip=get_clip(page, shot), animations="disabled", caret="hide")
	path = shot.get_image_path(theme)
	os.makedirs(os.path.dirname(path), exist_ok=True)
	save(png, path)
	context.close()


def get_clip(page, shot):
	"""The box around every element that the parts of *shot* match, with some page around it, inside the window."""
	boxes = [element.bounding_box() for selector in shot.parts for element in page.locator(selector).all()]
	boxes = [box for box in boxes if box and box["width"] and box["height"]]
	if not boxes:
		raise SystemExit(f"{shot.name}: nothing on {shot.path} matches {shot.parts}")
	viewport = page.viewport_size
	column = page.locator(shot.frame) if shot.frame else None
	frame = (column and column.count() and column.first.bounding_box()) or {
		"x": 0,
		"width": viewport["width"],
	}
	left = max(min(box["x"] for box in boxes) - PADDING, frame["x"])
	top = max(min(box["y"] for box in boxes) - PADDING, 0)
	right = min(max(box["x"] + box["width"] for box in boxes) + PADDING, frame["x"] + frame["width"])
	bottom = min(max(box["y"] + box["height"] for box in boxes) + PADDING, viewport["height"])
	return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def save(png, path):
	from PIL import Image

	Image.open(io.BytesIO(png)).save(path, quality=85, method=6)
	print(f"Saved {os.path.relpath(path, os.path.dirname(DOCS))}")


def log_in(page, user):
	response = page.request.post("/api/method/login", form={"usr": user, "pwd": user})
	if not response.ok:
		raise SystemExit(f"Could not log in as {user}. Is the sample data loaded? ({response.status})")


def open_view(page, view, theme, style=HIDE_ONBOARDING):
	page.goto(view.path)
	page.wait_for_load_state("networkidle")
	page.add_style_tag(content=style)
	if view.prepare:
		view.prepare(page)
		page.wait_for_load_state("networkidle")
	set_theme(page, theme)
	page.evaluate("document.fonts.ready")
	page.wait_for_timeout(500)


def set_theme(page, theme):
	"""Flip the page the way its own switch does, without saving the choice to the sample user."""
	page.evaluate(
		"""theme => {
			document.documentElement.setAttribute("data-theme-mode", theme);
			document.documentElement.setAttribute("data-theme", theme);
		}""",
		theme,
	)


def get_stale_shots(paths):
	"""The manual pictures whose screen a change to *paths* (from the app root) may have changed."""
	changed = [os.path.normpath(path) for path in paths if path.endswith(SCREEN_FILES)]
	return [
		shot
		for shot in MANUAL_SHOTS
		if any(path.startswith(folder + os.sep) for folder in shot.screen_folders for path in changed)
	]


def print_stale_shots(paths):
	"""Name each picture to look at again. On GitHub, each one is a warning on the pull request."""
	shots = get_stale_shots(paths)
	if not shots:
		return
	names = " ".join(shot.name for shot in shots)
	if os.environ.get("GITHUB_ACTIONS"):
		for shot in shots:
			print(
				f"::warning title=Manual picture::{shot.name} may show an old screen. Look at it, and take it again if it changed."
			)
	print(f"These manual pictures show a screen that this change touches: {names}")
	print(f"Look at each one, and take it again if the screen changed: uv run docs/screenshots.py {names}")


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("names", nargs="*", help="shots, manuals or manual pictures to take (default: all)")
	parser.add_argument("--url", default=DEFAULT_URL, help=f"site to photograph (default: {DEFAULT_URL})")
	parser.add_argument(
		"--stale",
		action="store_true",
		help="name the manual pictures that the changed files given may make old",
	)
	args = parser.parse_args()
	if args.stale:
		print_stale_shots(args.names)
		return
	names = set(args.names)
	manual_names = {shot.name for shot in MANUAL_SHOTS} | {shot.name.split("/")[0] for shot in MANUAL_SHOTS}
	unknown = names - {shot.slug for shot in SHOTS} - manual_names
	if unknown:
		parser.error(f"unknown shots: {', '.join(sorted(unknown))}")
	capture(
		args.url,
		[shot for shot in SHOTS if not names or shot.slug in names],
		[shot for shot in MANUAL_SHOTS if not names or {shot.name, shot.name.split("/")[0]} & names],
	)


if __name__ == "__main__":
	main()
