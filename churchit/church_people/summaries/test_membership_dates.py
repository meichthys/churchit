# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import getdate, today

from churchit.church_people import smart_lists
from churchit.church_people.membership import MEMBER, VISITOR
from churchit.church_people.summaries import refresh
from churchit.church_people.summaries.test_serving import queued_people
from churchit.tests.helpers import RollbackEachTest, force_single_church, make_person, make_smart_list


def date_milestones(person, field, when):
	"""Move *person*'s Milestones of *field* to *when*, as if the change was kept then."""
	for name in frappe.get_all(
		"Milestone", filters={"reference_name": person, "track_field": field}, pluck="name"
	):
		frappe.db.set_value("Milestone", name, "creation", when, update_modified=False)


class TestMembershipDatesSummary(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def dates(self, person):
		refresh([person])
		return frappe.db.get_value(
			"Person", person, ["membership_changed_on", "status_changed_on"], as_dict=True
		)

	def test_each_date_is_the_latest_change_of_its_field(self):
		person = make_person("_Test Dates", "Member", membership=VISITOR, membership_status="Active")
		date_milestones(person.name, "membership", "2024-03-01 10:00:00")
		date_milestones(person.name, "membership_status", "2024-03-01 10:00:00")
		person.membership = MEMBER
		person.save(ignore_permissions=True)

		dates = self.dates(person.name)

		self.assertEqual(dates.membership_changed_on, getdate(today()))
		self.assertEqual(dates.status_changed_on, getdate("2024-03-01"))

	def test_a_person_with_no_milestone_has_no_dates(self):
		person = make_person("_Test Dates", "Unknown").name
		frappe.db.delete("Milestone", {"reference_name": person})

		self.assertEqual(self.dates(person), {"membership_changed_on": None, "status_changed_on": None})

	def test_a_new_milestone_queues_its_person(self):
		person = make_person("_Test Dates", "Queued", membership=VISITOR)
		person.membership = MEMBER

		self.assertIn([person.name], queued_people(lambda: person.save(ignore_permissions=True)))

	def test_a_list_finds_the_people_who_became_members_in_a_year(self):
		joined = make_person("_Test Dates Joined", "_Test Dates List", membership=MEMBER).name
		date_milestones(joined, "membership", "2025-06-15 09:00:00")
		earlier = make_person("_Test Dates Earlier", "_Test Dates List", membership=MEMBER).name
		date_milestones(earlier, "membership", "2024-12-31 23:00:00")
		visitor = make_person("_Test Dates Visitor", "_Test Dates List", membership=VISITOR).name
		date_milestones(visitor, "membership", "2025-06-15 09:00:00")
		refresh([joined, earlier, visitor])
		smart_list = make_smart_list(
			"_Test Dates Joined 2025",
			[
				["Person", "last_name", "=", "_Test Dates List"],
				["Person", "membership", "=", MEMBER],
				["Person", "membership_changed_on", "between", ["2025-01-01", "2025-12-31"]],
			],
		)

		self.assertEqual(smart_lists.get_people(smart_list.name, None), [joined])
