# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, today

from churchit.church_people.membership import MEMBER
from churchit.church_people.report.member_demographics import member_demographics
from churchit.tests.helpers import ensure, make_person, make_two_churches


class TestMemberDemographics(FrappeTestCase):
	def test_a_picked_church_counts_only_its_own_members(self):
		_root, branch_a, branch_b = make_two_churches()
		self.addCleanup(frappe.clear_cache)
		ensure("Membership Type", {"type": MEMBER})
		for church in (branch_a, branch_b):
			make_person(
				"_Test Demographics",
				church,
				church=church,
				membership=MEMBER,
				life_events=[{"event_type": "Birth", "date": "1990-06-01"}],
			)

		_columns, rows = member_demographics.execute({"church": branch_a})

		self.assertEqual(sum(row["total"] for row in rows), 1)

	def test_a_member_with_no_birth_year_counts_as_unknown_age(self):
		ensure("Membership Type", {"type": MEMBER})
		ensure("Life Event Type", {"type": "Birth"})

		def totals():
			return {row["bucket"]: row["total"] for row in member_demographics.execute({})[1]}

		before = totals()
		make_person(
			"_Test Demographics",
			"Yearless",
			membership=MEMBER,
			life_events=[{"event_type": "Birth", "date": "1990-06-01", "year_unknown": 1}],
		)
		make_person(
			"_Test Demographics",
			"Thirties",
			membership=MEMBER,
			life_events=[{"event_type": "Birth", "date": add_years(today(), -35)}],
		)

		after = totals()
		self.assertEqual(after["Unknown Age"], before.get("Unknown Age", 0) + 1)
		self.assertEqual(after["30-44 (Adults)"], before["30-44 (Adults)"] + 1)
		self.assertEqual(after["0-12 (Children)"], before["0-12 (Children)"])
