# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.63.0"]
# ///
"""Drive a churchit site in headless Chromium with commands read from stdin.

	uv run .claude/skills/run-churchit/driver.py <<'EOF'
	login mary.johnson@example.com
	nav /desk/rolodex?view=people
	shot rolodex
	errors
	EOF

One command per line; blank lines and lines starting with # are skipped. The
first failing command takes a screenshot named `failed` and exits 1.
"""

import argparse
import json
import os
import shlex
import sys

DEFAULT_URL = "http://churchit.localhost:8000"
DEFAULT_OUT = "/tmp/churchit-shots"

# Frappe opens its Getting Started panel over every workspace for a sample user.
HIDE_ONBOARDING = ".onb-panel { display: none !important; }"

DEVICES = {
	"desktop": {"viewport": {"width": 1280, "height": 800}},
	"mobile": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
}


class Driver:
	"""One browser page; each public method is a command of the same name."""

	def __init__(self, page, out_dir):
		self.page = page
		self.out_dir = out_dir
		self.console_errors = []
		page.on("console", self.record_console)
		page.on("pageerror", lambda error: self.console_errors.append(f"pageerror: {error}"))
		page.on("response", self.record_response)

	def run(self, line):
		name, _, rest = line.strip().partition(" ")
		arguments = [rest] if name == "eval" else shlex.split(rest)
		command = getattr(self, name.replace("-", "_"), None)
		if not command or name.startswith("_") or name == "run":
			raise SystemExit(f"Unknown command: {name}")
		command(*arguments)

	def login(self, user, password=None):
		"""Sample-data passwords equal the email; Administrator's dev password is `admin`."""
		password = password or ("admin" if user == "Administrator" else user)
		response = self.page.request.post("/api/method/login", form={"usr": user, "pwd": password})
		if not response.ok:
			raise RuntimeError(f"login {user} failed with HTTP {response.status}")
		print(f"logged in as {user}")

	def nav(self, path):
		self.page.goto(path)
		self.page.wait_for_load_state("networkidle")
		self.page.add_style_tag(content=HIDE_ONBOARDING)
		print(f"at {self.page.url}")

	def wait(self, selector):
		self.page.locator(selector).first.wait_for(state="visible")

	def wait_url(self, pattern):
		"""Wait for a glob such as `**/desk/person/PRSN-*`; a form's URL changes once it saves."""
		self.page.wait_for_url(pattern)
		print(f"at {self.page.url}")

	def click(self, selector):
		self.page.locator(selector).first.click()

	def fill(self, selector, text):
		self.page.locator(selector).first.fill(text)

	def press(self, key):
		self.page.keyboard.press(key)

	def text(self, selector):
		print(self.page.locator(selector).first.inner_text())

	def eval(self, expression):
		"""Evaluate the rest of the line as JS in the page; a returned promise is awaited."""
		print(json.dumps(self.page.evaluate(expression), indent=1, default=str))

	def url(self):
		print(self.page.url)

	def viewport(self, width, height):
		"""The desk scrolls `.main-section`, not the page, so a full-page shot needs a taller window."""
		self.page.set_viewport_size({"width": int(width), "height": int(height)})

	def sleep(self, milliseconds):
		self.page.wait_for_timeout(int(milliseconds))

	def shot(self, name="screenshot"):
		path = os.path.join(self.out_dir, f"{name}.png")
		self.page.screenshot(path=path, full_page=True, animations="disabled", caret="hide")
		print(f"saved {path}")

	def errors(self):
		print("\n".join(self.console_errors) or "no errors")

	def record_console(self, message):
		if message.type == "error":
			self.console_errors.append(f"console: {message.text}")

	def record_response(self, response):
		"""The console names only the status of a failed request, not its URL."""
		if response.status >= 400:
			self.console_errors.append(f"http {response.status}: {response.request.method} {response.url}")


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--url", default=DEFAULT_URL, help=f"site to drive (default: {DEFAULT_URL})")
	parser.add_argument("--out", default=DEFAULT_OUT, help=f"screenshot folder (default: {DEFAULT_OUT})")
	parser.add_argument("--device", choices=DEVICES, default="desktop")
	parser.add_argument("--theme", choices=("light", "dark"), default="light")
	args = parser.parse_args()
	os.makedirs(args.out, exist_ok=True)
	run_script(args, sys.stdin.read().splitlines())


def run_script(args, lines):
	from playwright.sync_api import sync_playwright

	with sync_playwright() as playwright:
		browser = playwright.chromium.launch()
		context = browser.new_context(base_url=args.url, color_scheme=args.theme, **DEVICES[args.device])
		driver = Driver(context.new_page(), args.out)
		for line in lines:
			if line.strip() and not line.lstrip().startswith("#"):
				print(f"> {line.strip()}", flush=True)
				run_line(driver, line)
		browser.close()


def run_line(driver, line):
	try:
		driver.run(line)
	except Exception as error:
		print(f"FAILED: {line.strip()}\n{type(error).__name__}: {error}", file=sys.stderr)
		driver.shot("failed")
		driver.errors()
		raise SystemExit(1) from error


if __name__ == "__main__":
	main()
