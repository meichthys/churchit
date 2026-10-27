# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.api.v1 import read_doc
from frappe.client import get as client_get
from frappe.desk.form.load import getdoc
from frappe.desk.search import search_link
from frappe.handler import run_doc_method
from frappe.permissions import add_user_permission
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, getdate, nowdate

from churchit.church_communications.newsletter import email_church, has_unsubscribed, set_subscribed
from churchit.church_foundations.church_access import set_user_church, user_church_permissions
from churchit.church_people.derived import refresh_daily
from churchit.church_people.doctype.inactive_reason.inactive_reason import DECEASED
from churchit.church_people.doctype.person.person import SOURCE_IMPORT
from churchit.church_people.merge import merge_people
from churchit.church_people.test_merge import phone
from churchit.patches.v1_0 import set_inactive_since_from_history
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_person,
	make_primary_contact,
	make_two_churches,
	set_private_people,
)


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


def without_church(user):
	"""*user* with no Church permission, which reaches every church."""
	frappe.db.delete("User Permission", {"user": user, "allow": "Church"})
	return user


def ensure_outgoing_email_account():
	return _ensure(
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


class TestPerson(FrappeTestCase):
	def _make_person(self, **values):
		return frappe.get_doc({"doctype": "Person", **values}).insert(ignore_permissions=True)

	def test_full_name_built_from_first_and_last(self):
		person = self._make_person(first_name="John", last_name="Doe")
		self.assertEqual(person.full_name, "John Doe")

	def test_full_name_with_only_first_name(self):
		person = self._make_person(first_name="Madonna")
		self.assertEqual(person.full_name, "Madonna")

	def test_display_name_is_the_name_a_person_goes_by(self):
		person = self._make_person(first_name="Robert", last_name="Smith", nickname="Bob", suffix="Jr.")
		self.assertEqual(person.display_name, "Bob Smith Jr.")
		self.assertEqual(person.full_name, "Robert Smith")

		person.nickname = None
		person.save()
		self.assertEqual(person.display_name, "Robert Smith Jr.")

	def test_display_name_with_only_first_name(self):
		self.assertEqual(self._make_person(first_name="Cher").display_name, "Cher")

	def test_link_search_finds_the_nickname_and_the_previous_last_name(self):
		person = self._make_person(
			first_name="Margaret",
			last_name="_Test Wedded",
			nickname="_Test Peggy",
			previous_last_name="_Test Maiden",
		)
		for text in ("_Test Peggy", "_Test Maiden"):
			self.assertIn(person.name, [result["value"] for result in search_link("Person", text)], text)

	def test_desk_views_of_a_person_are_logged(self):
		person = self._make_person(first_name="_Test Viewed")
		getdoc("Person", person.name)
		self.assertTrue(
			frappe.db.exists("View Log", {"reference_doctype": "Person", "reference_name": person.name})
		)

	def test_age_computed_from_birth_life_event(self):
		_ensure("Life Event Type", {"type": "Birth"}, {"type": "Birth"})
		person = frappe.get_doc({"doctype": "Person", "first_name": "Aged"})
		person.append("life_events", {"event_type": "Birth", "date": add_years(nowdate(), -30)})
		person.insert(ignore_permissions=True)
		self.assertEqual(person.age, 30)

	def test_daily_refresh_catches_up_a_stale_age_and_marriage(self):
		"""Age and years married are stored on save, so a birthday alone left them a year behind."""
		_ensure("Life Event Type", {"type": "Birth"}, {"type": "Birth"})
		person = self._make_person(
			first_name="_Test Stale",
			anniversary=add_years(nowdate(), -10),
			life_events=[{"event_type": "Birth", "date": add_years(nowdate(), -30)}],
		)
		frappe.db.set_value("Person", person.name, {"age": 29, "marriage_years": 9}, update_modified=False)

		refresh_daily()

		self.assertEqual(frappe.db.get_value("Person", person.name, ["age", "marriage_years"]), (30, 10))

	def test_age_cleared_without_birth_event(self):
		person = self._make_person(first_name="Ageless")
		self.assertEqual(person.age, 0)

	def test_setting_family_adds_person_to_family_members(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Smith Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Sam", last_name="Smith", family=family.name)

		family.reload()
		members = [m.member for m in family.members]
		self.assertIn(person.name, members)

	def test_leaving_the_family_clears_its_primary_contact(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Contact Household"}).insert(
			ignore_permissions=True
		)
		person = make_primary_contact(
			self._make_person(first_name="Head", last_name="Honcho", family=family.name)
		)
		self.assertTrue(person.is_primary_contact)

		person.family = None
		person.save(ignore_permissions=True)
		self.assertFalse(person.is_primary_contact)
		self.assertIsNone(frappe.db.get_value("Family", family.name, "primary_contact"))

	def test_moving_to_another_family_leaves_the_old_one(self):
		old = frappe.get_doc({"doctype": "Family", "family_name": "Left Household"}).insert(
			ignore_permissions=True
		)
		new = frappe.get_doc({"doctype": "Family", "family_name": "Joined Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Mover", last_name="Along", family=old.name)

		person.family = new.name
		person.save(ignore_permissions=True)
		# Saving the old family used to pull the person back into it.
		old.reload()
		old.save(ignore_permissions=True)

		self.assertNotIn(person.name, [m.member for m in old.members])
		self.assertEqual(frappe.db.get_value("Person", person.name, "family"), new.name)

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

	def test_deleting_a_person_whose_phone_a_household_member_shares(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Sharing Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Imported", family=family.name, phones=[phone("555-010-0417")])
		member = self._make_person(
			first_name="Staying",
			family=family.name,
			phones=[phone("555-010-0417", shared_from_type="Person", shared_from=person.name)],
		)

		person.delete()

		self.assertFalse(frappe.db.exists("Person", person.name))
		self.assertIsNone(frappe.db.get_value("Phone Number", {"parent": member.name}, "shared_from"))

	def test_spouse_link_is_reciprocated(self):
		wife = self._make_person(first_name="Jane", last_name="Doe", gender="Female")
		husband = self._make_person(first_name="John", last_name="Doe", gender="Male")

		husband.spouse = wife.name
		husband.marital_status = "Married"
		husband.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), husband.name)
		self.assertEqual(frappe.db.get_value("Person", wife.name, "marital_status"), "Married")

	def test_anniversary_and_marriage_years_shared_with_spouse(self):
		wife = self._make_person(first_name="Amy", last_name="Years", anniversary=add_years(nowdate(), -10))
		husband = self._make_person(
			first_name="Al", last_name="Years", spouse=wife.name, marital_status="Married"
		)

		# The husband had no anniversary, so he takes the wife's.
		self.assertEqual(getdate(husband.anniversary), getdate(wife.anniversary))
		self.assertEqual(husband.marriage_years, 10)
		self.assertEqual(frappe.db.get_value("Person", wife.name, "marriage_years"), 10)

	def test_divorce_ends_the_marriage_on_both_sides(self):
		wife = self._make_person(first_name="Ann", last_name="Split", gender="Female")
		husband = self._make_person(
			first_name="Bob",
			last_name="Split",
			gender="Male",
			spouse=wife.name,
			marital_status="Married",
			anniversary="2001-01-01",
		)

		husband.marital_status = "Divorced"
		husband.save(ignore_permissions=True)

		self.assertIsNone(husband.spouse)
		self.assertIsNone(husband.anniversary)
		wife_values = frappe.db.get_value("Person", wife.name, ["spouse", "marital_status", "anniversary"])
		self.assertEqual(wife_values, (None, "Divorced", None))

	def test_a_widow_keeps_the_spouse_and_anniversary(self):
		wife = self._make_person(first_name="Wanda", gender="Female")
		husband = self._make_person(
			first_name="Walt",
			gender="Male",
			spouse=wife.name,
			marital_status="Married",
			anniversary="1980-05-05",
		)
		wife = frappe.get_doc("Person", wife.name)

		wife.marital_status = "Widowed"
		wife.save(ignore_permissions=True)
		husband.reload()
		husband.alergies = "Pollen"
		husband.save(ignore_permissions=True)

		self.assertEqual(wife.spouse, husband.name)
		self.assertEqual(str(wife.anniversary), "1980-05-05")
		self.assertEqual(frappe.db.get_value("Person", wife.name, "marital_status"), "Widowed")
		self.assertEqual(frappe.db.get_value("Person", husband.name, "spouse"), wife.name)

	def test_changing_spouse_unlinks_the_previous_one(self):
		first = self._make_person(first_name="First", last_name="Wife", gender="Female")
		second = self._make_person(first_name="Second", last_name="Wife", gender="Female")
		husband = self._make_person(
			first_name="Fickle", gender="Male", spouse=first.name, marital_status="Married"
		)

		husband.spouse = second.name
		husband.save(ignore_permissions=True)

		self.assertIsNone(frappe.db.get_value("Person", first.name, "spouse"))
		self.assertEqual(frappe.db.get_value("Person", second.name, "spouse"), husband.name)

	def test_deleting_a_person_unlinks_their_spouse(self):
		wife = self._make_person(first_name="Widow", gender="Female")
		husband = self._make_person(
			first_name="Late", gender="Male", spouse=wife.name, marital_status="Married"
		)

		husband.delete()

		self.assertIsNone(frappe.db.get_value("Person", wife.name, "spouse"))

	def _members(self, family_name):
		return {m.member for m in frappe.get_doc("Family", family_name).members}

	def test_marrying_without_a_family_starts_one(self):
		wife = self._make_person(first_name="Nora", last_name="Newlywed", gender="Female")
		husband = self._make_person(
			first_name="Ned", last_name="Newlywed", gender="Male", spouse=wife.name, marital_status="Married"
		)

		self.assertEqual(frappe.db.get_value("Family", husband.family, "family_name"), "Newlywed - Ned")
		self.assertTrue(husband.is_primary_contact)
		self.assertEqual(frappe.db.get_value("Person", wife.name, "family"), husband.family)
		self.assertEqual(self._members(husband.family), {husband.name, wife.name})

	def test_marrying_into_a_family_joins_it(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Joining - Jo"}).insert(
			ignore_permissions=True
		)
		wife = make_primary_contact(self._make_person(first_name="Jo", gender="Female", family=family.name))
		husband = self._make_person(
			first_name="Jim", gender="Male", spouse=wife.name, marital_status="Married"
		)

		self.assertEqual(husband.family, family.name)
		self.assertFalse(husband.is_primary_contact)
		self.assertEqual(self._members(family.name), {husband.name, wife.name})

	def test_marrying_brings_a_spouse_without_a_family_in(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Bringing - Bo"}).insert(
			ignore_permissions=True
		)
		husband = make_primary_contact(self._make_person(first_name="Bo", gender="Male", family=family.name))
		wife = self._make_person(first_name="Bea", gender="Female")
		husband.reload()
		husband.spouse = wife.name
		husband.marital_status = "Married"
		husband.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Person", wife.name, "family"), family.name)
		labels = {
			m.member: m.relationship_to_primary_contact for m in frappe.get_doc("Family", family.name).members
		}
		self.assertEqual(labels, {husband.name: "Husband", wife.name: "Wife"})

	def test_marrying_across_two_families_moves_no_one(self):
		his = frappe.get_doc({"doctype": "Family", "family_name": "His"}).insert(ignore_permissions=True)
		hers = frappe.get_doc({"doctype": "Family", "family_name": "Hers"}).insert(ignore_permissions=True)
		wife = self._make_person(first_name="Her", gender="Female", family=hers.name)
		husband = self._make_person(first_name="Him", gender="Male", family=his.name)
		husband.spouse = wife.name
		husband.marital_status = "Married"
		husband.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Person", wife.name, "family"), hers.name)
		self.assertEqual(self._members(his.name), {husband.name})

	def test_new_family_from_person_makes_them_its_primary_contact(self):
		person = self._make_person(first_name="Founder", last_name="Fam")
		person.new_family_from_person()

		person.reload()
		self.assertTrue(person.family)
		self.assertTrue(person.is_primary_contact)
		self.assertEqual(frappe.db.get_value("Family", person.family, "family_name"), "Fam - Founder")

	def test_new_family_from_person_joins_an_existing_family_of_the_same_name(self):
		existing = frappe.get_doc({"doctype": "Family", "family_name": "Twin - Joiner"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(first_name="Joiner", last_name="Twin")
		frappe.local.message_log = []
		person.new_family_from_person()

		person.reload()
		self.assertEqual(person.family, existing.name)
		self.assertFalse(person.is_primary_contact)
		messages = " ".join(str(message) for message in frappe.local.message_log)
		self.assertIn(f"/family/{existing.name}", messages)

	def test_invite_to_portal_requires_an_email_address(self):
		person = self._make_person(first_name="Unreachable")
		ensure_outgoing_email_account()
		with self.assertRaises(frappe.ValidationError):
			person.invite_to_portal()

	def test_user_dashboard_data_links_the_person_doctype(self):
		from churchit.church_people.doctype.person.person import get_user_dashboard_data

		data = get_user_dashboard_data({"transactions": []})
		self.assertIn({"label": "Church", "items": ["Person"]}, data["transactions"])
		self.assertEqual(data["non_standard_fieldnames"]["Person"], "user")

	def test_every_connection_names_a_field_that_points_at_a_person(self):
		"""A connection on a field its doctype lacks counts nothing; Frappe finds the field in a child table too."""
		for link in frappe.get_meta("Person").links:
			meta = frappe.get_meta(link.link_doctype)
			tables = [frappe.get_meta(table.options) for table in meta.get_table_fields()]
			fields = [table.get_field(link.link_fieldname) for table in (meta, *tables)]
			self.assertTrue(
				any(
					field and (field.options == "Person" or field.fieldtype == "Dynamic Link")
					for field in fields
				),
				f"{link.link_doctype}.{link.link_fieldname}",
			)


class TestPersonMembership(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for status in ("Active", "Inactive"):
			_ensure("Member Status", {"status": status}, {"status": status})
		for membership_type in ("Member", "Contact"):
			_ensure("Membership Type", {"type": membership_type}, {"type": membership_type})
		for event_type in ("Membership", "Death"):
			_ensure("Life Event Type", {"type": event_type}, {"type": event_type})
		for reason in (DECEASED, "Moved away"):
			_ensure("Inactive Reason", {"reason": reason}, {"reason": reason})

	def test_a_new_person_is_active(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Newcomer"}).insert()
		self.assertEqual(person.membership_status, "Active")

	def test_a_membership_event_makes_the_person_a_member(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Joiner"}).insert()
		person.append("life_events", {"event_type": "Membership", "date": nowdate()})
		person.save()
		self.assertEqual(person.membership, "Member")

	def test_an_existing_membership_event_leaves_a_changed_membership_alone(self):
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Former",
				"life_events": [{"event_type": "Membership", "date": "2010-01-01"}],
			}
		).insert()
		person.membership = "Contact"
		person.save()
		self.assertEqual(person.membership, "Contact")

	def test_a_death_event_widows_the_spouse(self):
		wife = frappe.get_doc(
			{"doctype": "Person", "first_name": "_Test Survivor", "gender": "Female"}
		).insert()
		husband = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Late",
				"spouse": wife.name,
				"marital_status": "Married",
			}
		).insert()

		husband.append("life_events", {"event_type": "Death", "date": nowdate()})
		husband.save()

		self.assertEqual(frappe.db.get_value("Person", wife.name, "marital_status"), "Widowed")
		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), husband.name)

	def test_a_death_event_makes_the_person_inactive(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Departed"}).insert()
		person.append("life_events", {"event_type": "Death", "date": nowdate()})
		person.save()
		self.assertEqual(person.membership_status, "Inactive")
		self.assertEqual(person.inactive_reason, DECEASED)
		self.assertEqual(getdate(person.inactive_since), getdate(nowdate()))

	def test_the_inactive_reason_goes_when_the_person_is_active_again(self):
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Returner",
				"membership_status": "Inactive",
				"inactive_reason": "Moved away",
			}
		).insert()
		person.membership_status = "Active"
		person.save()
		self.assertIsNone(person.inactive_reason)

	def test_becoming_inactive_records_the_day(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Leaver"}).insert()
		self.assertIsNone(person.inactive_since)

		person.membership_status = "Inactive"
		person.save()
		self.assertEqual(getdate(person.inactive_since), getdate(nowdate()))

		person.membership_status = "Active"
		person.save()
		self.assertIsNone(person.inactive_since)

	def test_a_person_added_as_inactive_is_dated_too(self):
		person = frappe.get_doc(
			{"doctype": "Person", "first_name": "_Test Lapsed", "membership_status": "Inactive"}
		).insert()
		self.assertEqual(getdate(person.inactive_since), getdate(nowdate()))

	def test_saving_an_inactive_person_again_keeps_the_day(self):
		person = frappe.get_doc(
			{"doctype": "Person", "first_name": "_Test Long Gone", "membership_status": "Inactive"}
		).insert()
		frappe.db.set_value("Person", person.name, "inactive_since", "2020-01-01")
		person.reload()

		person.alergies = "Pollen"
		person.save()

		self.assertEqual(getdate(person.inactive_since), getdate("2020-01-01"))


class TestInactiveSinceFromHistory(FrappeTestCase):
	"""People already Inactive take the day of the tracked change that made them so."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for status in ("Active", "Inactive"):
			_ensure("Member Status", {"status": status}, {"status": status})

	def set_status(self, person, status, day):
		"""Save *status* on *person* and date the tracked change *day*."""
		person.membership_status = status
		person.save(ignore_version=False)
		version = frappe.get_all(
			"Version",
			filters={"ref_doctype": "Person", "docname": person.name},
			order_by="creation desc",
			limit=1,
			pluck="name",
		)[0]
		frappe.db.set_value("Version", version, "creation", day)

	def test_the_latest_change_to_inactive_gives_the_day(self):
		person = frappe.get_doc({"doctype": "Person", "first_name": "_Test Wanderer"}).insert()
		self.set_status(person, "Inactive", "2020-01-01 10:00:00")
		self.set_status(person, "Active", "2021-01-01 10:00:00")
		self.set_status(person, "Inactive", "2022-03-04 10:00:00")
		frappe.db.set_value("Person", person.name, "inactive_since", None)

		set_inactive_since_from_history.execute()

		self.assertEqual(frappe.db.get_value("Person", person.name, "inactive_since"), getdate("2022-03-04"))

	def test_a_person_with_no_such_change_stays_undated(self):
		person = frappe.get_doc(
			{"doctype": "Person", "first_name": "_Test Undated", "membership_status": "Inactive"}
		).insert()
		frappe.db.set_value("Person", person.name, "inactive_since", None)

		set_inactive_since_from_history.execute()

		self.assertIsNone(frappe.db.get_value("Person", person.name, "inactive_since"))


class TestPersonSource(FrappeTestCase):
	"""How a person was first added, kept as it was."""

	def make_imported_person(self, first_name):
		frappe.flags.in_import = True
		try:
			return make_person(first_name)
		finally:
			frappe.flags.in_import = False

	def test_a_person_added_in_the_desk_comes_from_the_desk(self):
		self.assertEqual(make_person("_Test Typed In").source, "Desk")

	def test_a_data_import_marks_the_people_it_adds(self):
		self.assertEqual(self.make_imported_person("_Test Imported").source, SOURCE_IMPORT)

	def test_saving_never_changes_the_source(self):
		person = self.make_imported_person("_Test Imported Then Edited")
		person.alergies = "Pollen"
		person.save()
		self.assertEqual(frappe.db.get_value("Person", person.name, "source"), SOURCE_IMPORT)

		person.source = "Desk"
		with self.assertRaises(frappe.CannotChangeConstantError):
			person.save()

	def test_a_person_added_before_the_source_was_recorded_keeps_it_blank(self):
		person = make_person("_Test Old Timer")
		frappe.db.set_value("Person", person.name, "source", None)
		person.reload()

		person.alergies = "Pollen"
		person.save()

		self.assertIsNone(frappe.db.get_value("Person", person.name, "source"))


class TestPersonMedicalNotes(FrappeTestCase):
	"""Managers, the office and check-in volunteers read medical notes; only the first two change them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.person = make_person("_Test Patient", medical_notes="_Test Diabetic")

	def tearDown(self):
		frappe.set_user("Administrator")

	def as_role(self, role, person=None):
		"""*person* as a user holding only *role* loads them."""
		frappe.set_user(ensure_user(f"_test_medical_{frappe.scrub(role)}@example.com", role, roles=(role,)))
		return frappe.get_doc("Person", (person or self.person).name)

	def test_who_reads_the_medical_notes(self):
		for role, notes in (
			("Church Manager", "_Test Diabetic"),
			("Church People Editor", "_Test Diabetic"),
			("Church Check-In", "_Test Diabetic"),
			("Church Staff", None),
		):
			person = self.as_role(role)
			person.apply_fieldlevel_read_permissions()
			self.assertEqual(person.get("medical_notes"), notes, role)

	def test_who_changes_the_medical_notes(self):
		for role, can_change in (
			("Church Manager", True),
			("Church People Editor", True),
			("Church Check-In", False),
		):
			person = self.as_role(role)
			self.assertEqual(
				person.has_permlevel_access_to("medical_notes", permission_type="write"), can_change
			)

	def test_the_office_saves_a_change(self):
		person = self.as_role(
			"Church People Editor", make_person("_Test Insulin", medical_notes="_Test Diabetic")
		)
		person.medical_notes = "_Test Diabetic, carries insulin"
		person.save()
		self.assertEqual(
			frappe.db.get_value("Person", person.name, "medical_notes"), "_Test Diabetic, carries insulin"
		)

	def test_medical_notes_stay_out_of_the_form_timeline(self):
		"""The timeline shows a Person's Versions to every reader, and Church Staff may not read the notes."""
		person = make_person("_Test Timeline", medical_notes="_Test Diabetic")
		person.update({"first_name": "_Test Timeline Renamed", "medical_notes": "_Test Carries insulin"})
		# Saves write no Version in tests unless in_test is off.
		with patch.object(frappe, "in_test", False):
			person.save(ignore_permissions=True)
			person.medical_notes = "_Test Allergic to latex"
			person.save(ignore_permissions=True)

		frappe.set_user(
			ensure_user("_test_medical_church_staff@example.com", "Staff", roles=("Church Staff",))
		)
		getdoc("Person", person.name)
		versions = [version.data for version in frappe.response.docinfo.versions]
		frappe.set_user("Administrator")

		self.assertTrue([data for data in versions if "_Test Timeline Renamed" in data])
		self.assertFalse([data for data in versions if "medical_notes" in data])


class TestPersonChurchEmails(FrappeTestCase):
	def test_the_office_can_resubscribe_someone_who_unsubscribed(self):
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Resubscribe",
				"emails": [{"email_address": "_test_resubscribe@example.com", "is_primary": 1}],
			}
		).insert(ignore_permissions=True)
		set_subscribed("_test_resubscribe@example.com", email_church(person.church), False)
		person.run_method("onload")
		self.assertTrue(person.get_onload().has_unsubscribed)

		person.resubscribe_to_church_emails()

		self.assertFalse(has_unsubscribed(person))


class TestPersonDerivedFields(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for event_type in ("Birth", "Death"):
			_ensure("Life Event Type", {"type": event_type}, {"type": event_type})
		settings = frappe.get_single("People Settings")
		settings.adult_age = 18
		settings.save(ignore_permissions=True)

	def _make_person(self, first_name, *life_events, **values):
		return frappe.get_doc(
			{"doctype": "Person", "first_name": first_name, "life_events": list(life_events), **values}
		).insert(ignore_permissions=True)

	def _stored(self, person, *fields):
		return frappe.db.get_value("Person", person.name, fields, as_dict=True)

	def test_the_birth_event_gives_the_birth_date(self):
		person = self._make_person("_Test Born", {"event_type": "Birth", "date": "1990-05-01"})

		self.assertEqual(
			self._stored(person, "birth_date", "birth_month", "birth_day"),
			{"birth_date": getdate("1990-05-01"), "birth_month": 5, "birth_day": 1},
		)

	def test_a_birthday_without_a_year_gives_no_birth_date_or_age(self):
		person = self._make_person(
			"_Test Yearless", {"event_type": "Birth", "date": "1990-07-04", "year_unknown": 1}
		)

		self.assertEqual(
			self._stored(person, "birth_date", "birth_month", "birth_day", "age"),
			{"birth_date": None, "birth_month": 7, "birth_day": 4, "age": 0},
		)

	def test_removing_the_birth_event_clears_the_birth_fields(self):
		person = self._make_person("_Test Unborn", {"event_type": "Birth", "date": "1990-05-01"})
		person.life_events = []
		person.save()

		self.assertEqual(
			self._stored(person, "birth_date", "birth_month", "birth_day", "age"),
			{"birth_date": None, "birth_month": 0, "birth_day": 0, "age": 0},
		)

	def test_saving_someone_with_no_known_age_records_no_age_change(self):
		"""An unknown age stays 0 in memory as in the column, so a save logged a change from 0 to nothing."""
		person = self._make_person("_Test Quiet")
		person.alergies = "_Test Pollen"
		person.save(ignore_version=False)

		versions = frappe.get_all(
			"Version", filters={"ref_doctype": "Person", "docname": person.name}, pluck="data"
		)
		changed = [change[0] for data in versions for change in frappe.parse_json(data).get("changed", [])]
		self.assertIn("alergies", changed)
		self.assertNotIn("age", changed)

	def test_a_death_event_marks_the_person_deceased_and_stops_their_age(self):
		person = self._make_person("_Test Mortal", {"event_type": "Birth", "date": "1950-03-01"})
		person.append("life_events", {"event_type": "Death", "date": "2000-02-28"})
		person.save()

		self.assertEqual(
			self._stored(person, "is_deceased", "deceased_date", "age"),
			{"is_deceased": 1, "deceased_date": getdate("2000-02-28"), "age": 49},
		)

	def test_without_a_household_role_the_life_stage_follows_the_age(self):
		child = self._make_person("_Test Young", {"event_type": "Birth", "date": add_years(nowdate(), -10)})
		adult = self._make_person("_Test Grown", {"event_type": "Birth", "date": add_years(nowdate(), -18)})
		unknown = self._make_person("_Test Unknown Age")

		self.assertEqual((child.life_stage, adult.life_stage, unknown.life_stage), ("Child", "Adult", None))

	def test_the_household_role_comes_before_the_age(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Role Household"}).insert(
			ignore_permissions=True
		)
		person = self._make_person(
			"_Test Dependent", {"event_type": "Birth", "date": "1990-05-01"}, family=family.name
		)
		frappe.db.set_value(
			"Family Members", {"parent": family.name, "member": person.name}, "household_role", "Child"
		)

		person.reload()
		person.save()

		self.assertEqual(person.life_stage, "Child")


class TestPersonAcrossChurches(RollbackEachTest):
	"""Every church reads the shared directory; only a person's own church acts on them or reads their figures."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		set_private_people(False)
		cls.addClassCleanup(frappe.clear_cache)
		ensure_outgoing_email_account()
		cls.staff = {}
		for church, key in ((cls.branch_a, "a"), (cls.branch_b, "b")):
			cls.staff[key] = ensure_user(
				f"_test_across_staff_{key}@example.com",
				f"Staff {key}",
				roles=("Church Staff", "Church People Editor", "Church Finance", "Church Pastoral Care"),
			)
			set_user_church(cls.staff[key], church)

	def setUp(self):
		super().setUp()
		frappe.local.request = frappe._dict(method="POST")
		self.addCleanup(delattr, frappe.local, "request")

	def test_a_person_cannot_join_another_churchs_family(self):
		parent = make_person("_Test Across", "Parent", church=self.branch_a).name
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Across Family A", "members": [{"member": parent}]}
		).insert(ignore_permissions=True)
		family.primary_contact = parent
		family.save(ignore_permissions=True)
		joiner = make_person("_Test Across", "Joiner", church=self.branch_b).name

		frappe.set_user(self.staff["b"])
		person = frappe.get_doc("Person", joiner)
		person.family = family.name
		with self.assertRaises(frappe.PermissionError):
			person.save()
		frappe.set_user("Administrator")
		self.assertIsNone(frappe.db.get_value("Person", joiner, "family"))
		self.assertEqual([row.member for row in frappe.get_doc("Family", family.name).members], [parent])

		frappe.set_user(user_of_both_churches(self.branch_a, self.branch_b))
		person = frappe.get_doc("Person", joiner)
		person.family = family.name
		person.save()
		frappe.set_user("Administrator")
		self.assertEqual(
			[row.member for row in frappe.get_doc("Family", family.name).members], [parent, joiner]
		)

	def test_a_person_cannot_bring_another_churchs_spouse_into_their_family(self):
		spouse = make_person("_Test Across", "Spouse", church=self.branch_a).name
		head = make_person("_Test Across", "Head", church=self.branch_b).name

		frappe.set_user(self.staff["b"])
		person = frappe.get_doc("Person", head)
		person.update({"spouse": spouse, "marital_status": "Married"})
		with self.assertRaises(frappe.PermissionError):
			person.save()
		frappe.set_user("Administrator")
		self.assertIsNone(frappe.db.get_value("Person", spouse, "family"))
		self.assertIsNone(frappe.db.get_value("Person", spouse, "spouse"))

		frappe.set_user(user_of_both_churches(self.branch_a, self.branch_b))
		person = frappe.get_doc("Person", head)
		person.update({"spouse": spouse, "marital_status": "Married"})
		person.save()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Person", spouse, "family"), person.family)

	def person_in_a(self, email):
		return make_person(
			"_Test Across",
			"Churches",
			church=self.branch_a,
			emails=[{"email_address": email, "is_primary": 1}],
		).name

	def invite_as(self, user, person):
		frappe.set_user(user)
		try:
			run_doc_method("invite_to_portal", dt="Person", dn=person)
		finally:
			frappe.set_user("Administrator")

	def test_another_churchs_staff_cannot_invite_a_person_to_the_portal(self):
		email = "_test_across_invitee@example.com"
		person = self.person_in_a(email)

		with self.assertRaises(frappe.PermissionError):
			self.invite_as(self.staff["b"], person)

		self.assertFalse(frappe.db.exists("User", {"email": email}))
		self.assertIsNone(frappe.db.get_value("Person", person, "user"))

	def link_as(self, user, person, login):
		"""Set *login* as *person*'s Portal User as *user*, the way the form saves it."""
		frappe.set_user(user)
		try:
			doc = frappe.get_doc("Person", person)
			doc.user = login
			doc.save()
		finally:
			frappe.set_user("Administrator")

	def test_another_churchs_staff_cannot_link_an_existing_login(self):
		user = ensure_user("_test_across_existing@example.com", "Existing")
		set_user_church(user, self.branch_a)  # a login of branch A that no person has yet
		person = self.person_in_a(user)

		with self.assertRaises(frappe.PermissionError):
			self.invite_as(self.staff["b"], person)
		self.assertIsNone(frappe.db.get_value("Person", person, "user"))

		self.invite_as(self.staff["a"], person)
		self.assertEqual(frappe.db.get_value("Person", person, "user"), user)

	def test_another_churchs_login_is_not_linked(self):
		"""It would move the login to this church, and its owner would read this person."""
		login = ensure_user("_test_across_member_b@example.com", "Member B")
		set_user_church(login, self.branch_b)
		person = self.person_in_a(login)

		with self.assertRaises(frappe.PermissionError):
			self.link_as(self.staff["a"], person, login)
		with self.assertRaises(frappe.PermissionError):
			self.invite_as(self.staff["a"], person)

		self.assertIsNone(frappe.db.get_value("Person", person, "user"))
		self.assertEqual([p.for_value for p in user_church_permissions(login)], [self.branch_b])

	def test_a_login_another_person_has_is_not_linked_again(self):
		login = ensure_user("_test_across_taken@example.com", "Taken")
		set_user_church(login, self.branch_a)
		make_person("_Test Across", "Owner", church=self.branch_a, user=login)
		person = self.person_in_a("_test_across_second@example.com")

		with self.assertRaises(frappe.ValidationError):
			self.link_as(self.staff["a"], person, login)
		self.assertIsNone(frappe.db.get_value("Person", person, "user"))

	def test_linking_a_login_by_hand_scopes_a_member_but_never_staff(self):
		"""A staff login's churches are an administrator's to set; a link would change them silently."""
		overseer = without_church(
			ensure_user("_test_across_overseer@example.com", "Overseer", roles=("Church Manager",))
		)
		member = without_church(ensure_user("_test_across_newcomer@example.com", "Newcomer"))

		for login in (overseer, member):
			self.link_as(self.staff["a"], self.person_in_a(login), login)

		self.assertEqual(user_church_permissions(overseer), [])
		self.assertEqual([p.for_value for p in user_church_permissions(member)], [self.branch_a])

	def test_the_methods_that_change_a_person_refuse_a_get(self):
		"""A GET carries no CSRF token, so another site could start one in the user's browser."""
		person = self.person_in_a("_test_across_get@example.com")
		frappe.local.request.method = "GET"
		frappe.set_user(self.staff["a"])
		try:
			for method in ("new_family_from_person", "resubscribe_to_church_emails", "invite_to_portal"):
				with self.assertRaises(frappe.PermissionError, msg=method):
					run_doc_method(method, dt="Person", dn=person)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Person", person, ["family", "user"]), (None, None))

	def test_another_churchs_staff_cannot_start_a_family_for_a_person(self):
		"""The method saves with the caller's rights, so the person's church refuses it like a form save."""
		person = self.person_in_a("_test_across_family@example.com")
		frappe.set_user(self.staff["b"])
		try:
			with self.assertRaises(frappe.PermissionError):
				run_doc_method("new_family_from_person", dt="Person", dn=person)
		finally:
			frappe.set_user("Administrator")

		self.assertIsNone(frappe.db.get_value("Person", person, "family"))

	def test_giving_and_care_figures_show_only_to_the_persons_own_church(self):
		person = self.person_in_a("_test_across_giver@example.com")
		figures = {"last_gift_on": getdate(nowdate()), "open_care_requests": 2}
		frappe.db.set_value("Person", person, figures, update_modified=False)
		frappe.local.form_dict = frappe._dict()

		for key, expected in (("a", figures), ("b", {"last_gift_on": None, "open_care_requests": 0})):
			frappe.set_user(self.staff[key])
			getdoc("Person", person)
			reads = {
				"form": frappe.response.docs[-1].as_dict(),
				"frappe.client.get": client_get("Person", person),
				"/api/resource": read_doc("Person", person).as_dict(),
			}
			for path, doc in reads.items():
				self.assertEqual({fieldname: doc[fieldname] for fieldname in figures}, expected, (key, path))
				self.assertEqual(doc["first_name"], "_Test Across", (key, path))
			self.assertEqual(
				frappe.get_doc("Person", person).has_permlevel_access_to("last_gift_on"), key == "a"
			)


class TestNewFamilyAcrossChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_new_family_joins_only_a_family_of_the_persons_own_church(self):
		"""Another church's household of the same name is not this person's family."""
		person = make_person("_Test New Family", "Twin", church=self.branch_a)
		theirs = frappe.get_doc(
			{"doctype": "Family", "family_name": person.household_name, "church": self.branch_b}
		).insert(ignore_permissions=True)

		person.new_family_from_person()

		family = frappe.db.get_value("Person", person.name, "family")
		self.assertTrue(family)
		self.assertNotEqual(family, theirs.name)


def user_of_both_churches(church_a, church_b):
	"""A People Editor who sees *church_a* and *church_b*."""
	user = ensure_user(
		"_test_both_churches@example.com", "Both", roles=("Church Staff", "Church People Editor")
	)
	set_user_church(user, church_a)
	add_user_permission("Church", church_b, user, ignore_permissions=True, hide_descendants=1)
	return user


class TestPersonEnvelopeNumber(RollbackEachTest):
	"""An envelope number finds one giver in their church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_link_search_finds_a_person_by_envelope_number(self):
		person = make_person("_Test Envelope", "Giver", church=self.branch_a, envelope_number="90417")

		self.assertIn(person.name, [result["value"] for result in search_link("Person", "90417")])

	def test_a_number_is_unique_in_a_church(self):
		make_person("_Test Envelope", "First", church=self.branch_a, envelope_number="90418")

		with self.assertRaisesRegex(frappe.ValidationError, "90418"):
			make_person("_Test Envelope", "Second", church=self.branch_a, envelope_number="90418")
		other_church = make_person("_Test Envelope", "Other", church=self.branch_b, envelope_number="90418")
		self.assertEqual(other_church.envelope_number, "90418")

	def test_a_person_keeps_their_own_number_when_saved_again(self):
		person = make_person("_Test Envelope", "Again", church=self.branch_a, envelope_number="90419")
		person.nickname = "_Test Again"

		person.save(ignore_permissions=True)

	def test_a_merge_moves_the_number_to_the_kept_person(self):
		kept = make_person("_Test Envelope", "Kept", church=self.branch_a)
		removed = make_person("_Test Envelope", "Removed", church=self.branch_a, envelope_number="90420")

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "envelope_number"), "90420")
