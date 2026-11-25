# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.client import set_value

from churchit.ai.opt_outs import AI_OFF, AI_ON, MEMBER_AI_STATES
from churchit.ai.switch import SETTINGS
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.derived import BIRTH
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.church_website.pages import sync_page_switches
from churchit.portal import account
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_two_churches


def switch_page(route, enabled):
	features = frappe.get_single("Church Features")
	features.get("website_pages", {"route": route})[0].enabled = enabled
	features.save()


class TestAccountApi(RollbackEachTest):
	"""The Smiths of church A (John and Jane Adults, Tim a Child of 10, Gran) and the Joneses of church B."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		sync_page_switches()
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household("_Test Portal Account")
		frappe.db.set_value("Family", cls.family, "church", cls.branch_a)
		frappe.db.set_value("Person", {"family": cls.family}, "church", cls.branch_a)
		cls.father_user = link_user(cls.father, "_test_portal_account_father@example.com")
		cls.mother_user = link_user(cls.mother, "_test_portal_account_mother@example.com")
		cls.son_user = link_user(cls.son, "_test_portal_account_son@example.com")
		for user in (cls.father_user, cls.mother_user, cls.son_user):
			set_user_church(user, cls.branch_a)

		other = make_household("_Test Portal Account Other", "Jones")
		cls.other_father = other[1]
		frappe.db.set_value("Family", other[0], "church", cls.branch_b)
		frappe.db.set_value("Person", {"family": other[0]}, "church", cls.branch_b)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.in_web_form = False
		super().tearDown()

	def save(self, person, **values):
		details = account.get_personal_details(person)
		return account.save_personal_details(
			person,
			details["modified"],
			values.pop("values", {}),
			values.pop("emails", None),
			values.pop("phones", None),
		)

	def test_a_member_reads_only_the_fields_of_the_form(self):
		frappe.set_user(self.father_user)
		result = account.get_personal_details()

		self.assertEqual(result["name"], self.father)
		self.assertTrue(result["is_you"])
		self.assertTrue(result["can_edit"])
		self.assertNotIn("medical_notes", result["values"])
		self.assertNotIn("membership", result["values"])
		self.assertIn("first_name", result["fields"])
		self.assertNotIn("addresses", result["values"])
		self.assertIn("genders", result["options"])

	def test_an_adult_reads_their_child_but_not_another_adult_or_another_church(self):
		frappe.set_user(self.father_user)
		self.assertEqual(account.get_personal_details(self.son)["name"], self.son)

		for other in (self.mother, self.other_father):
			with self.assertRaises(frappe.PermissionError):
				account.get_personal_details(other)

	def test_a_child_cannot_read_a_parent(self):
		frappe.set_user(self.son_user)

		with self.assertRaises(frappe.PermissionError):
			account.get_personal_details(self.father)

	def test_a_switched_off_page_is_refused(self):
		switch_page("personal-details", 0)
		frappe.set_user(self.father_user)

		with self.assertRaises(frappe.PermissionError):
			account.get_personal_details()
		with self.assertRaises(frappe.PermissionError):
			account.save_personal_details(self.father, "", {})

	def test_a_member_saves_their_own_fields(self):
		frappe.set_user(self.father_user)
		result = self.save(self.father, values={"alergies": "Peanuts", "share_email": 1})

		self.assertEqual(result["values"]["alergies"], "Peanuts")
		self.assertEqual(frappe.db.get_value("Person", self.father, "alergies"), "Peanuts")

	def test_an_adult_saves_their_childs_record(self):
		frappe.set_user(self.father_user)
		self.save(self.son, values={"alergies": "Milk"})

		self.assertEqual(frappe.db.get_value("Person", self.son, "alergies"), "Milk")

	def test_a_member_cannot_save_another_members_record(self):
		frappe.set_user(self.father_user)
		with self.assertRaises(frappe.PermissionError):
			account.save_personal_details(
				self.mother, str(frappe.db.get_value("Person", self.mother, "modified")), {}
			)
		with self.assertRaises(frappe.PermissionError):
			account.save_personal_details(
				self.other_father, str(frappe.db.get_value("Person", self.other_father, "modified")), {}
			)

	def test_a_field_outside_the_form_is_refused(self):
		frappe.set_user(self.father_user)
		modified = account.get_personal_details()["modified"]

		for field, value in (("membership", "Member"), ("family", None), ("user", None), ("addresses", [])):
			with self.assertRaises(frappe.PermissionError, msg=field):
				account.save_personal_details(self.father, modified, {field: value})

	def test_a_stale_save_is_refused(self):
		frappe.set_user(self.father_user)
		modified = account.get_personal_details()["modified"]
		frappe.db.set_value("Person", self.father, "alergies", "Changed by staff")

		with self.assertRaises(frappe.TimestampMismatchError):
			account.save_personal_details(self.father, modified, {"alergies": "Mine"})
		self.assertEqual(frappe.db.get_value("Person", self.father, "alergies"), "Changed by staff")

	def test_contact_rows_are_added_kept_and_removed(self):
		frappe.set_user(self.father_user)
		email_type = account.get_options()["email_types"]
		first = account.get_personal_details()
		kept = first["emails"]

		rows = [
			*kept,
			{"email_address": "new.address@example.com", "email_type": email_type[0] if email_type else None},
		]
		result = self.save(self.father, emails=rows)
		self.assertEqual(
			{row["email_address"] for row in result["emails"]},
			{row["email_address"] for row in rows},
		)

		result = self.save(
			self.father,
			emails=[row for row in result["emails"] if row["email_address"] != "new.address@example.com"],
		)
		self.assertEqual(len(result["emails"]), len(kept))

	def test_an_email_held_by_another_person_is_refused_until_shared(self):
		frappe.set_user("Administrator")
		held = frappe.get_doc("Person", self.mother)
		held.append("emails", {"email_address": "mother.held@example.com", "is_primary": 1})
		held.save(ignore_permissions=True)

		frappe.set_user(self.father_user)
		rows = [*account.get_personal_details()["emails"], {"email_address": "mother.held@example.com"}]
		with self.assertRaises(frappe.ValidationError):
			self.save(self.father, emails=rows)

	def test_shared_from_names_only_a_person_the_member_may_read(self):
		frappe.set_user("Administrator")
		held = frappe.get_doc("Person", self.other_father)
		held.append("emails", {"email_address": "other.held@example.com", "is_primary": 1})
		held.save(ignore_permissions=True)

		frappe.set_user(self.father_user)
		rows = [
			*account.get_personal_details()["emails"],
			{"email_address": "other.held@example.com", "shared_from": self.other_father},
		]
		with self.assertRaises(frappe.PermissionError):
			self.save(self.father, emails=rows)

	def test_the_birthday_reads_from_the_stored_date(self):
		frappe.set_user(self.father_user)
		result = account.get_personal_details(self.son)

		self.assertEqual(
			result["values"]["birthday"], str(frappe.db.get_value("Person", self.son, "birth_date"))
		)

	def test_a_member_gives_their_birthday_and_directory_choices(self):
		ensure("Life Event Type", {"type": BIRTH})
		frappe.set_user(self.father_user)

		self.save(
			self.father,
			values={
				"birthday": "1985-03-14",
				"share_email": 1,
				"share_phone": 0,
				"share_address": 0,
				"share_birthday": 1,
			},
		)

		frappe.set_user("Administrator")
		person = frappe.get_doc("Person", self.father)
		self.assertEqual(
			[(str(row.date), row.year_unknown) for row in person.life_events if row.event_type == BIRTH],
			[("1985-03-14", 0)],
		)
		self.assertEqual(
			(person.share_email, person.share_phone, person.share_address, person.share_birthday),
			(1, 0, 0, 1),
		)

	def test_a_member_keeps_their_own_and_their_childs_details_out_of_ai_and_not_their_spouses(self):
		"""A parent who may edit a child's details sets it for the child too, as for the rest of the page."""
		frappe.set_user(self.father_user)

		self.save(self.father, values={"exclude_from_ai": 1})
		with self.assertRaises(frappe.PermissionError):
			self.save(self.mother, values={"exclude_from_ai": 1})
		self.save(self.son, values={"exclude_from_ai": 1})

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
		editor = ensure_user(
			"_test_account_editor@example.com", "Details Editor", roles=("Church People Editor",)
		)
		set_user_church(editor, self.branch_a)
		for person in (self.father, self.mother, self.son):
			frappe.db.set_value("Person", person, "exclude_from_ai", 1)

		frappe.set_user(editor)
		with self.assertRaisesRegex(frappe.PermissionError, "Only the person, a parent of a child"):
			set_value("Person", self.father, "exclude_from_ai", 0)

		frappe.set_user(self.father_user)
		self.save(self.father, values={"exclude_from_ai": 0})
		self.save(self.son, values={"exclude_from_ai": 0})

		frappe.set_user("Administrator")
		set_value("Person", self.mother, "exclude_from_ai", 0)
		self.assertEqual(
			[
				frappe.db.get_value("Person", person, "exclude_from_ai")
				for person in (self.father, self.mother, self.son)
			],
			[0, 0, 0],
		)

	def test_the_notes_say_whether_the_church_uses_ai_and_has_a_member_directory(self):
		frappe.set_user(self.father_user)
		for enabled, state in ((0, AI_OFF), (1, AI_ON)):
			frappe.db.set_single_value(SETTINGS, "enabled", enabled)
			self.assertTrue(
				account.get_personal_details()["notes"]["ai_state"].startswith(MEMBER_AI_STATES[state])
			)
		for enabled in (1, 0):
			frappe.db.set_single_value("People Settings", "member_directory", enabled)
			self.assertEqual(account.get_personal_details()["notes"]["directory_off"], not enabled)

	def test_a_member_cannot_change_their_addresses_by_posting_them(self):
		frappe.set_user(self.father_user)
		modified = account.get_personal_details()["modified"]

		with self.assertRaises(frappe.PermissionError):
			account.save_personal_details(self.father, modified, {"addresses": []})

	def test_the_preferences_name_the_purposes_and_the_push_key(self):
		frappe.set_user(self.father_user)
		result = account.get_preferences()

		self.assertIsInstance(result["purposes"], list)
		self.assertIn("channels", result)
		self.assertIn("push_public_key", result)

	def test_the_preferences_refuse_a_guest(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			account.get_preferences()

	def test_holders_refuses_an_unknown_kind_and_a_record_the_member_cannot_read(self):
		frappe.set_user(self.father_user)
		with self.assertRaises(frappe.ValidationError):
			account.get_holders("fax", "x", self.father)
		with self.assertRaises(frappe.PermissionError):
			account.get_holders("email", "x", self.other_father)
		self.assertEqual(account.get_holders("email", "nobody@example.com", self.father), {"items": []})
