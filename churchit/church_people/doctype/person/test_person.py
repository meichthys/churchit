# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, nowdate


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestPerson(FrappeTestCase):
	def _make_person(self, **values):
		return frappe.get_doc({"doctype": "Person", **values}).insert(ignore_permissions=True)

	def test_full_name_built_from_first_and_last(self):
		person = self._make_person(first_name="John", last_name="Doe")
		self.assertEqual(person.full_name, "John Doe")

	def test_full_name_with_only_first_name(self):
		person = self._make_person(first_name="Madonna")
		self.assertEqual(person.full_name, "Madonna")

	def test_age_computed_from_birth_life_event(self):
		_ensure("Life Event Type", {"type": "Birth"}, {"type": "Birth"})
		person = frappe.get_doc({"doctype": "Person", "first_name": "Aged"})
		person.append("life_events", {"event_type": "Birth", "date": add_years(nowdate(), -30)})
		person.insert(ignore_permissions=True)
		self.assertEqual(person.age, 30)

	def test_age_cleared_without_birth_event(self):
		person = self._make_person(first_name="Ageless")
		self.assertIsNone(person.age)

	def test_setting_family_adds_person_to_family_members(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Smith Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Sam", last_name="Smith", family=family.name)

		family.reload()
		members = [m.member for m in family.members]
		self.assertIn(person.name, members)

	def test_removing_family_clears_head_of_household(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Head Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(
			first_name="Head", last_name="Honcho", family=family.name, is_head_of_household=1
		)
		self.assertTrue(person.is_head_of_household)

		person.family = None
		person.save(ignore_permissions=True)
		self.assertFalse(person.is_head_of_household)

	def test_deleting_person_removes_them_from_family(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Departing Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Gone", last_name="Soon", family=family.name)
		family.reload()
		self.assertIn(person.name, [m.member for m in family.members])

		person.delete()

		family.reload()
		self.assertNotIn(person.name, [m.member for m in family.members])

	def test_deleting_person_whose_family_is_already_gone(self):
		# A bulk delete removes the Family first; the Person still has to go.
		family = frappe.get_doc({"doctype": "Family", "family_name": "Vanished Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Orphan", last_name="Record", family=family.name)
		frappe.delete_doc("Family", family.name, force=True, ignore_permissions=True)

		person.delete()

		self.assertFalse(frappe.db.exists("Person", person.name))

	def test_spouse_link_is_reciprocated(self):
		wife = self._make_person(first_name="Jane", last_name="Doe")
		husband = self._make_person(first_name="John", last_name="Doe")

		husband.spouse = wife.name
		husband.is_married = 1
		husband.save(ignore_permissions=True)

		# The controller links the relationship back on the spouse record.
		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), husband.name)
		self.assertTrue(frappe.db.get_value("Person", wife.name, "is_married"))

	def test_unlinking_spouse_clears_both_sides(self):
		wife = self._make_person(first_name="Ann", last_name="Split")
		husband = self._make_person(first_name="Bob", last_name="Split", spouse=wife.name, is_married=1)

		husband.is_married = 0
		husband.save(ignore_permissions=True)

		self.assertIsNone(husband.spouse)
		self.assertIsNone(frappe.db.get_value("Person", wife.name, "spouse"))
		self.assertFalse(frappe.db.get_value("Person", wife.name, "is_married"))

	def test_new_head_of_household_demotes_the_old_one_and_renames_family(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Swap - Old"}).insert(
			ignore_permissions=True
		)
		old_head = self._make_person(first_name="Old", family=family.name, is_head_of_household=1)
		self._make_person(first_name="New", family=family.name, is_head_of_household=1)

		self.assertFalse(frappe.db.get_value("Person", old_head.name, "is_head_of_household"))
		self.assertEqual(frappe.db.get_value("Family", family.name, "family_name"), "Swap - New")

	def test_new_family_from_person_creates_and_heads_a_family(self):
		person = self._make_person(first_name="Founder", last_name="Fam")
		person.new_family_from_person()

		person.reload()
		self.assertTrue(person.family)
		self.assertTrue(person.is_head_of_household)
		self.assertEqual(frappe.db.get_value("Family", person.family, "family_name"), "Fam - Founder")

	def test_new_family_from_person_joins_an_existing_family_of_the_same_name(self):
		existing = frappe.get_doc({"doctype": "Family", "family_name": "Twin - Joiner"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Joiner", last_name="Twin")
		person.new_family_from_person()

		person.reload()
		self.assertEqual(person.family, existing.name)
		self.assertFalse(person.is_head_of_household)

	def test_invite_to_portal_requires_an_email_address(self):
		person = self._make_person(first_name="Unreachable")
		_ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Outgoing",
				"email_id": "_test_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		with self.assertRaises(frappe.ValidationError):
			person.invite_to_portal()

	def test_user_dashboard_data_links_the_person_doctype(self):
		from churchit.church_people.doctype.person.person import get_user_dashboard_data

		data = get_user_dashboard_data({"transactions": []})
		self.assertIn({"label": "Church", "items": ["Person"]}, data["transactions"])
		self.assertEqual(data["non_standard_fieldnames"]["Person"], "user")
