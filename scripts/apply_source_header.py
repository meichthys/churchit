"""Replace the copyright header Frappe writes into generated files.

Frappe scaffolds every new controller, test and client script from templates in
frappe/core/doctype/doctype/boilerplate, and the header there is fixed: there is
no hook to change it. This runs as a pre-commit hook instead, so a contributor
who adds a DocType gets the app's notice without having to remember it.

Files that carry no header are left alone.
"""

import re
import sys
from pathlib import Path

NOTICE = (
	"This source code is freely given for the sake of the gospel (Matthew 10:8)",
	"and is licensed under MIT No Attribution (MIT-0).",
)

COPYRIGHT = re.compile(r"^(#|//)\s*Copyright \(c\) \d{4},\s*.+ and [Cc]ontributors\s*$")
LICENSE_POINTER = re.compile(
	r"^(#|//)\s*(For license information, please see license\.txt|See license\.txt|License: MIT\.)\s*$"
)


def rewrite(path: Path) -> bool:
	"""Swap the header in *path*. Returns whether the file changed."""
	lines = path.read_text().splitlines(keepends=True)
	if not lines or not COPYRIGHT.match(lines[0]):
		return False

	comment = "#" if path.suffix == ".py" else "//"
	drop = 2 if len(lines) > 1 and LICENSE_POINTER.match(lines[1]) else 1
	header = [f"{comment} {line}\n" for line in NOTICE]

	path.write_text("".join(header + lines[drop:]))
	return True


def main(argv: list[str]) -> int:
	changed = [
		path
		for path in (Path(name) for name in argv)
		if path.suffix in {".py", ".js"} and path.is_file() and rewrite(path)
	]
	for path in changed:
		print(f"rewrote header: {path}")

	# Non-zero tells pre-commit the files were modified, so the commit is retried.
	return 1 if changed else 0


if __name__ == "__main__":
	raise SystemExit(main(sys.argv[1:]))
