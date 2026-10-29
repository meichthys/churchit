# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import call, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from churchit.church_people import events
from churchit.tests.helpers import ensure, make_person

received = []


def record(person, **data):
	"""A handler for the tests, at a dotted path the way a hook names one."""
	received.append((person, data))


class TestEmitChanges(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for status in ("Active", "Inactive"):
			ensure("Member Status", {"status": status})
		for membership_type in ("Member", "Visitor"):
			ensure("Membership Type", {"type": membership_type})
		for event_type in ("Birth", "Baptism", "Death"):
			ensure("Life Event Type", {"type": event_type})
		ensure("Inactive Reason", {"reason": "Deceased"})

	def emitted(self, change):
		"""The (event, person, data) of each event that *change* emits."""
		with patch.object(events, "emit") as emit:
			change()
		return [(*emitted.args, emitted.kwargs) for emitted in emit.call_args_list]

	def test_a_new_person_emits_what_they_start_with(self):
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Arrival",
				"membership": "Visitor",
				"life_events": [{"event_type": "Birth", "date": "1990-05-01"}],
			}
		)

		emitted = self.emitted(lambda: person.insert(ignore_permissions=True))

		self.assertEqual(
			emitted,
			[
				(
					events.MEMBERSHIP_CHANGED,
					person.name,
					{"field": "membership", "old": None, "new": "Visitor"},
				),
				(
					events.MEMBERSHIP_CHANGED,
					person.name,
					{"field": "membership_status", "old": None, "new": "Active"},
				),
				(
					events.LIFE_EVENT_ADDED,
					person.name,
					{"event_type": "Birth", "date": getdate("1990-05-01")},
				),
			],
		)

	def test_a_new_person_emits_no_membership_they_do_not_have(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Unconnected"})

		emitted = self.emitted(lambda: person.insert(ignore_permissions=True))

		self.assertEqual([data["field"] for _event, _person, data in emitted], ["membership_status"])

	def test_a_membership_change_emits_the_old_and_new_value(self):
		person = make_person("_Test Joiner", membership="Visitor")
		person.membership = "Member"

		emitted = self.emitted(person.save)

		self.assertEqual(
			emitted,
			[
				(
					events.MEMBERSHIP_CHANGED,
					person.name,
					{"field": "membership", "old": "Visitor", "new": "Member"},
				)
			],
		)

	def test_a_death_emits_the_life_event_and_the_death(self):
		person = make_person("_Test Passing", membership="Member")
		person.append("life_events", {"event_type": "Death", "date": "2026-10-01"})

		emitted = self.emitted(person.save)

		self.assertIn(
			(events.LIFE_EVENT_ADDED, person.name, {"event_type": "Death", "date": getdate("2026-10-01")}),
			emitted,
		)
		self.assertIn((events.PERSON_DECEASED, person.name, {"date": getdate("2026-10-01")}), emitted)
		self.assertIn(
			(
				events.MEMBERSHIP_CHANGED,
				person.name,
				{"field": "membership_status", "old": "Active", "new": "Inactive"},
			),
			emitted,
		)

	def test_a_death_with_no_date_emits_a_death_with_no_date(self):
		person = make_person("_Test Unrecorded")
		person.append("life_events", {"event_type": "Death"})

		emitted = self.emitted(person.save)

		self.assertIn((events.PERSON_DECEASED, person.name, {"date": None}), emitted)

	def test_only_the_added_life_event_is_emitted(self):
		person = make_person("_Test Growing", life_events=[{"event_type": "Birth", "date": "2000-01-01"}])
		person.append("life_events", {"event_type": "Baptism", "date": "2010-06-06"})

		emitted = self.emitted(person.save)

		self.assertEqual(
			emitted,
			[
				(
					events.LIFE_EVENT_ADDED,
					person.name,
					{"event_type": "Baptism", "date": getdate("2010-06-06")},
				)
			],
		)

	def test_a_save_that_changes_nothing_relevant_emits_nothing(self):
		person = make_person(
			"_Test Steady",
			membership="Member",
			life_events=[
				{"event_type": "Birth", "date": "2000-01-01"},
				{"event_type": "Death", "date": "2020-01-01"},
			],
		)
		person.alergies = "Peanuts"
		person.life_events[0].location = "Springfield"
		person.life_events[0].date = "2000-01-02"

		self.assertEqual(self.emitted(person.save), [])


class TestEmit(FrappeTestCase):
	def emit(self, hooks, *args, **data):
		"""The calls `frappe.enqueue` gets when *hooks* are registered and an event is emitted."""
		with patch("frappe.get_hooks", return_value=hooks) as get_hooks, patch("frappe.enqueue") as enqueue:
			events.emit(*args, **data)
		if enqueue.called:
			get_hooks.assert_called_with(events.HOOK, {})
		return enqueue.call_args_list

	def test_each_handler_of_the_event_runs_after_the_commit(self):
		hooks = {"membership_changed": ["one.handler", "two.handler"], "person_deceased": ["three.handler"]}

		queued = self.emit(
			hooks, "membership_changed", "PRSN-0001", field="membership", old=None, new="Member"
		)

		data = {"field": "membership", "old": None, "new": "Member"}
		self.assertEqual(
			queued,
			[
				call(
					events.run_handler,
					enqueue_after_commit=True,
					handler=handler,
					person="PRSN-0001",
					data=data,
				)
				for handler in ("one.handler", "two.handler")
			],
		)

	def test_an_event_nobody_handles_queues_nothing(self):
		self.assertEqual(self.emit({}, "person_deceased", "PRSN-0001", date=None), [])

	def test_install_patches_and_migrate_emit_nothing(self):
		hooks = {"person_deceased": ["one.handler"]}
		for flag in ("in_install", "in_patch", "in_migrate"):
			with self.subTest(flag=flag), patch.dict(frappe.local.flags, {flag: True}):
				self.assertEqual(self.emit(hooks, "person_deceased", "PRSN-0001", date=None), [])

	def test_the_job_calls_the_handler_with_the_person_and_data(self):
		received.clear()

		events.run_handler(f"{__name__}.record", "PRSN-0001", {"event": "kept apart", "date": None})

		self.assertEqual(received, [("PRSN-0001", {"event": "kept apart", "date": None})])
