# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Personal Details form: a Birthday kept on the Birth life event, the directory and AI choices, and a
parent's edits."""

import frappe
from frappe.client import set_value
from frappe.website.doctype.web_form.web_form import accept

from churchit.ai.opt_outs import AI_OFF, AI_ON, MEMBER_AI_STATES
from churchit.ai.switch import SETTINGS
from churchit.church_people.derived import BIRTH
from churchit.church_people.member_access import PERSONAL_DETAILS, personal_details_fields
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.church_people.web_form.personal_details import personal_details as personal_details_form
from churchit.church_website.published_fields import MEMBERS, published_field_map
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_address

SHARE_FIELDS = ("share_email", "share_phone", "share_address", "share_birthday")
EDITOR = "_test_details_editor@example.com"


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

	def test_the_list_page_opens_the_members_own_record(self):
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())
		frappe.set_user(self.father_user)
		frappe.local.form_dict = frappe._dict(is_list=1)

		with self.assertRaises(frappe.Redirect):
			personal_details_form.get_context(frappe._dict())

		self.assertEqual(frappe.local.flags.redirect_location, f"/{PERSONAL_DETAILS}/{self.father}/edit")

	def test_the_list_page_stays_for_a_user_without_a_person(self):
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict(is_list=1)

		personal_details_form.get_context(frappe._dict())

	def test_the_form_cannot_print_the_office_view(self):
		self.assertEqual(frappe.db.get_value("Web Form", PERSONAL_DETAILS, "allow_print"), 0)

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

	def test_a_member_keeps_their_own_and_their_childs_details_out_of_ai_and_not_their_spouses(self):
		"""A parent who may edit a child's details sets it for the child too, as for the rest of the form."""
		own, spouse, child = (
			form_values(person, exclude_from_ai=1) for person in (self.father, self.mother, self.son)
		)
		frappe.set_user(self.father_user)

		accept(PERSONAL_DETAILS, own)
		with self.assertRaises(frappe.PermissionError):
			accept(PERSONAL_DETAILS, spouse)
		accept(PERSONAL_DETAILS, child)

		frappe.set_user("Administrator")
		self.assertEqual(
			[
				frappe.db.get_value("Person", person, "exclude_from_ai")
				for person in (self.father, self.mother, self.son)
			],
			[1, 0, 1],
		)

	def test_only_the_person_a_parent_or_a_system_manager_clears_the_ai_choice(self):
		"""Staff may tick it for a person who asks, and may not clear it."""
		ensure_user(EDITOR, "Details Editor", roles=("Church People Editor",))
		for person in (self.father, self.mother, self.son):
			frappe.db.set_value("Person", person, "exclude_from_ai", 1)

		frappe.set_user(EDITOR)
		with self.assertRaisesRegex(frappe.PermissionError, "Only the person, a parent of a child"):
			set_value("Person", self.father, "exclude_from_ai", 0)
		set_value("Person", self.grandmother, "exclude_from_ai", 1)

		frappe.set_user(self.father_user)
		accept(PERSONAL_DETAILS, form_values(self.father, exclude_from_ai=0))
		accept(PERSONAL_DETAILS, form_values(self.son, exclude_from_ai=0))

		frappe.set_user("Administrator")
		set_value("Person", self.mother, "exclude_from_ai", 0)
		self.assertEqual(
			[
				frappe.db.get_value("Person", person, "exclude_from_ai")
				for person in (self.father, self.mother, self.son, self.grandmother)
			],
			[0, 0, 0, 1],
		)

	def test_the_ai_section_says_whether_the_church_uses_ai_now(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.set_user(self.father_user)
		frappe.local.form_dict = frappe._dict(name=self.father, is_edit=1)
		frappe.local.path = f"{PERSONAL_DETAILS}/{self.father}/edit"
		for enabled, state in ((0, AI_OFF), (1, AI_ON)):
			frappe.db.set_single_value(SETTINGS, "enabled", enabled)
			context = frappe._dict()
			frappe.get_doc("Web Form", PERSONAL_DETAILS).get_context(context)
			[section] = [f for f in context.web_form_doc.web_form_fields if f.fieldname == "ai_section"]
			self.assertTrue(section.description.startswith(MEMBER_AI_STATES[state]), section.description)
			self.assertIn("briefings", section.description, "The section's own help stays")

	def open_own_form(self):
		"""The Personal Details form's context as the father opens his own record."""
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.set_user(self.father_user)
		frappe.local.form_dict = frappe._dict(name=self.father, is_edit=1)
		frappe.local.path = f"{PERSONAL_DETAILS}/{self.father}/edit"
		context = frappe._dict()
		frappe.get_doc("Web Form", PERSONAL_DETAILS).get_context(context)
		return {field.fieldname: field for field in context.web_form_doc.web_form_fields}

	def test_the_type_columns_offer_every_type(self):
		ensure("Email Type", {"type": "_Test Details Work"})
		ensure("Phone Type", {"type": "_Test Details Office"})

		fields = self.open_own_form()

		for table, column, value in (
			("emails", "email_type", "_Test Details Work"),
			("phones", "phone_type", "_Test Details Office"),
		):
			[df] = [df for df in fields[table].fields if df["fieldname"] == column]
			self.assertIn(value, df["options"], table)

	def test_a_member_sees_their_addresses_but_the_office_changes_them(self):
		fields = self.open_own_form()

		self.assertEqual(fields["addresses"].read_only, 1)
		self.assertIn("tell the church office", fields["addresses"].description)

	def test_a_member_cannot_change_their_addresses_by_posting_them(self):
		"""Frappe's accept sets a read-only field from the post too, so the server refuses the change."""
		home, other = (make_address(f"_Test Details {title}").name for title in ("Home", "Other"))
		father = frappe.get_doc("Person", self.father)
		father.append("addresses", {"address": home})
		father.save(ignore_permissions=True)
		frappe.set_user(self.father_user)

		accept(PERSONAL_DETAILS, form_values(self.father, alergies="_Test Pollen"))
		for addresses in ([], [{"address": other}]):
			with self.assertRaises(frappe.PermissionError):
				accept(PERSONAL_DETAILS, form_values(self.father, addresses=addresses))

		frappe.set_user("Administrator")
		father.reload()
		self.assertEqual(
			(father.alergies, [row.address for row in father.addresses]), ("_Test Pollen", [home])
		)

	def test_the_directory_section_says_when_the_church_has_no_member_directory(self):
		for enabled, wording in ((1, "What the other members"), (0, "has no Member Directory page")):
			frappe.db.set_single_value("People Settings", "member_directory", enabled)
			self.assertIn(wording, self.open_own_form()["directory_section"].description, enabled)

	def test_a_save_says_the_details_are_saved_and_goes_back_to_the_household(self):
		form = frappe.get_doc("Web Form", PERSONAL_DETAILS)

		self.assertEqual(
			(form.success_title, form.success_message, form.success_url),
			("Saved", "Your details are saved.", "/household"),
		)

	def test_the_badge_marks_the_ai_choice_as_shown_to_members(self):
		sources = published_field_map()["Person"]["exclude_from_ai"]

		self.assertIn(
			(PERSONAL_DETAILS, MEMBERS), {(source["route"], source["access"]) for source in sources}
		)
