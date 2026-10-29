# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, getdate, today

from churchit.church_people.number_card.birthdays_this_week import birthdays_this_week
from churchit.church_people.report.person_birthdays_this_month import person_birthdays_this_month
from churchit.church_people.report.person_birthdays_this_week import person_birthdays_this_week
from churchit.tests.helpers import ensure, make_person


class TestBirthdayLists(FrappeTestCase):
	def test_people_who_have_died_are_left_out(self):
		for event_type in ("Birth", "Death"):
			ensure("Life Event Type", {"type": event_type})
		birth = {"event_type": "Birth", "date": add_years(today(), -70)}
		living = make_person("_Test Birthday", "Living", life_events=[birth])
		count = birthdays_this_week.get_count()
		departed = make_person(
			"_Test Birthday", "Departed", life_events=[birth, {"event_type": "Death", "date": "2024-01-01"}]
		)

		for report in (person_birthdays_this_week, person_birthdays_this_month):
			with self.subTest(report.__name__):
				names = [row["name"] for row in report.execute({})[1]]
				self.assertIn(living.name, names)
				self.assertNotIn(departed.name, names)
		self.assertEqual(birthdays_this_week.get_count(), count)

	def test_a_birthday_with_no_year_is_listed_without_an_age(self):
		ensure("Life Event Type", {"type": "Birth"})
		count = birthdays_this_week.get_count()
		known = make_person("_Test Birthday", "Known", life_events=[birth_on(add_years(today(), -40))])
		yearless = make_person(
			"_Test Birthday", "Yearless", life_events=[birth_on(add_years(today(), -1), year_unknown=1)]
		)

		for report in (person_birthdays_this_week, person_birthdays_this_month):
			with self.subTest(report.__name__):
				rows = {row["name"]: (row["birthday"], row["age"]) for row in report.execute({})[1]}
				self.assertEqual(rows[known.name], (getdate(), 40))
				self.assertEqual(rows[yearless.name], (getdate(), None))
		self.assertEqual(birthdays_this_week.get_count(), count + 2)

	def test_a_week_across_the_new_year_lists_both_years_in_order(self):
		ensure("Life Event Type", {"type": "Birth"})
		december = make_person("_Test Birthday", "December", life_events=[birth_on("1990-12-30")])
		january = make_person(
			"_Test Birthday", "January", life_events=[birth_on("1900-01-02", year_unknown=1)]
		)

		with patch("churchit.query.getdate", return_value=getdate("2031-12-31")):
			rows = person_birthdays_this_week.execute({})[1]

		self.assertEqual(
			[
				(row["name"], row["birthday"], row["age"])
				for row in rows
				if "_Test Birthday" in row["full_name"]
			],
			[(december.name, getdate("2031-12-30"), 41), (january.name, getdate("2032-01-02"), None)],
		)

	def test_a_leap_day_birthday_counts_on_february_28_in_a_common_year(self):
		ensure("Life Event Type", {"type": "Birth"})
		with patch("churchit.query.getdate", return_value=getdate("2031-02-26")):
			count = birthdays_this_week.get_count()
			leapling = make_person("_Test Birthday", "Leapling", life_events=[birth_on("1988-02-29")])
			rows = {
				row["name"]: (row["birthday"], row["age"])
				for row in person_birthdays_this_week.execute({})[1]
			}

			self.assertEqual(birthdays_this_week.get_count(), count + 1)
		self.assertEqual(rows[leapling.name], (getdate("2031-02-28"), 43))


def birth_on(date, year_unknown=0):
	return {"event_type": "Birth", "date": date, "year_unknown": year_unknown}
