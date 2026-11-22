# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Birthday of a Person is the date of their first Birth life event."""

import frappe

from churchit.church_people.derived import BIRTH
from churchit.church_people.test_household import make_household, set_adult_age
from churchit.tests.helpers import RollbackEachTest, ensure


def births(person):
	"""(date, year unknown) of each of *person*'s Birth life events, as saved."""
	return [
		(str(row.date), row.year_unknown)
		for row in frappe.get_doc("Person", person).life_events
		if row.event_type == BIRTH
	]


class TestPersonBirthday(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		ensure("Life Event Type", {"type": BIRTH})
		_family, cls.father, _mother, cls.son, _grandmother = make_household("_Test Person Birthday")

	def save_birthday(self, person, birthday):
		doc = frappe.get_doc("Person", person)
		doc.set("birthday", birthday)
		doc.save(ignore_permissions=True)
		return doc

	def test_the_birthday_is_the_birth_date(self):
		person = frappe.get_doc("Person", self.son)

		self.assertEqual(person.birthday, person.birth_date)
		self.assertEqual(person.as_dict()["birthday"], person.birth_date)

	def test_a_birthday_adds_a_birth_event_to_someone_without_one(self):
		person = self.save_birthday(self.father, "1985-03-14")

		self.assertEqual(births(self.father), [("1985-03-14", 0)])
		self.assertEqual(str(person.birth_date), "1985-03-14")

	def test_a_birthday_changes_the_first_birth_event(self):
		self.save_birthday(self.son, "2016-05-02")

		self.assertEqual(births(self.son), [("2016-05-02", 0)])

	def test_a_birthday_gives_a_birth_whose_year_is_unknown_its_year(self):
		frappe.db.set_value("Life Event", {"parent": self.son, "event_type": BIRTH}, "year_unknown", 1)
		date = births(self.son)[0][0]
		person = self.save_birthday(self.son, "")
		self.assertEqual(births(self.son), [(date, 1)], "a blank Birthday keeps the year unknown")
		self.assertIsNone(person.birth_date)

		self.save_birthday(self.son, f"2015{date[4:]}")

		self.assertEqual(births(self.son), [(f"2015{date[4:]}", 0)])

	def test_the_office_changing_the_birth_event_wins_over_the_birthday_the_desk_sends_back(self):
		"""The desk sends every field it loaded, so the Birthday it sends is the birth date before the change."""
		person = frappe.get_doc("Person", self.son)
		person.set("birthday", person.birthday)
		next(row for row in person.life_events if row.event_type == BIRTH).date = "2016-05-02"
		person.save(ignore_permissions=True)

		self.assertEqual(births(self.son), [("2016-05-02", 0)])
