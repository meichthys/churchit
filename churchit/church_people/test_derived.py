# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.email.doctype.notification.notification import evaluate_alert
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, getdate, nowdate

from churchit.church_people.derived import (
	ADULT,
	CHILD,
	get_derived_values,
	get_grade,
	get_grade_number,
	get_next_anniversary,
	get_next_occurrence,
	life_stage_for,
	refresh_daily,
)
from churchit.church_people.membership import living_people_filter
from churchit.patches.v1_0 import (
	derive_birth_death_and_life_stage,
	send_birthday_and_anniversary_greetings,
	sign_greeting_templates_and_greet_active_people,
	store_new_people_settings_defaults,
)
from churchit.tests.helpers import RollbackEachTest, ensure, make_person, make_primary_contact


def row(event_type, date=None, year_unknown=0):
	return frappe._dict(event_type=event_type, date=date, year_unknown=year_unknown)


def on_today(year):
	"""Today's month and day in *year*. Pass a leap year, so that February 29 exists in it."""
	return getdate().replace(year=year)


def email(address):
	return [{"email_address": address, "is_primary": 1}]


def set_adult_age(age):
	settings = frappe.get_single("People Settings")
	settings.adult_age = age
	settings.save(ignore_permissions=True)


def set_school_year_start_month(month):
	frappe.db.set_single_value("People Settings", "school_year_start_month", month)


class TestDerivedValues(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def test_the_first_dated_birth_gives_the_birth_fields_and_age(self):
		born = getdate(add_years(nowdate(), -30))
		values = get_derived_values([row("Birth"), row("Birth", born), row("Birth", "1900-01-01")], None)

		self.assertEqual(values["birth_date"], born)
		self.assertEqual((values["birth_month"], values["birth_day"]), (born.month, born.day))
		self.assertEqual(values["age"], 30)
		self.assertEqual(values["life_stage"], ADULT)

	def test_a_birth_year_nobody_knows_gives_the_birthday_but_no_age(self):
		values = get_derived_values([row("Birth", "1900-07-04", year_unknown=1)], None)

		self.assertEqual((values["birth_month"], values["birth_day"]), (7, 4))
		self.assertIsNone(values["birth_date"])
		self.assertEqual(values["age"], 0)
		self.assertIsNone(values["life_stage"])

	def test_no_birth_clears_the_birth_fields(self):
		values = get_derived_values([row("Baptism", "2000-01-01")], None)

		self.assertEqual(
			(values["birth_date"], values["birth_month"], values["birth_day"], values["age"]),
			(None, 0, 0, 0),
		)
		self.assertEqual((values["is_deceased"], values["deceased_date"]), (0, None))

	def test_a_death_stops_the_age_at_the_death(self):
		values = get_derived_values([row("Birth", "1950-03-01"), row("Death", "2000-02-28")], None)

		self.assertEqual((values["is_deceased"], values["deceased_date"]), (1, "2000-02-28"))
		self.assertEqual(values["age"], 49)

	def test_a_death_with_no_date_leaves_the_age_unknown(self):
		values = get_derived_values([row("Birth", "1950-03-01"), row("Death")], None)

		self.assertEqual((values["is_deceased"], values["deceased_date"]), (1, None))
		self.assertEqual(values["age"], 0)
		self.assertIsNone(values["life_stage"])


class TestNextBirthdayAndAnniversary(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Life Event Type", {"type": "Birth"})
		ensure("Marital Status", {"status": "Married"})

	def test_the_day_itself_stays_next_until_it_ends(self):
		self.assertEqual(get_next_occurrence(9, 30, "2026-09-30"), date(2026, 9, 30))
		self.assertEqual(get_next_occurrence(9, 30, "2026-10-01"), date(2027, 9, 30))

	def test_february_29_falls_on_february_28_in_a_common_year(self):
		self.assertEqual(get_next_occurrence(2, 29, "2027-01-10"), date(2027, 2, 28))
		self.assertEqual(get_next_occurrence(2, 29, "2027-03-01"), date(2028, 2, 29))

	def test_the_birth_row_gives_the_next_birthday_even_when_its_year_is_unknown(self):
		for year_unknown in (0, 1):
			values = get_derived_values([row("Birth", on_today(1980), year_unknown)], None)
			self.assertEqual(values["next_birthday"], getdate())

	def test_someone_who_died_has_no_next_birthday_or_anniversary(self):
		values = get_derived_values([row("Birth", on_today(1952)), row("Death", "2020-01-01")], None)

		self.assertIsNone(values["next_birthday"])
		self.assertIsNone(get_next_anniversary(on_today(1972), is_deceased=1))

	def test_no_birth_or_anniversary_gives_no_next_date(self):
		self.assertIsNone(get_derived_values([row("Baptism", "2000-01-01")], None)["next_birthday"])
		self.assertIsNone(get_next_anniversary(None, is_deceased=0))

	def test_saving_a_person_sets_the_next_birthday_and_anniversary(self):
		person = make_person(
			"_Test Next",
			"Dates",
			marital_status="Married",
			anniversary=on_today(1988),
			life_events=[row("Birth", on_today(1980))],
		)

		self.assertEqual(
			frappe.db.get_value("Person", person.name, ["next_birthday", "next_anniversary"]),
			(getdate(), getdate()),
		)


class TestLifeStage(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def test_the_household_role_comes_before_the_age(self):
		self.assertEqual(life_stage_for(CHILD, 40), CHILD)
		self.assertEqual(life_stage_for(ADULT, 5), ADULT)
		self.assertEqual(life_stage_for("Other Adult", None), ADULT)

	def test_without_a_role_the_age_is_measured_against_the_adult_age(self):
		self.assertEqual(life_stage_for(None, 17), CHILD)
		self.assertEqual(life_stage_for(None, 18), ADULT)

		set_adult_age(21)
		self.addCleanup(set_adult_age, 18)

		self.assertEqual(life_stage_for(None, 18), CHILD)

	def test_neither_role_nor_age_leaves_it_unknown(self):
		self.assertIsNone(life_stage_for(None, None))


class TestGrade(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_school_year_start_month("August")

	def test_the_grade_moves_up_on_the_first_day_of_the_start_month(self):
		self.assertEqual(get_grade(2030, "2026-07-31"), "Grade 8")
		self.assertEqual(get_grade(2030, "2026-08-01"), "Grade 9")

	def test_kindergarten_starts_thirteen_years_before_graduation(self):
		self.assertIsNone(get_grade(2039, "2026-07-31"))
		self.assertEqual(get_grade(2039, "2026-08-01"), "Kindergarten")
		self.assertEqual(get_grade(2038, "2026-08-01"), "Grade 1")

	def test_the_final_year_ends_in_graduation(self):
		self.assertEqual(get_grade(2026, "2026-07-31"), "Grade 12")
		self.assertEqual(get_grade(2026, "2026-08-01"), "Graduated")
		self.assertEqual(get_grade(2000, "2026-08-01"), "Graduated")

	def test_a_school_year_starting_in_january_is_the_calendar_year(self):
		set_school_year_start_month("January")
		self.addCleanup(set_school_year_start_month, "August")

		self.assertEqual(get_grade(2027, "2026-12-31"), "Grade 11")
		self.assertEqual(get_grade(2027, "2027-01-01"), "Grade 12")
		self.assertEqual(get_grade(2027, "2028-01-01"), "Graduated")

	def test_the_patch_gives_a_site_saved_before_the_setting_its_default(self):
		frappe.db.set_single_value("People Settings", "adult_age", 21)
		self.addCleanup(frappe.db.set_single_value, "People Settings", "adult_age", 18)
		frappe.db.delete("Singles", {"doctype": "People Settings", "field": "school_year_start_month"})
		frappe.db.value_cache.pop("People Settings", None)

		store_new_people_settings_defaults.execute()

		self.assertEqual(frappe.db.get_single_value("People Settings", "school_year_start_month"), "August")
		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 21)

	def test_no_graduation_year_gives_no_grade(self):
		self.assertIsNone(get_grade(None))
		self.assertIsNone(get_grade(0))
		self.assertIsNone(get_grade_number(None))

	def test_the_grade_number_counts_from_kindergarten_before_and_after_school(self):
		self.assertEqual(get_grade_number(2039, "2026-08-01"), 0)
		self.assertEqual(get_grade_number(2039, "2026-07-31"), -1)
		self.assertEqual(get_grade_number(2030, "2026-08-01"), 9)
		self.assertEqual(get_grade_number(2026, "2026-08-01"), 13)

	def test_saving_a_person_sets_the_grade(self):
		year = getdate().year + 5
		person = make_person("_Test Pupil", graduation_year=year)

		self.assertEqual(person.grade, get_grade(year))
		self.assertTrue(person.grade.startswith("Grade "))

		person.graduation_year = None
		person.save(ignore_permissions=True)
		self.assertIsNone(frappe.db.get_value("Person", person.name, "grade"))

	def test_the_daily_refresh_moves_the_grade_up(self):
		year = getdate().year + 5
		person = make_person("_Test Pupil Daily", graduation_year=year)
		frappe.db.set_value("Person", person.name, "grade", "Grade 1", update_modified=False)

		refresh_daily()

		self.assertEqual(frappe.db.get_value("Person", person.name, "grade"), get_grade(year))


class TestRefreshDaily(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		for event_type in ("Birth", "Death"):
			ensure("Life Event Type", {"type": event_type})
		ensure("Marital Status", {"status": "Married"})

	def stored(self, person, *fields):
		return frappe.db.get_value("Person", person.name, fields, as_dict=True)

	def test_a_birthday_brings_the_age_and_life_stage_up_to_date(self):
		person = make_person("_Test Coming Of Age", life_events=[row("Birth", add_years(nowdate(), -18))])
		frappe.db.set_value("Person", person.name, {"age": 17, "life_stage": CHILD}, update_modified=False)

		refresh_daily()

		self.assertEqual(self.stored(person, "age", "life_stage"), {"age": 18, "life_stage": ADULT})

	def test_a_birth_year_nobody_knows_keeps_no_age(self):
		person = make_person("_Test Ageless", life_events=[row("Birth", "1990-07-04", year_unknown=1)])
		frappe.db.set_value("Person", person.name, "age", 36, update_modified=False)

		refresh_daily()

		self.assertEqual(
			self.stored(person, "age", "birth_date", "birth_month"),
			{"age": 0, "birth_date": None, "birth_month": 7},
		)

	def test_the_age_of_someone_who_died_stays_at_their_death(self):
		person = make_person(
			"_Test Departed", life_events=[row("Birth", "1950-03-01"), row("Death", "2000-02-28")]
		)
		frappe.db.set_value("Person", person.name, "age", 76, update_modified=False)

		refresh_daily()

		self.assertEqual(self.stored(person, "age").age, 49)

	def test_a_birthday_and_anniversary_that_passed_move_to_next_year(self):
		yesterday = getdate(add_days(nowdate(), -1))
		person = make_person(
			"_Test Last Year",
			marital_status="Married",
			anniversary=yesterday.replace(year=1988),
			life_events=[row("Birth", yesterday.replace(year=1980))],
		)
		frappe.db.set_value(
			"Person",
			person.name,
			{"next_birthday": yesterday, "next_anniversary": yesterday},
			update_modified=False,
		)

		refresh_daily()

		next_year = getdate(add_years(yesterday, 1))
		self.assertEqual(
			self.stored(person, "next_birthday", "next_anniversary"),
			{"next_birthday": next_year, "next_anniversary": next_year},
		)

	def test_the_patch_derives_the_fields_of_people_saved_before_they_existed(self):
		person = make_person(
			"_Test Before", life_events=[row("Birth", "1950-03-01"), row("Death", "2000-02-28")]
		)
		blank = {
			"birth_date": None,
			"birth_month": 0,
			"birth_day": 0,
			"is_deceased": 0,
			"deceased_date": None,
			"age": 0,
			"life_stage": None,
		}
		frappe.db.set_value("Person", person.name, blank, update_modified=False)
		modified = frappe.db.get_value("Person", person.name, "modified")
		frappe.db.delete("Singles", {"doctype": "People Settings"})

		derive_birth_death_and_life_stage.execute()

		self.assertEqual(
			self.stored(person, *blank, "modified"),
			{
				"birth_date": getdate("1950-03-01"),
				"birth_month": 3,
				"birth_day": 1,
				"is_deceased": 1,
				"deceased_date": getdate("2000-02-28"),
				"age": 49,
				"life_stage": ADULT,
				"modified": modified,
			},
		)
		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 18)


class TestLivingPeopleFilter(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Life Event Type", {"type": "Death"})
		cls.living = make_person("_Test Living", "_Test Filter")
		cls.dead = make_person("_Test Dead", "_Test Filter", life_events=[row("Death", "2020-01-01")])

	def test_the_filter_leaves_out_people_who_died_in_a_query(self):
		Person = frappe.qb.DocType("Person")
		names = (
			frappe.qb.from_(Person)
			.select(Person.name)
			.where((Person.last_name == "_Test Filter") & living_people_filter(Person))
			.run(pluck=True)
		)
		self.assertEqual(names, [self.living.name])

	def test_the_filter_leaves_out_people_who_died_in_get_list(self):
		names = frappe.get_list(
			"Person", filters=[{"last_name": "_Test Filter"}, living_people_filter()], pluck="name"
		)
		self.assertEqual(names, [self.living.name])

	def test_the_filter_reads_the_deceased_box(self):
		frappe.db.set_value("Person", self.dead.name, "is_deceased", 0, update_modified=False)
		self.addCleanup(
			frappe.db.set_value, "Person", self.dead.name, "is_deceased", 1, update_modified=False
		)

		names = frappe.get_list(
			"Person", filters=[{"last_name": "_Test Filter"}, living_people_filter()], pluck="name"
		)
		self.assertCountEqual(names, [self.living.name, self.dead.name])


OLD_BIRTHDAY_CONDITION = (
	'doc.event_type == "Birth" and frappe.db.get_value("Email Address", '
	'{"parenttype": "Person", "parent": doc.parent, "is_primary": 1}, "email_address")'
)
OLD_BIRTHDAY_CC = (
	'{{ frappe.db.get_value("Email Address", {"parenttype": "Person", "parent": doc.parent, "is_primary": 1}, '
	'"email_address") or "" }}'
)


class TestGreetings(RollbackEachTest):
	"""Birthday Greeting and Anniversary Greeting send on the day itself, as a church's enabled copy."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for event_type in ("Birth", "Death"):
			ensure("Life Event Type", {"type": event_type})
		for status in ("Married", "Widowed"):
			ensure("Marital Status", {"status": status})

	def shipped(self, name):
		"""The shipped *name* as a church's enabled copy of it."""
		folder = Path(
			frappe.get_app_path("churchit", "church_communications", "notification", frappe.scrub(name))
		)
		notification = json.loads((folder / f"{frappe.scrub(name)}.json").read_text())
		return frappe.get_doc({**notification, "is_standard": 0, "enabled": 1})

	def emailed(self, notification):
		"""The email that *notification* sends today to each address, by address.

		The site may have no outgoing Email Account, so the account check is passed as well.
		"""
		with (
			patch("frappe.sendmail") as sendmail,
			patch("churchit.church_communications.outgoing_email.can_send_email", return_value=True),
		):
			for doc in notification.get_documents_for_today():
				evaluate_alert(doc, notification, notification.event)
		return {
			address: frappe._dict(call.kwargs)
			for call in sendmail.call_args_list
			for address in call.kwargs["recipients"] + call.kwargs["cc"]
		}

	def make_copy(self, name, **values):
		"""A church's Notification *name* made before the greetings moved to the next dates."""
		return frappe.get_doc(
			{
				"doctype": "Notification",
				"name": name,
				"channel": "Email",
				"subject": "_Test greeting",
				"message": "<p>_Test greeting</p>",
				"event": "Days After",
				"days_in_advance": 0,
				"condition_type": "Python",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_the_birthday_greeting_reaches_a_person_on_their_birthday_only(self):
		greeted = make_person(
			"_Test Greeted",
			"Birthday",
			life_events=[row("Birth", on_today(1980))],
			emails=email("_test_greeted@example.com"),
		)
		tomorrow = getdate(add_days(nowdate(), 1)).replace(year=1980)
		make_person(
			"_Test Tomorrow",
			"Birthday",
			life_events=[row("Birth", tomorrow)],
			emails=email("_test_later@example.com"),
		)
		no_email = make_person("_Test Unreachable", "Birthday", life_events=[row("Birth", on_today(1980))])
		greeting = self.shipped("Birthday Greeting")

		sent = self.emailed(greeting)

		self.assertNotIn(no_email.name, [doc.name for doc in greeting.get_documents_for_today()])
		self.assertNotIn("_test_later@example.com", sent)
		self.assertEqual(sent["_test_greeted@example.com"].subject, "Happy Birthday, _Test Greeted!")
		self.assertIn("Dear _Test Greeted,", sent["_test_greeted@example.com"].message)
		self.assertEqual(sent["_test_greeted@example.com"].reference_name, greeted.name)

	def test_the_birthday_greeting_leaves_out_someone_who_died(self):
		make_person(
			"_Test Late",
			"Birthday",
			life_events=[row("Birth", on_today(1940)), row("Death", "2020-01-01")],
			emails=email("_test_late@example.com"),
		)

		self.assertNotIn("_test_late@example.com", self.emailed(self.shipped("Birthday Greeting")))

	def test_the_anniversary_greeting_reaches_a_married_couple_once_and_no_widow(self):
		couple = frappe.get_doc({"doctype": "Family", "family_name": "_Test Greeted Couple"}).insert(
			ignore_permissions=True
		)
		wife = make_person(
			"_Test Wife",
			"Couple",
			family=couple.name,
			marital_status="Married",
			anniversary=on_today(1988),
			emails=email("_test_wife@example.com"),
		)
		husband = make_person(
			"_Test Husband",
			"Couple",
			family=couple.name,
			marital_status="Married",
			spouse=wife.name,
			emails=email("_test_husband@example.com"),
		)
		make_primary_contact(husband)
		alone = frappe.get_doc({"doctype": "Family", "family_name": "_Test Greeted Widow"}).insert(
			ignore_permissions=True
		)
		widow = make_person(
			"_Test Widow",
			"Alone",
			family=alone.name,
			marital_status="Widowed",
			anniversary=on_today(1960),
			emails=email("_test_widow@example.com"),
		)
		make_primary_contact(widow)
		addresses = {"_test_wife@example.com", "_test_husband@example.com", "_test_widow@example.com"}

		sent = self.emailed(self.shipped("Anniversary Greeting"))

		self.assertEqual(addresses & set(sent), {"_test_husband@example.com"})
		self.assertIn("Dear _Test Husband and _Test Wife,", sent["_test_husband@example.com"].message)

	def test_linking_and_unlinking_a_spouse_keeps_their_next_anniversary(self):
		wife = make_person("_Test Linked", "Wife", marital_status="Married")
		husband = make_person(
			"_Test Linked", "Husband", marital_status="Married", spouse=wife.name, anniversary=on_today(1988)
		)
		self.assertEqual(frappe.db.get_value("Person", wife.name, "next_anniversary"), getdate())

		husband.spouse = None
		husband.save(ignore_permissions=True)
		self.assertIsNone(frappe.db.get_value("Person", wife.name, "next_anniversary"))

	def test_the_patch_fills_the_next_dates_of_people_saved_before_they_existed(self):
		person = make_person(
			"_Test Before Greetings",
			marital_status="Married",
			anniversary=on_today(1988),
			life_events=[row("Birth", on_today(1980))],
		)
		frappe.db.set_value(
			"Person", person.name, {"next_birthday": None, "next_anniversary": None}, update_modified=False
		)

		send_birthday_and_anniversary_greetings.execute()

		self.assertEqual(
			frappe.db.get_value("Person", person.name, ["next_birthday", "next_anniversary"]),
			(getdate(), getdate()),
		)

	def test_the_patch_moves_a_copied_birthday_greeting_onto_the_person_and_keeps_its_text(self):
		copy = self.make_copy(
			"_Test Birthday Copy",
			document_type="Life Event",
			date_changed="date",
			condition=OLD_BIRTHDAY_CONDITION,
			subject='Happy Birthday, {{ frappe.db.get_value("Person", doc.parent, "first_name") }}!',
			message='{% set person = frappe.get_doc("Person", doc.parent) %}<p>Dear {{ person.first_name }}, _Test from our pastor</p>',
			recipients=[{"cc": OLD_BIRTHDAY_CC}],
		)
		make_person(
			"_Test Copied",
			"Birthday",
			life_events=[row("Birth", on_today(1980))],
			emails=email("_test_copied@example.com"),
		)

		send_birthday_and_anniversary_greetings.execute()
		send_birthday_and_anniversary_greetings.execute()

		moved = frappe.get_doc("Notification", copy.name)
		self.assertEqual(
			(moved.document_type, moved.event, moved.date_changed, moved.days_in_advance),
			("Person", "Days Before", "next_birthday", 0),
		)
		moved.enabled = 1
		sent = self.emailed(moved)["_test_copied@example.com"]
		self.assertEqual(sent.subject, "Happy Birthday, _Test Copied!")
		self.assertIn("Dear _Test Copied, _Test from our pastor", sent.message)

	def test_the_patch_moves_a_copied_anniversary_greeting_and_asks_for_a_married_couple(self):
		copy = self.make_copy(
			"_Test Anniversary Copy",
			document_type="Person",
			date_changed="anniversary",
			condition="doc.emails and doc.is_primary_contact",
		)

		send_birthday_and_anniversary_greetings.execute()
		send_birthday_and_anniversary_greetings.execute()
		# The next patch in patches.txt adds the active-people part of the shipped condition.
		sign_greeting_templates_and_greet_active_people.execute()

		shipped = self.shipped("Anniversary Greeting")
		self.assertEqual(
			frappe.db.get_value("Notification", copy.name, ["event", "date_changed", "condition"]),
			(shipped.event, shipped.date_changed, shipped.condition),
		)

	def test_the_patch_leaves_a_church_notification_that_sends_days_after_the_date(self):
		copy = self.make_copy(
			"_Test Week After Anniversary",
			document_type="Person",
			date_changed="anniversary",
			days_in_advance=7,
			condition="doc.emails",
		)

		send_birthday_and_anniversary_greetings.execute()

		self.assertEqual(
			frappe.db.get_value("Notification", copy.name, ["event", "date_changed", "condition"]),
			("Days After", "anniversary", "doc.emails"),
		)
