# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import timedelta

import frappe

from churchit.church_people.membership import changed_between, record_changes
from churchit.patches.v1_0 import record_membership_history
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


def keep_milestone(person, field, value, at):
	"""A Milestone of *person*'s *field* taking *value*, dated *at*."""
	frappe.get_doc(
		{
			"doctype": "Milestone",
			"reference_type": "Person",
			"reference_name": person,
			"track_field": field,
			"value": value,
			"creation": at,
			"modified": at,
		}
	).db_insert()


def milestones(person):
	return frappe.get_all(
		"Milestone",
		filters={"reference_type": "Person", "reference_name": person},
		fields=["track_field", "value", "creation"],
		order_by="creation asc",
	)


def forget_milestones(person):
	frappe.db.delete("Milestone", {"reference_type": "Person", "reference_name": person})


class TestMembershipHistory(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for membership_type in ("Member", "Regular Attender", "Visitor"):
			ensure("Membership Type", {"type": membership_type})
		for status in ("Active", "Inactive"):
			ensure("Member Status", {"status": status})

	def kept_by(self, person, **values):
		"""The Milestones that saving *values* on *person* keeps, however saving is wired up."""
		person.update(values)
		person.save(ignore_permissions=True)
		forget_milestones(person.name)
		record_changes(person)
		return [(milestone.track_field, milestone.value) for milestone in milestones(person.name)]

	def test_a_new_person_keeps_their_first_values(self):
		person = make_person("_Test History New", membership="Visitor")
		forget_milestones(person.name)
		record_changes(person)

		self.assertEqual(
			sorted((milestone.track_field, milestone.value) for milestone in milestones(person.name)),
			[("membership", "Visitor"), ("membership_status", "Active")],
		)

	def test_a_change_keeps_only_the_field_that_changed(self):
		person = make_person("_Test History Change", membership="Visitor")

		self.assertEqual(self.kept_by(person, membership="Member"), [("membership", "Member")])
		self.assertEqual(self.kept_by(person, first_name="_Test History Renamed"), [])

	def test_clearing_a_field_keeps_nothing_and_still_saves(self):
		person = make_person("_Test History Cleared", membership="Visitor")

		self.assertEqual(self.kept_by(person, membership=None), [])
		self.assertIsNone(frappe.db.get_value("Person", person.name, "membership"))

	def test_nothing_is_kept_during_migrate(self):
		person = make_person("_Test History Migrate", membership="Visitor")
		forget_milestones(person.name)
		frappe.flags.in_migrate = True
		try:
			record_changes(person)
		finally:
			frappe.flags.in_migrate = False

		self.assertEqual(milestones(person.name), [])

	def test_changed_between_finds_who_took_the_value_in_the_date_range(self):
		keep_milestone("_Test Early", "membership", "Member", "2031-02-28 23:59:00")
		keep_milestone("_Test First Day", "membership", "Member", "2031-03-01 00:00:00")
		keep_milestone("_Test Last Day", "membership", "Member", "2031-03-31 23:00:00")
		keep_milestone("_Test Late", "membership", "Member", "2031-04-01 00:00:00")
		keep_milestone("_Test Other Value", "membership", "Visitor", "2031-03-10 10:00:00")
		keep_milestone("_Test Other Field", "membership_status", "Member", "2031-03-10 10:00:00")

		self.assertEqual(
			changed_between("membership", "Member", "2031-03-01", "2031-03-31"),
			{"_Test First Day", "_Test Last Day"},
		)

	def make_person_with_versions(self):
		"""A Visitor who became a Regular Attender, went Inactive, then became a Member, each kept in a Version."""
		person = make_person("_Test History Versions", membership="Visitor")
		for values in (
			{"membership": "Regular Attender"},
			{"membership_status": "Inactive"},
			{"membership": "Member"},
		):
			person.update(values)
			person.save(ignore_permissions=True, ignore_version=False)
		forget_milestones(person.name)
		return person.name

	def test_the_history_is_rebuilt_from_versions(self):
		person = self.make_person_with_versions()
		added = frappe.db.get_value("Person", person, "creation")
		first_change = frappe.db.get_value(
			"Version", {"ref_doctype": "Person", "docname": person}, "creation", order_by="creation asc"
		)

		record_membership_history.execute()

		kept = milestones(person)
		self.assertEqual(
			sorted(
				(milestone.track_field, milestone.value) for milestone in kept if milestone.creation == added
			),
			[("membership", "Visitor"), ("membership_status", "Active")],
		)
		self.assertEqual(
			[(milestone.track_field, milestone.value) for milestone in kept if milestone.creation != added],
			[("membership", "Regular Attender"), ("membership_status", "Inactive"), ("membership", "Member")],
		)
		self.assertEqual(kept[2].creation, first_change)

	def test_the_rebuild_keeps_no_change_twice(self):
		person = self.make_person_with_versions()
		last_change = frappe.db.get_value(
			"Version", {"ref_doctype": "Person", "docname": person}, "creation", order_by="creation desc"
		)
		keep_milestone(person, "membership", "Member", last_change + timedelta(seconds=2))

		record_membership_history.execute()
		record_membership_history.execute()

		self.assertEqual(len(milestones(person)), 5)
