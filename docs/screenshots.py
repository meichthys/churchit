# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0", "pillow"]
# ///
"""Take the screenshots shown on churchit.app/screenshots.html.

Each Shot is one feature on that page, and build_docs.py renders the page from
SHOTS. Run it against a site that holds only the sample data, from the app root:

    uvx --from playwright==1.63.0 playwright install chromium     # once
    uv run docs/screenshots.py                                    # every shot
    uv run docs/screenshots.py rolodex check-in                   # some shots
    uv run docs/screenshots.py --url https://demo.example.org     # another site

Every shot is taken in both themes, and the site shows the one that matches the
reader's. Images are written to docs/assets/screenshots/<slug>-<desktop|mobile>-<light|dark>.webp.
"""

import argparse
import io
import itertools
import json
import os
from collections.abc import Callable
from dataclasses import dataclass

DOCS = os.path.dirname(os.path.abspath(__file__))
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
	manual: str = ""  # documentation.html anchor
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
		manual="people-rolodex",
		desktop=View("/desk/rolodex?view=people"),
		mobile=View("/desk/rolodex?view=people"),
	),
	Shot(
		slug="check-in",
		title="Check-In Station",
		module="Ministries",
		caption="Type part of a name or a phone number and the whole family comes up together. Tap the "
		"people who have arrived, and a name tag prints for each of them.",
		manual="ministries-function-check-ins",
		desktop=View("/desk/check-in", select_two_wilsons),
		mobile=View("/desk/check-in", select_two_wilsons),
	),
	Shot(
		slug="sermon",
		title="Sermon slides",
		module="Study",
		caption="A sermon is a list of slides: passages of Scripture, beliefs, songs, missionaries and people "
		"to pray for. Click Present on the sermon and move through it with the arrow keys.",
		manual="study-sermons",
		desktop=View("/desk/sermon", present_sermon),
	),
	Shot(
		slug="bible-memory",
		title="Bible memory",
		module="Study",
		caption="Members keep a list of passages to learn in the portal. Blur hides a few more words each "
		"round, and Type checks the first letter of every word and records the progress.",
		manual="study-bible-memory",
		desktop=View("/memorize", blur_psalm),
	),
	Shot(
		slug="directory",
		title="Church directory",
		module="People",
		caption="Choose what goes in, watch the preview change, and print a directory of your families with "
		"photos, positions, phone numbers and email addresses.",
		manual="people-church-directory",
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
		manual="study-bible-reader",
		desktop=View("/desk/bible"),
		mobile=View("/bible"),
	),
	Shot(
		slug="portal",
		title="Member portal",
		module="Website",
		caption="Members sign in on the church website to sign up for events, share prayer requests, download "
		"giving statements and bulletins, and practise their memory verses.",
		manual="website-user-portal",
		desktop=View("/portal"),
		mobile=View("/portal"),
		user=MEMBER,
	),
]


def capture(base_url, shots):
	from playwright.sync_api import sync_playwright

	os.makedirs(os.path.join(DOCS, "assets", "screenshots"), exist_ok=True)
	with sync_playwright() as playwright:
		browser = playwright.chromium.launch()
		for shot in shots:
			for device, theme in itertools.product(shot.views, THEMES):
				take(browser, base_url, shot, device, theme)
		browser.close()


def take(browser, base_url, shot, device, theme):
	from PIL import Image

	context = browser.new_context(
		base_url=base_url,
		color_scheme=theme,
		**{**DEVICES[device], "viewport": shot.get_viewport(device)},
	)
	page = context.new_page()
	log_in(page, shot.user)
	open_view(page, shot.views[device], theme)
	png = page.screenshot(animations="disabled", caret="hide")
	path = shot.get_image_path(device, theme)
	Image.open(io.BytesIO(png)).save(os.path.join(DOCS, path), quality=85, method=6)
	print(f"Saved {path}")
	context.close()


def log_in(page, user):
	response = page.request.post("/api/method/login", form={"usr": user, "pwd": user})
	if not response.ok:
		raise SystemExit(f"Could not log in as {user}. Is the sample data loaded? ({response.status})")


def open_view(page, view, theme):
	page.goto(view.path)
	page.wait_for_load_state("networkidle")
	page.add_style_tag(content=HIDE_ONBOARDING)
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


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("slugs", nargs="*", help="shots to take (default: all)")
	parser.add_argument("--url", default=DEFAULT_URL, help=f"site to photograph (default: {DEFAULT_URL})")
	args = parser.parse_args()
	unknown = set(args.slugs) - {shot.slug for shot in SHOTS}
	if unknown:
		parser.error(f"unknown shots: {', '.join(sorted(unknown))}")
	capture(args.url, [shot for shot in SHOTS if not args.slugs or shot.slug in args.slugs])


if __name__ == "__main__":
	main()
