# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.privacy import anonymize_person
from churchit.church_people.test_merge import email, make_family
from churchit.tests.helpers import RollbackEachTest, ensure, make_person
from churchit.tests.test_desk_ui_hygiene import PERSON_HISTORY_EXCEPTIONS

# Frappe skips Version rows while it runs tests, unless a save asks for them.
SAVE_WITH_HISTORY = {"ignore_permissions": True, "ignore_version": False}


class TestHistoryAfterRemovingPersonalData(RollbackEachTest):
	"""Proves by behavior the gaps of PERSON_HISTORY_EXCEPTIONS that no privacy.py tuple shows.

	A doctype in the exceptions must still leak, and one that is not must not. Closing a leak makes
	its test fail until the doctype's line is deleted; the test then stays as the regression check.
	"""

	def assert_history_matches_exception(self, doctype, name, text):
		rows = frappe.get_all("Version", filters={"ref_doctype": doctype, "docname": name}, pluck="data")
		self.assertEqual(
			any(text in data for data in rows),
			doctype in PERSON_HISTORY_EXCEPTIONS,
			f"The {doctype} history and its PERSON_HISTORY_EXCEPTIONS line disagree. "
			"A leak needs the line, and a closed leak loses it.",
		)

	def test_a_family_that_keeps_members_forgets_the_persons_first_name(self):
		person = make_person("_Test History", "Member")
		family = make_family("Member - _Test History", person, make_person("_Test Wife", "Member"))
		family.family_name = "Member Household - _Test History"
		family.save(**SAVE_WITH_HISTORY)

		anonymize_person(person.name)

		self.assert_history_matches_exception("Family", family.name, "_Test History")

	def test_a_collection_forgets_the_email_of_a_donor_added_after_the_first_save(self):
		address = "_test.history@example.com"
		donor = make_person("_Test History", "Donor", emails=[email(address)])
		gift = {
			"fund": ensure("Fund", {"fund": "_Test History Fund"}),
			"payment_type": ensure("Payment Type", {"type": "Cash"}),
			"amount": 5,
		}
		collection = frappe.get_doc(
			{"doctype": "Collection", "date": "2031-01-05 10:00:00", "expected_total": 5, "donations": [gift]}
		).insert(ignore_permissions=True)
		collection.append("donations", {**gift, "person": donor.name, "person_email": address})
		collection.expected_total = 10
		collection.save(**SAVE_WITH_HISTORY)

		anonymize_person(donor.name)

		self.assert_history_matches_exception("Collection", collection.name, address)
