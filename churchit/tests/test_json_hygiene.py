# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""No record the app ships as JSON carries a `modified` time that has not come yet.

Migrate imports a record file (a doctype, report, workspace, sidebar, web form, notification,
print format or fixture) only when its `modified` is newer than the row in the database, and then
stores the file's time on the row. A file stamped in the future makes every later edit made before
that time look older than the database, so migrate skips it with no error. Stamp a hand edit with
the real time: `date '+%F %T'`.
"""

import json
import os
import re
from datetime import datetime

from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_datetime

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Templates and built assets that are served as they are, not imported as records.
NOT_RECORDS = ("www", "public", "node_modules")
# The repository was renamed from church to churchit.
OLD_REPOSITORY = re.compile(r"github\.com/meichthys/church(?!it)")


def record_files():
	for root, dirs, files in os.walk(APP_DIR):
		dirs[:] = [name for name in dirs if name not in NOT_RECORDS]
		for name in files:
			if name.endswith(".json"):
				yield os.path.join(root, name)


def stamped_records(path):
	"""(record name, modified) for the record in *path*, or each record of a fixture list."""
	with open(path) as file:
		data = json.load(file)
	for record in data if isinstance(data, list) else [data]:
		if isinstance(record, dict) and record.get("modified"):
			yield record.get("name"), record["modified"]


class TestRecordTimestamps(FrappeTestCase):
	def test_no_record_is_stamped_in_the_future(self):
		"""Against the machine's clock, which `date` reads: a test site without a time zone runs ahead of it."""
		now = datetime.now()
		future = [
			f"{os.path.relpath(path, APP_DIR)} ({name}: {modified})"
			for path in record_files()
			for name, modified in stamped_records(path)
			if get_datetime(modified) > now
		]
		assert not future, (
			"These records carry a `modified` time later than now, so migrate will skip real edits "
			"made before it. Set it to the current time: " + ", ".join(sorted(future))
		)


class TestRepositoryLinks(FrappeTestCase):
	def test_no_record_links_to_the_old_repository(self):
		stale = []
		for path in record_files():
			with open(path) as file:
				if OLD_REPOSITORY.search(file.read()):
					stale.append(os.path.relpath(path, APP_DIR))
		assert not stale, "Change github.com/meichthys/church to .../churchit in: " + ", ".join(sorted(stale))
