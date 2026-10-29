# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from contextlib import contextmanager

import frappe
from frappe.tests.classes.context_managers import patch_hooks

from churchit.church_people import duplicates
from churchit.church_people.matching import NOT_A_DUPLICATE, OPEN, get_pairs
from churchit.church_people.test_matching import make_matchable
from churchit.tests.helpers import RollbackEachTest


@contextmanager
def dropping_pairs_on_delete():
	"""The Person on_trash hook as hooks.py registers it, whatever else that file holds."""
	doc_events = {
		**frappe.get_hooks("doc_events"),
		"Person": {"on_trash": ["churchit.church_people.duplicates.drop_pairs"]},
	}
	frappe.local.doc_events_hooks = None
	try:
		with patch_hooks({"doc_events": doc_events}):
			yield
	finally:
		frappe.local.doc_events_hooks = None


class TestDuplicateScan(RollbackEachTest):
	def test_the_scan_pairs_people_who_match_once(self):
		ruth = make_matchable("Ruth", birth_date="1960-01-02")
		other_ruth = make_matchable("Ruth", birth_date="1960-01-02")

		duplicates.scan()

		(pair,) = get_pairs(ruth, other_ruth)
		duplicate = frappe.get_doc("Possible Duplicate", pair.name)
		self.assertEqual(duplicate.status, OPEN)
		self.assertIn("same birth date", duplicate.reasons)

	def test_people_in_one_family_are_not_paired(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Scan Family"}).insert()
		naomi = make_matchable("Naomi", birth_date="1961-02-03", family=family.name)
		twin = make_matchable("Naomi", birth_date="1961-02-03", family=family.name)
		elsewhere = make_matchable("Naomi", birth_date="1961-02-03")

		duplicates.scan()

		self.assertEqual(get_pairs(naomi, twin), [])
		self.assertEqual(len(get_pairs(naomi, elsewhere)), 1)

	def test_a_pair_marked_not_a_duplicate_is_not_opened_again(self):
		boaz = make_matchable("Boaz", birth_date="1962-03-04")
		other_boaz = make_matchable("Boaz", birth_date="1962-03-04")
		duplicates.scan()
		(pair,) = get_pairs(boaz, other_boaz)
		frappe.db.set_value("Possible Duplicate", pair.name, "status", NOT_A_DUPLICATE)

		duplicates.scan()

		self.assertEqual([row.name for row in get_pairs(boaz, other_boaz)], [pair.name])
		self.assertEqual(frappe.db.get_value("Possible Duplicate", pair.name, "status"), NOT_A_DUPLICATE)

	def test_deleting_a_person_drops_their_pairs(self):
		jesse = make_matchable("Jesse", birth_date="1963-04-05")
		other_jesse = make_matchable("Jesse", birth_date="1963-04-05")
		duplicates.scan()

		(pair,) = get_pairs(jesse)

		with dropping_pairs_on_delete():
			frappe.delete_doc("Person", other_jesse)

		self.assertEqual(get_pairs(jesse), [])
		# A pair in Deleted Documents would keep both names after the people are deleted or anonymized.
		self.assertFalse(
			frappe.db.exists(
				"Deleted Document", {"deleted_doctype": "Possible Duplicate", "deleted_name": pair.name}
			)
		)
