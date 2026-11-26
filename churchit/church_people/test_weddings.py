# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, today

from churchit.patches.v1_0 import move_anniversaries_to_wedding_events
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
	set_private_people,
)

WEDDING = "Wedding"
LAST_NAME = "_Test Weddings"


def get_weddings(person) -> list[tuple]:
	"""*person*'s Wedding rows as (date, year_unknown, spouse), in table order."""
	return [
		(str(row.date) if row.date else None, row.year_unknown, row.spouse)
		for row in frappe.get_doc("Person", person.name).life_events
		if row.event_type == WEDDING
	]


def get_anniversary(person) -> tuple:
	return tuple(
		frappe.db.get_value(
			"Person", person.name, ["anniversary", "anniversary_year_unknown"], as_dict=True
		).values()
	)


class TestWeddings(RollbackEachTest):
	"""The anniversary comes from the Wedding life event, and a couple shares one wedding."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for event_type in (WEDDING, "Birth", "Death"):
			ensure("Life Event Type", {"type": event_type})

	def test_a_typed_anniversary_becomes_a_wedding_row(self):
		person = make_person("Typed", LAST_NAME, marital_status="Married", anniversary="2001-06-05")

		self.assertEqual(get_weddings(person), [("2001-06-05", 0, None)])
		self.assertEqual(str(person.anniversary), "2001-06-05")

	def test_a_new_person_keeps_the_date_of_their_wedding_row(self):
		person = make_person(
			"New",
			LAST_NAME,
			marital_status="Married",
			life_events=[{"event_type": WEDDING, "date": "2000-06-05", "year_unknown": 1}],
		)

		self.assertEqual(get_weddings(person), [("2000-06-05", 1, None)])
		self.assertEqual(get_anniversary(person), (frappe.utils.getdate("2000-06-05"), 1))

	def test_the_wedding_row_sets_the_read_only_anniversary(self):
		person = make_person("Row", LAST_NAME, marital_status="Married")
		person.append("life_events", {"event_type": WEDDING, "date": "1999-04-10", "year_unknown": 1})
		person.save()

		self.assertEqual(get_anniversary(person), (frappe.utils.getdate("1999-04-10"), 1))
		self.assertEqual(person.marriage_years, 0)

	def test_a_changed_row_wins_over_the_stored_anniversary(self):
		person = make_person("Changed", LAST_NAME, marital_status="Married", anniversary="2001-06-05")
		person.life_events[0].date = "2002-07-06"
		person.save()

		self.assertEqual(str(person.anniversary), "2002-07-06")
		self.assertEqual(get_weddings(person), [("2002-07-06", 0, None)])

	def test_linking_a_spouse_shares_the_wedding_and_names_each_spouse(self):
		wife = make_person("Wife", LAST_NAME)
		husband = make_person(
			"Husband", LAST_NAME, marital_status="Married", spouse=wife.name, anniversary="2001-06-05"
		)

		self.assertEqual(get_weddings(husband), [("2001-06-05", 0, wife.name)])
		self.assertEqual(get_weddings(wife), [("2001-06-05", 0, husband.name)])
		self.assertEqual(str(get_anniversary(wife)[0]), "2001-06-05")

	def test_a_spouse_without_a_date_takes_the_other_spouses_wedding(self):
		wife = make_person("Dated", LAST_NAME, marital_status="Married", anniversary="1990-09-09")
		husband = make_person("Undated", LAST_NAME, marital_status="Married", spouse=wife.name)

		self.assertEqual(get_weddings(husband), [("1990-09-09", 0, wife.name)])
		self.assertEqual(get_weddings(wife), [("1990-09-09", 0, husband.name)])

	def test_a_divorce_keeps_the_wedding_and_clears_the_anniversary(self):
		wife = make_person("Leaving", LAST_NAME)
		husband = make_person(
			"Staying", LAST_NAME, marital_status="Married", spouse=wife.name, anniversary="2001-06-05"
		)
		husband.marital_status = "Divorced"
		husband.save()

		self.assertEqual(get_weddings(husband), [("2001-06-05", 0, wife.name)])
		self.assertEqual(get_anniversary(husband), (None, 0))
		self.assertEqual(get_anniversary(wife), (None, 0))

	def test_a_new_marriage_leaves_the_earlier_wedding_alone(self):
		first = make_person("First", LAST_NAME)
		second = make_person("Second", LAST_NAME)
		person = make_person(
			"Twice", LAST_NAME, marital_status="Married", spouse=first.name, anniversary="1990-01-01"
		)
		person.marital_status = "Widowed"
		person.save()
		person.update({"marital_status": "Married", "spouse": second.name, "anniversary": "2010-02-02"})
		person.save()

		self.assertEqual(
			get_weddings(person), [("1990-01-01", 0, first.name), ("2010-02-02", 0, second.name)]
		)
		self.assertEqual(str(get_anniversary(person)[0]), "2010-02-02")
		self.assertEqual(get_weddings(first), [("1990-01-01", 0, person.name)])

	def test_a_portal_anniversary_has_a_known_year(self):
		person = make_person(
			"Portal",
			LAST_NAME,
			marital_status="Married",
			anniversary="1999-04-10",
			anniversary_year_unknown=1,
		)
		frappe.flags.in_web_form = True
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)

		person.anniversary = "1998-04-10"
		person.save()

		self.assertEqual(get_weddings(person), [("1998-04-10", 0, None)])

	def test_an_empty_web_form_value_leaves_an_earlier_wedding_alone(self):
		person = make_person("Former", LAST_NAME, marital_status="Married", anniversary="1990-03-03")
		person.marital_status = "Divorced"
		person.save()

		person.anniversary = ""
		person.save()

		self.assertEqual(get_weddings(person), [("1990-03-03", 0, None)])

	def test_married_to_a_spouse_who_has_died_is_refused(self):
		late = make_person("Late", LAST_NAME, life_events=[{"event_type": "Death", "date": "2020-01-01"}])
		person = make_person("Remarrying", LAST_NAME, marital_status="Widowed", spouse=late.name)
		person.marital_status = "Married"

		self.assertRaisesRegex(frappe.ValidationError, "choose the new spouse", person.save)

	def test_a_wedding_cannot_be_in_the_future_or_before_the_birth(self):
		person = make_person("Dates", LAST_NAME, marital_status="Married")
		person.append("life_events", {"event_type": "Birth", "date": "1980-01-01"})
		person.save()

		for date, message in ((add_days(today(), 1), "in the future"), ("1979-01-01", "before the birth")):
			with self.subTest(date=date):
				person.reload()
				person.append("life_events", {"event_type": WEDDING, "date": date})
				self.assertRaisesRegex(frappe.ValidationError, message, person.save)

	def test_deleting_a_spouse_keeps_the_wedding_without_a_name(self):
		wife = make_person("Deleted", LAST_NAME)
		husband = make_person(
			"Kept", LAST_NAME, marital_status="Married", spouse=wife.name, anniversary="2001-06-05"
		)
		frappe.delete_doc("Person", wife.name, ignore_permissions=True)

		self.assertEqual(get_weddings(husband), [("2001-06-05", 0, None)])

	def test_a_newly_married_couple_gets_wedding_rows_without_a_date(self):
		wife = make_person("Bride", LAST_NAME)
		husband = make_person("Groom", LAST_NAME, marital_status="Married", spouse=wife.name)

		self.assertEqual(get_weddings(husband), [(None, 0, wife.name)])
		self.assertEqual(get_weddings(wife), [(None, 0, husband.name)])
		self.assertEqual(get_anniversary(wife), (None, 0))

	def test_becoming_married_adds_a_wedding_row_once(self):
		person = make_person("Once", LAST_NAME, marital_status="Single")
		person.marital_status = "Married"
		person.save()
		self.assertEqual(get_weddings(person), [(None, 0, None)])

		person.set("life_events", [])
		person.save()

		self.assertEqual(get_weddings(person), [])

	def test_recording_married_keeps_the_wedding_of_a_person_of_unknown_status(self):
		person = make_person("Unknown", LAST_NAME, anniversary="1995-08-08")
		person.marital_status = "Married"
		person.save()

		self.assertEqual(get_weddings(person), [("1995-08-08", 0, None)])
		self.assertEqual(str(get_anniversary(person)[0]), "1995-08-08")

	def test_clearing_a_wrong_spouse_adds_no_wedding_row(self):
		wrong = make_person("Wrong", LAST_NAME)
		person = make_person("Fixed", LAST_NAME, marital_status="Married", spouse=wrong.name)
		person.spouse = None
		person.save()

		self.assertEqual(get_weddings(person), [(None, 0, wrong.name)])

	def test_a_widow_who_remarries_starts_a_new_wedding_row(self):
		person = make_person("Widow", LAST_NAME, marital_status="Married", anniversary="1980-05-05")
		person.marital_status = "Widowed"
		person.save()
		groom = make_person("Groom", LAST_NAME)
		person.update({"marital_status": "Married", "spouse": groom.name})
		person.save()

		self.assertEqual(get_weddings(person), [("1980-05-05", 0, None), (None, 0, groom.name)])
		self.assertEqual(get_anniversary(person), (None, 0))
		self.assertEqual(get_weddings(groom), [(None, 0, person.name)])

	def test_linking_the_spouse_of_a_married_person_names_their_wedding(self):
		person = make_person("Named", LAST_NAME, marital_status="Married", anniversary="2000-01-02")
		spouse = make_person("Later", LAST_NAME)
		person.spouse = spouse.name
		person.save()

		self.assertEqual(get_weddings(person), [("2000-01-02", 0, spouse.name)])
		self.assertEqual(get_weddings(spouse), [("2000-01-02", 0, person.name)])

	def test_a_spouse_keeps_details_the_other_row_lacks(self):
		wife = make_person("Details", LAST_NAME)
		husband = make_person(
			"Keeper", LAST_NAME, marital_status="Married", spouse=wife.name, anniversary="2001-06-05"
		)
		wife_row = frappe.get_doc("Person", wife.name).life_events[0]
		frappe.db.set_value("Life Event", wife_row.name, "location", "Old Chapel")

		husband.reload()
		husband.anniversary = "2001-06-06"
		husband.save()

		for person in (husband, wife):
			row = frappe.get_doc("Person", person.name).life_events[0]
			self.assertEqual((str(row.date), row.location), ("2001-06-06", "Old Chapel"))

	def test_clearing_a_detail_clears_it_for_both_spouses(self):
		wife = make_person("Cleared", LAST_NAME)
		husband = make_person("Clearer", LAST_NAME, marital_status="Married", spouse=wife.name)
		husband.life_events[0].location = "Old Chapel"
		husband.save()
		self.assertEqual(frappe.get_doc("Person", wife.name).life_events[0].location, "Old Chapel")

		husband.life_events[0].location = None
		husband.save()

		self.assertIsNone(frappe.get_doc("Person", wife.name).life_events[0].location)

	def test_patch_keeps_the_stored_anniversary_and_can_run_twice(self):
		person = make_person("History", LAST_NAME)
		person.set(
			"life_events",
			[
				{"event_type": WEDDING, "date": "1995-01-01"},
				{"event_type": WEDDING, "date": "1970-01-01"},
			],
		)
		person.save()
		person.db_set({"marital_status": "Married", "anniversary": "1995-01-01"})

		for _run in range(2):
			move_anniversaries_to_wedding_events.execute()

		self.assertEqual(get_weddings(person), [("1970-01-01", 0, None), ("1995-01-01", 0, None)])
		self.assertEqual(str(get_anniversary(person)[0]), "1995-01-01")

	def test_patch_moves_follow_up_triggers_on_anniversary_events(self):
		ensure("Life Event Type", {"type": "Anniversary"})
		trigger = frappe.get_doc(
			{
				"doctype": "Follow-up Trigger",
				"parent": "_Test Weddings Workflow",
				"parenttype": "Follow-up Workflow",
				"parentfield": "triggers",
				"trigger": "Life Event Added",
				"value_type": "Life Event Type",
				"value": "Anniversary",
			}
		)
		trigger.db_insert()

		move_anniversaries_to_wedding_events.execute()

		self.assertEqual(frappe.db.get_value("Follow-up Trigger", trigger.name, "value"), WEDDING)
		self.assertFalse(frappe.db.exists("Life Event Type", "Anniversary"))

	def test_patch_moves_anniversaries_and_anniversary_events_to_wedding_rows(self):
		ensure("Life Event Type", {"type": "Anniversary"})
		partner = make_person("Partner", LAST_NAME)
		typed = make_person("Patched", LAST_NAME)
		typed.db_set(
			{"marital_status": "Married", "anniversary": "2003-03-03", "anniversary_year_unknown": 1}
		)
		evented = make_person("Evented", LAST_NAME)
		evented.append("life_events", {"event_type": "Anniversary", "date": add_years(today(), -5)})
		evented.save()
		evented.db_set("marital_status", "Married")
		undated = make_person("Undated", LAST_NAME)
		undated.db_set({"marital_status": "Married", "spouse": partner.name})

		move_anniversaries_to_wedding_events.execute()

		self.assertEqual(get_weddings(typed), [("2003-03-03", 1, None)])
		self.assertEqual(get_weddings(evented), [(add_years(today(), -5), 0, None)])
		self.assertEqual(str(get_anniversary(evented)[0]), add_years(today(), -5))
		self.assertEqual(get_weddings(undated), [(None, 0, partner.name)])
		self.assertFalse(frappe.db.exists("Life Event Type", "Anniversary"))


class TestWeddingSpouseChurch(FrappeTestCase):
	"""In a private directory, a Wedding row names only a spouse of a church the user can see."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		ensure("Life Event Type", {"type": WEDDING})
		cls.manager_a = ensure_user("_test_weddings_a@example.com", "WeddingsA", roles=("Church Manager",))
		make_person("_Test Weddings", "Manager", church=cls.branch_a, user=cls.manager_a)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_another_churchs_person_is_refused_in_a_private_directory(self):
		person = make_person("Mine", LAST_NAME, church=self.branch_a)
		other = make_person("Theirs", LAST_NAME, church=self.branch_b)
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		frappe.set_user(self.manager_a)

		doc = frappe.get_doc("Person", person.name)
		doc.append("life_events", {"event_type": WEDDING, "date": "1990-01-01", "spouse": other.name})

		self.assertRaisesRegex(frappe.PermissionError, "another church", doc.save)
