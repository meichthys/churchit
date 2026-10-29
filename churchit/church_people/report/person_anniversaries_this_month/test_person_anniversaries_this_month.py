# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, today

from churchit.church_people.number_card.anniversaries_this_week import anniversaries_this_week
from churchit.church_people.report.person_anniversaries_this_month import person_anniversaries_this_month
from churchit.tests.helpers import ensure, make_person

DEATH = {"event_type": "Death", "date": "2024-01-01"}


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
