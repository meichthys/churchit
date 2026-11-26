# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, add_years, getdate, today

from churchit.church_people.number_card.anniversaries_this_week import anniversaries_this_week
from churchit.church_people.report.person_anniversaries_this_month import person_anniversaries_this_month
from churchit.tests.helpers import ensure, make_person

DEATH = {"event_type": "Death", "date": "2024-01-01"}
REPORT_DATE = (
	"churchit.church_people.report.person_anniversaries_this_month.person_anniversaries_this_month.getdate"
)


def marry(first_name, spouse, **values):
	"""A person married to *spouse* twenty years ago today, who leads the couple's new family."""
	return make_person(
		first_name,
		"_Test Anniversary",
		spouse=spouse.name,
		marital_status="Married",
		anniversary=add_years(today(), -20),
		**values,
	)


class TestAnniversaryLists(FrappeTestCase):
	def test_a_couple_with_someone_who_has_died_is_left_out(self):
		ensure("Life Event Type", {"type": "Death"})
		living = marry("Living", make_person("Spouse", "_Test Anniversary"))
		count = anniversaries_this_week.get_count()
		widowed = marry("Widowed", make_person("Late Spouse", "_Test Anniversary", life_events=[DEATH]))
		departed = marry("Departed", make_person("Widow", "_Test Anniversary"), life_events=[DEATH])

		names = [row["name"] for row in person_anniversaries_this_month.execute({})[1]]

		self.assertIn(living.name, names)
		self.assertNotIn(widowed.name, names)
		self.assertNotIn(departed.name, names)
		self.assertEqual(anniversaries_this_week.get_count(), count)

	def test_an_anniversary_with_no_year_is_listed_without_its_years(self):
		known = marry("Known", make_person("Spouse", "_Test Anniversary"))
		unknown = marry("Unknown", make_person("Other", "_Test Anniversary"), anniversary_year_unknown=1)

		rows = {row["name"]: row for row in person_anniversaries_this_month.execute({})[1]}

		self.assertEqual(
			(rows[known.name].marriage_years, rows[known.name].anniversary_year_unknown), (20, 0)
		)
		# The desk script shows the anniversary of a row with the flag without its year.
		self.assertEqual(
			(rows[unknown.name].marriage_years, rows[unknown.name].anniversary_year_unknown), (None, 1)
		)

	def test_this_month_is_the_month_of_the_sites_date(self):
		next_month = add_months(getdate(), 1)
		couple = make_person(
			"Next Month",
			"_Test Anniversary",
			spouse=make_person("Spouse", "_Test Anniversary").name,
			marital_status="Married",
			anniversary=add_years(next_month, -20),
		)

		with patch(REPORT_DATE, return_value=next_month):
			self.assertIn(couple.name, listed())
		self.assertNotIn(couple.name, listed())


def listed():
	return [row["name"] for row in person_anniversaries_this_month.execute({})[1]]
