# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""House style the repo enforces rather than reviews.

See the House style section of AGENTS.md for the rule and how to rewrite around it.
"""

import os
import re

from frappe.tests.utils import FrappeTestCase

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_DIR = os.path.dirname(APP_DIR)

# Em dash and en dash, assembled from their parts so this file does not trip its
# own check and needs no exemption from it. Each arrives in three shapes: the
# character itself, an HTML entity, and the unicode escape JSON and JavaScript
# string literals use.
DASH_CHARACTERS = f"[{chr(0x2014)}{chr(0x2013)}]"
DASH_ENTITIES = [f"&{prefix}dash;" for prefix in ("m", "n")]
DASH_ESCAPES = r"\\u201[34]"
DASHES = re.compile("|".join([DASH_CHARACTERS, DASH_ESCAPES, *DASH_ENTITIES]))

SCANNED = (".py", ".md", ".html", ".js", ".json", ".txt", ".css", ".scss")
SKIPPED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "env"}


def scanned_files():
	for root, dirs, files in os.walk(REPO_DIR):
		dirs[:] = [name for name in dirs if name not in SKIPPED_DIRS]
		for name in files:
			if name.endswith(SCANNED):
				yield os.path.join(root, name)


class TestNoDashes(FrappeTestCase):
	def test_nothing_ships_an_em_dash_or_an_en_dash(self):
		"""Rewrite the sentence rather than swapping in a hyphen; AGENTS.md says how."""
		offenders = []
		for path in scanned_files():
			try:
				lines = open(path, encoding="utf-8").read().splitlines()
			except UnicodeDecodeError:
				continue
			for number, line in enumerate(lines, start=1):
				if DASHES.search(line):
					offenders.append(f"{os.path.relpath(path, REPO_DIR)}:{number}")

		self.assertEqual(
			sorted(offenders),
			[],
			"These lines carry an em dash or en dash. Rewrite the sentence: a comma pair, "
			"parentheses, a colon, a full stop, or 'to' for a range. See AGENTS.md.",
		)
