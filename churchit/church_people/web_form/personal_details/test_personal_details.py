# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Personal Details form: a Birthday kept on the Birth life event, the directory choices, and a parent's edits."""

import frappe
from frappe.website.doctype.web_form.web_form import accept

from churchit.church_people.derived import BIRTH
from churchit.church_people.member_access import PERSONAL_DETAILS, personal_details_fields
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.tests.helpers import RollbackEachTest, ensure

SHARE_FIELDS = ("share_email", "share_phone", "share_address", "share_birthday")


def births(person):
	"""(date, year unknown) of each of *person*'s Birth life events, as saved."""
	return [
		(str(row.date), row.year_unknown)
		for row in frappe.get_doc("Person", person).life_events
		if row.event_type == BIRTH
	]


def form_values(person, **changes):
	"""What the Personal Details form sends for *person*: every field it shows, with *changes*."""
	doc = frappe.get_doc("Person", person).as_dict(convert_dates_to_str=True)
	values = {fieldname: doc.get(fieldname) for fieldname in personal_details_fields()}
	return frappe.as_json({**values, **changes, "doctype": "Person", "name": person})


class TestPersonalDetails(RollbackEachTest):
	"""The Smiths: John and Jane (Adults), Tim (Child, 10) and Gran (Other Adult)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		ensure("Life Event Type", {"type": BIRTH})
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household(
			"_Test Personal Details"
		)
		cls.father_user = link_user(cls.father, "_test_details_father@example.com")
		cls.son_user = link_user(cls.son, "_test_details_son@example.com")

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

	def test_the_form_offers_the_birthday_and_the_directory_choices(self):
		fields = personal_details_fields()

		self.assertTrue({"birthday", "hide_from_directory", *SHARE_FIELDS} <= fields)

	def test_a_member_gives_their_birthday_and_directory_choices_on_the_form(self):
		frappe.set_user(self.father_user)

		accept(
			PERSONAL_DETAILS,
			form_values(
				self.father,
				birthday="1985-03-14",
				share_email=1,
				share_phone=0,
				share_address=0,
				share_birthday=1,
			),
		)

		frappe.set_user("Administrator")
		self.assertEqual(births(self.father), [("1985-03-14", 0)])
		self.assertEqual(
			frappe.db.get_value("Person", self.father, list(SHARE_FIELDS), as_dict=True),
			{"share_email": 1, "share_phone": 0, "share_address": 0, "share_birthday": 1},
		)

	def test_an_adult_opens_and_saves_their_childs_details(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.set_user(self.father_user)
		frappe.local.form_dict = frappe._dict(name=self.son, is_edit=1)
		frappe.local.path = f"{PERSONAL_DETAILS}/{self.son}/edit"
		context = frappe._dict()
		frappe.get_doc("Web Form", PERSONAL_DETAILS).get_context(context)
		self.assertEqual(context.reference_doc["name"], self.son)
		self.assertNotIn("medical_notes", context.reference_doc)

		accept(PERSONAL_DETAILS, form_values(self.son, alergies="_Test Peanuts"))

		self.assertEqual(frappe.db.get_value("Person", self.son, "alergies"), "_Test Peanuts")

	def test_a_child_cannot_open_or_save_a_parents_details(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		values = form_values(self.father, alergies="_Test Peanuts")
		frappe.set_user(self.son_user)
		frappe.local.form_dict = frappe._dict(name=self.father, is_edit=1)
		frappe.local.path = f"{PERSONAL_DETAILS}/{self.father}/edit"

		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Web Form", PERSONAL_DETAILS).get_context(frappe._dict())
		with self.assertRaises(frappe.PermissionError):
			accept(PERSONAL_DETAILS, values)
		self.assertFalse(frappe.db.get_value("Person", self.father, "alergies"))
