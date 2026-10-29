# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, getdate, nowdate

from churchit.church_people.derived import (
	ADULT,
	CHILD,
	get_derived_values,
	get_grade,
	get_grade_number,
	life_stage_for,
	refresh_daily,
)
from churchit.church_people.membership import living_people_filter
from churchit.patches.v1_0 import derive_birth_death_and_life_stage, store_new_people_settings_defaults
from churchit.tests.helpers import ensure, make_person


def row(event_type, date=None, year_unknown=0):
	return frappe._dict(event_type=event_type, date=date, year_unknown=year_unknown)


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
