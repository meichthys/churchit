# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Build the Manual: <Module> workspaces and Help from the Markdown in manual/.

    python docs/build_manuals.py           # write the workspace JSON that changed
    python docs/build_manuals.py --check   # only list the workspace JSON that is out of date

Then run migrate, so that the site shows the new text. Standard library only.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from churchit.manual_sources import build_all

if __name__ == "__main__":
	check = "--check" in sys.argv
	changed = build_all(check=check)
	for path in changed:
		print(("Out of date: " if check else "Wrote ") + path)
	sys.exit(1 if check and changed else 0)
