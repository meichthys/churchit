# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, today

from churchit.church_communications.report.letters_to_be_shared import letters_to_be_shared
from churchit.church_missions.report.missionary_letters import missionary_letters
from churchit.church_missions.report.missionary_letters_not_yet_read import (
	missionary_letters_not_yet_read,
)
from churchit.church_people.report.people_letters_not_yet_read import people_letters_not_yet_read
from churchit.tests.helpers import RollbackEachTest


class TestLetter(RollbackEachTest):
	def letters(self, parent, rows):
		for row in rows:
			parent.append("letters", {"share_with_church": 1, **row})
		parent.insert(ignore_permissions=True)
		return parent

	def contents(self, report):
		return [row["content"] for row in report.get_data({})]

	def test_a_private_letter_is_never_listed_to_be_read_to_the_church(self):
		rows = [
			{"date": today(), "content": "_Open note"},
			{"date": today(), "content": "_Private note", "is_private": 1},
		]
		self.letters(frappe.get_doc({"doctype": "Missionary", "title": "_Test Letter Sender"}), rows)
		self.letters(make_person_doc("_Test Letter", "Writer"), rows)

		for report in (missionary_letters_not_yet_read, people_letters_not_yet_read, letters_to_be_shared):
			contents = self.contents(report)
			self.assertIn("_Open note", contents, report.__name__)
			self.assertNotIn("_Private note", contents, report.__name__)

	def test_the_letters_report_lists_the_newest_first_and_filters_by_date(self):
		rows = [
			{"date": add_days(today(), -401), "content": "_Old note"},
			{"date": add_days(today(), -400), "content": "_New note"},
		]
		self.letters(frappe.get_doc({"doctype": "Missionary", "title": "_Test Letter Order"}), rows)

		window = {"from_date": add_days(today(), -405), "to_date": add_days(today(), -395)}
		contents = [row["content"] for row in missionary_letters.get_data(window)]
		self.assertEqual(contents, ["_New note", "_Old note"])

		recent = {"from_date": add_days(today(), -400), "to_date": add_days(today(), -395)}
		self.assertEqual([row["content"] for row in missionary_letters.get_data(recent)], ["_New note"])

	def test_a_new_letter_starts_dated_today(self):
		self.assertEqual(frappe.get_meta("Letter").get_field("date").default, "Today")

	def test_a_private_letter_hides_the_sharing_fields(self):
		meta = frappe.get_meta("Letter")
		for fieldname in ("share_with_church", "shared_date"):
			self.assertEqual(meta.get_field(fieldname).depends_on, "eval:!doc.is_private")


def make_person_doc(first_name, last_name):
	return frappe.get_doc({"doctype": "Person", "first_name": first_name, "last_name": last_name})
