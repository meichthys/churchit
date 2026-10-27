# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.handler import execute_cmd
from frappe.model.rename_doc import update_document_title
from frappe.tests.classes.context_managers import patch_hooks
from frappe.utils import CallbackManager

from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import CARD, CLOSED, OPEN, add_card
from churchit.church_people.matching import MERGED, Match, get_pairs, record_possible_duplicates
from churchit.church_people.merge import merge_families, merge_people
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_primary_contact,
	make_two_churches,
)


def email(address, **values):
	return {"email_address": address, "email_type": ensure("Email Type", {"type": "Home"}), **values}


def phone(number, **values):
	return {"phone_number": number, "phone_type": ensure("Phone Type", {"type": "Mobile"}), **values}


def life_event(event_type, date=None):
	return {"event_type": ensure("Life Event Type", {"type": event_type}), "date": date}


def make_family(family_name, *people, **values):
	family = frappe.get_doc(
		{
			"doctype": "Family",
			"family_name": family_name,
			"members": [{"member": p.name} for p in people],
			**values,
		}
	).insert(ignore_permissions=True)
	return family


def merge_in_rename_dialog(doctype):
	"""Merge as the desk Rename dialog's "Merge with existing" does."""

	def rename_dialog(keep, remove):
		update_document_title(doctype=doctype, docname=remove, name=keep, merge=True)

	return rename_dialog


def merge_and_commit(merge, keep, remove):
	"""Run *merge*, then the callbacks its commit would run, leaving the test's transaction open."""
	pending, frappe.db.before_commit = frappe.db.before_commit, CallbackManager()
	try:
		merge(keep, remove)
		frappe.db.before_commit.run()
	finally:
		frappe.db.before_commit = pending


def make_older_deleted_copy(doctype, name):
	"""A Deleted Document from an earlier record that had the name *name*, as a reverted series reuses names."""
	copy = frappe.get_doc(
		doctype="Deleted Document",
		deleted_doctype=doctype,
		deleted_name=name,
		data="{}",
		creation="2020-01-01",
	)
	copy.db_insert()
	return copy.name


def deleted_copies(doctype, name):
	return frappe.get_all(
		"Deleted Document", filters={"deleted_doctype": doctype, "deleted_name": name}, pluck="name"
	)


class TestMergePeople(RollbackEachTest):
	def test_the_kept_values_win_and_blank_fields_are_filled(self):
		kept = make_person("_Test Kept", "Merge", nickname="Kit", gender="Unknown")
		removed = make_person(
			"_Test Removed", "Merge", nickname="Remy", middle_name="Quinn", gender="Female", alergies="Kiwi"
		)

		merge_people(kept.name, removed.name)

		kept.reload()
		self.assertEqual((kept.first_name, kept.nickname), ("_Test Kept", "Kit"))
		self.assertEqual((kept.middle_name, kept.gender, kept.alergies), ("Quinn", "Female", "Kiwi"))
		self.assertFalse(frappe.db.exists("Person", removed.name))

	def test_neither_way_of_merging_leaves_the_removed_person_in_deleted_documents(self):
		"""The copy keeps their personal data, and restoring it brings back a record nothing links to."""
		for way in (merge_people, merge_in_rename_dialog("Person")):
			kept = make_person("_Test Kept", "Forgotten")
			removed = make_person("_Test Removed", "Forgotten", medical_notes="_Test Asthma")
			older_copy = make_older_deleted_copy("Person", removed.name)

			merge_and_commit(way, kept.name, removed.name)

			self.assertEqual(deleted_copies("Person", removed.name), [older_copy], way)

	def test_contact_rows_and_life_events_are_combined_once_with_one_primary(self):
		removed = make_person(
			"_Test Removed",
			"Contacts",
			emails=[email("_TEST.SHARED@example.com"), email("_test.removed@example.com", is_primary=1)],
			phones=[phone("(555) 010-0001")],
			life_events=[life_event("Baptism", "2001-04-01"), life_event("Birth", "1980-02-03")],
		)
		kept = make_person(
			"_Test Kept",
			"Contacts",
			emails=[
				email("_test.kept@example.com"),
				email("_test.shared@example.com", shared_from_type="Person", shared_from=removed.name),
			],
			phones=[phone("555-010-0001", shared_from_type="Person", shared_from=removed.name)],
			life_events=[life_event("Baptism", "2001-04-01")],
		)

		merge_people(kept.name, removed.name)

		kept.reload()
		self.assertEqual(
			[(row.email_address, row.is_primary, row.shared_from) for row in kept.emails],
			[
				("_test.kept@example.com", 1, None),
				("_test.shared@example.com", 0, None),
				("_test.removed@example.com", 0, None),
			],
		)
		self.assertEqual(
			[(row.phone_number, row.shared_from) for row in kept.phones], [("555-010-0001", None)]
		)
		self.assertEqual(sorted(row.event_type for row in kept.life_events), ["Baptism", "Birth"])
		self.assertEqual(str(kept.birth_date), "1980-02-03")

	def test_records_about_the_removed_person_move_to_the_kept_one(self):
		kept = make_person("_Test Kept", "Records")
		removed = make_person("_Test Removed", "Records", membership_status="Inactive")
		check = frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": removed.name,
				"check_type": ensure("Background Check Type", {"type": "_Test Check"}),
				"status": "Cleared",
				"requested_on": "2026-01-01",
				"completed_on": "2026-01-15",
			}
		).insert(ignore_permissions=True)

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Background Check", check.name, "person"), kept.name)
		self.assertTrue(
			frappe.db.exists(
				"Milestone",
				{"reference_type": "Person", "reference_name": kept.name, "value": "Inactive"},
			)
		)
		self.assertEqual(frappe.db.get_value("Person", kept.name, "background_check_status"), "Cleared")

	def test_a_roster_names_the_kept_person_once(self):
		kept = make_person("_Test Kept", "Roster")
		removed = make_person("_Test Removed", "Roster")
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Merge Group",
				"members": [
					{"person": kept.name},
					{"person": removed.name, "group_role": ensure("Group Role", {"role": "_Test Leader"})},
				],
			}
		).insert(ignore_permissions=True)
		checked_in = ensure("Function Attendance Type", {"type": "Checked-In"})
		function = make_function(
			"_Test Merge Service",
			start_date=frappe.utils.today(),
			attendance=[
				{"person": removed.name, "attendance_type": checked_in},
				{"person": kept.name, "attendance_type": checked_in},
			],
		)

		merge_people(kept.name, removed.name)

		group.reload()
		self.assertEqual(
			[(row.person, row.group_role) for row in group.members], [(kept.name, "_Test Leader")]
		)
		function.reload()
		self.assertEqual([row.person for row in function.attendance], [kept.name])
		self.assertEqual(function.attendance_total, 1)

	def test_the_kept_person_stays_in_their_own_family_only(self):
		kept = make_person("_Test Kept", "Household")
		removed = make_person("_Test Removed", "Household")
		child = make_person("_Test Child", "Household")
		kept_family = make_family("_Test Kept Household", kept)
		removed_family = make_family("_Test Removed Household", removed, child)
		make_primary_contact(removed.reload())

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "family"), kept_family.name)
		self.assertEqual([row.member for row in kept_family.reload().members], [kept.name])
		removed_family.reload()
		self.assertEqual([row.member for row in removed_family.members], [child.name])
		self.assertFalse(removed_family.primary_contact)

	def test_a_person_without_a_family_takes_the_removed_persons(self):
		kept = make_person("_Test Kept", "Joiner")
		removed = make_person("_Test Removed", "Joiner")
		family = make_family("_Test Joined Household", removed)
		make_primary_contact(removed.reload())

		merge_people(kept.name, removed.name)

		family.reload()
		self.assertEqual(frappe.db.get_value("Person", kept.name, "family"), family.name)
		self.assertEqual(
			([row.member for row in family.members], family.primary_contact), ([kept.name], kept.name)
		)

	def test_the_spouse_comes_with_the_marriage(self):
		kept = make_person("_Test Kept", "Spouse")
		removed = make_person("_Test Removed", "Spouse")
		wife = make_person("_Test Wife", "Spouse", spouse=removed.name, marital_status="Married")

		merge_people(kept.name, removed.name)

		self.assertEqual(
			frappe.db.get_value("Person", kept.name, ["spouse", "marital_status"]), (wife.name, "Married")
		)
		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), kept.name)

	def test_the_portal_user_moves_to_a_kept_person_without_one(self):
		user = ensure_user("_test_merge_member@example.com", "Member")
		kept = make_person("_Test Kept", "Login")
		removed = make_person("_Test Removed", "Login", user=user)

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "user"), user)

	def test_the_calendar_key_moves_without_a_version(self):
		kept = make_person("_Test Kept", "Calendar")
		removed = make_person("_Test Removed", "Calendar")
		frappe.db.set_value("Person", removed.name, "team_calendar_key", "_test_merged_key")

		# Saves write no Version in tests unless in_test is off.
		with patch.object(frappe, "in_test", False):
			merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "team_calendar_key"), "_test_merged_key")
		versions = frappe.get_all(
			"Version", filters={"ref_doctype": "Person", "docname": kept.name}, pluck="data"
		)
		self.assertFalse([data for data in versions if "_test_merged_key" in data])

	def test_two_people_with_portal_users_are_not_merged(self):
		kept = make_person("_Test Kept", "Logins", user=ensure_user("_test_merge_one@example.com", "One"))
		removed = make_person(
			"_Test Removed", "Logins", user=ensure_user("_test_merge_two@example.com", "Two")
		)

		self.assertRaises(frappe.ValidationError, merge_people, kept.name, removed.name)
		self.assertTrue(frappe.db.exists("Person", removed.name))

	def test_people_married_to_others_are_not_merged(self):
		kept = make_person("_Test Kept", "Spouses")
		removed = make_person("_Test Removed", "Spouses")
		make_person("_Test Her", "Spouses", spouse=kept.name, marital_status="Married")
		make_person("_Test Him", "Spouses", spouse=removed.name, marital_status="Married")

		self.assertRaises(frappe.ValidationError, merge_people, kept.name, removed.name)

	def test_people_of_two_churches_are_not_merged(self):
		_root, branch_a, branch_b = make_two_churches()
		kept = make_person("_Test Kept", "Churches", church=branch_a)
		removed = make_person("_Test Removed", "Churches", church=branch_b)

		self.assertRaises(frappe.ValidationError, merge_people, kept.name, removed.name)

	def test_the_rename_dialog_merges_by_the_same_rules(self):
		kept = make_person("_Test Kept", "Dialog")
		removed = make_person("_Test Removed", "Dialog", middle_name="Dee")

		update_document_title(doctype="Person", docname=removed.name, name=kept.name, merge=True)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "middle_name"), "Dee")
		self.assertRaises(
			frappe.ValidationError,
			update_document_title,
			doctype="Person",
			docname=kept.name,
			name="_Test New ID",
		)

	def test_a_merge_refuses_a_get(self):
		"""A GET carries no CSRF token, so another site could start a merge in the user's browser."""
		people = make_person("_Test Kept", "Get").name, make_person("_Test Removed", "Get").name
		families = make_family("_Test Kept Get Family").name, make_family("_Test Removed Get Family").name
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

		for method, (keep, remove) in (("merge_people", people), ("merge_families", families)):
			frappe.local.form_dict = frappe._dict(keep=keep, remove=remove)
			with self.assertRaises(frappe.PermissionError, msg=method):
				execute_cmd(f"churchit.church_people.merge.{method}")

		self.assertTrue(frappe.db.exists("Person", people[1]))
		self.assertTrue(frappe.db.exists("Family", families[1]))

	def test_a_person_is_never_just_renamed(self):
		person = make_person("_Test Renamed", "Person")

		self.assertRaises(frappe.ValidationError, frappe.rename_doc, "Person", person.name, "_Test New ID")

	def test_a_merge_needs_the_right_to_delete(self):
		kept = make_person("_Test Kept", "Rights")
		removed = make_person("_Test Removed", "Rights")
		frappe.set_user(ensure_user("_test_merge_editor@example.com", "Editor", ["Church People Editor"]))

		self.assertRaises(frappe.PermissionError, merge_people, kept.name, removed.name)

	def test_the_possible_duplicate_closes(self):
		kept = make_person("_Test Kept", "Pair")
		removed = make_person("_Test Removed", "Pair")
		(pair,) = record_possible_duplicates(kept.name, [Match(removed.name, 90)])

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Possible Duplicate", pair, "status"), MERGED)
		self.assertEqual([row.name for row in get_pairs(kept.name)], [pair])

	def test_one_follow_up_card_stays_open_per_workflow(self):
		kept = make_person("_Test Kept", "Followed")
		removed = make_person("_Test Removed", "Followed")
		workflow = make_workflow("_Test Merge Welcome", [("Call", None, 2)]).name
		first = add_card(kept.name, workflow)
		second = add_card(removed.name, workflow)

		merge_people(kept.name, removed.name)

		self.assertEqual(
			frappe.get_all(CARD, filters={"person": kept.name, "status": OPEN}, pluck="name"), [first]
		)
		self.assertEqual(frappe.db.get_value(CARD, second, ["person", "status"]), (kept.name, CLOSED))

	def test_the_pair_survives_the_hook_that_drops_a_deleted_persons_pairs(self):
		kept = make_person("_Test Kept", "Hooked")
		removed = make_person("_Test Removed", "Hooked")
		(pair,) = record_possible_duplicates(kept.name, [Match(removed.name, 90)])
		doc_events = {
			**frappe.get_hooks("doc_events"),
			"Person": {"on_trash": "churchit.church_people.duplicates.drop_pairs"},
		}

		with patch_hooks({"doc_events": doc_events}):
			frappe.local.doc_events_hooks = None
			self.addCleanup(setattr, frappe.local, "doc_events_hooks", None)
			merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Possible Duplicate", pair, "status"), MERGED)

	def test_the_imported_id_moves_to_a_person_without_one(self):
		kept = make_person("_Test Kept", "Imported")
		removed = make_person("_Test Removed", "Imported", legacy_system="_Test System", legacy_id="7")

		merge_people(kept.name, removed.name)

		self.assertEqual(
			frappe.db.get_value("Person", kept.name, ["legacy_system", "legacy_id"]), ("_Test System", "7")
		)

	def test_an_imported_id_that_cannot_move_is_noted_on_the_kept_person(self):
		kept = make_person("_Test Kept", "Imported", legacy_system="_Test System", legacy_id="7")
		removed = make_person("_Test Removed", "Imported", legacy_system="_Test System", legacy_id="8")

		merge_people(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", kept.name, "legacy_id"), "7")
		notes = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Person", "reference_name": kept.name, "comment_type": "Info"},
			pluck="content",
		)
		self.assertTrue(any("<strong>8</strong>" in note and "_Test System" in note for note in notes), notes)

	def test_a_failed_merge_leaves_both_people_untouched(self):
		kept = make_person("_Test Kept", "Failed")
		removed = make_person(
			"_Test Removed", "Failed", middle_name="Lee", emails=[email("_test.failed@example.com")]
		)
		wife = make_person("_Test Wife", "Failed", spouse=removed.name, marital_status="Married")

		with patch("churchit.church_people.matching.resolve_merged", side_effect=frappe.ValidationError):
			self.assertRaises(frappe.ValidationError, merge_people, kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), removed.name)
		self.assertFalse(frappe.db.get_value("Person", kept.name, "middle_name"))
		self.assertEqual(
			[row.email_address for row in frappe.get_doc("Person", removed.name).emails],
			["_test.failed@example.com"],
		)


class TestMergeFamilies(RollbackEachTest):
	def test_members_and_contact_rows_move_to_the_kept_family(self):
		head = make_person("_Test Head", "Families", gender="Male")
		other_head = make_person("_Test Other Head", "Families", gender="Male")
		child = make_person("_Test Child", "Families")
		kept = make_family("_Test Kept Family", head, emails=[email("_test.home@example.com")])
		removed = make_family(
			"_Test Removed Family",
			other_head,
			child,
			emails=[
				email("_test.home@example.com", shared_from_type="Family", shared_from=kept.name),
				email("_test.other@example.com"),
			],
		)
		make_primary_contact(head.reload())
		make_primary_contact(other_head.reload())
		frappe.db.set_value(
			"Family Members",
			{"parent": removed.name, "member": child.name},
			{
				"relationship_to_primary_contact": ensure("Person Relation Type", {"type": "Son"}),
				"household_role": "Child",
			},
		)

		merge_families(kept.name, removed.name)

		kept.reload()
		self.assertEqual(
			[(row.member, row.relationship_to_primary_contact, row.household_role) for row in kept.members],
			[(head.name, None, "Adult"), (other_head.name, None, "Adult"), (child.name, None, "Child")],
		)
		self.assertEqual(
			[row.email_address for row in kept.emails], ["_test.home@example.com", "_test.other@example.com"]
		)
		self.assertEqual(frappe.db.get_value("Person", child.name, "family"), kept.name)
		self.assertFalse(frappe.db.exists("Family", removed.name))

	def test_neither_way_of_merging_leaves_the_removed_family_in_deleted_documents(self):
		for way in (merge_families, merge_in_rename_dialog("Family")):
			kept = make_family("_Test Kept Family")
			removed = make_family("_Test Forgotten Family")

			merge_and_commit(way, kept.name, removed.name)

			self.assertEqual(deleted_copies("Family", removed.name), [], way)

	def test_a_family_without_a_primary_contact_takes_the_removed_ones(self):
		head = make_person("_Test Head", "Contactless")
		kept = make_family("_Test Contactless Family")
		removed = make_family("_Test Headed Family", head)
		make_primary_contact(head.reload())

		merge_families(kept.name, removed.name)

		self.assertEqual(frappe.db.get_value("Family", kept.name, "primary_contact"), head.name)

	def test_a_family_is_never_just_renamed(self):
		family = make_family("_Test Renamed Family")

		self.assertRaises(frappe.ValidationError, frappe.rename_doc, "Family", family.name, "_Test New ID")

	def test_the_rename_dialog_still_changes_a_familys_name(self):
		family = make_family("_Test Renamed Family")

		update_document_title(doctype="Family", docname=family.name, name=family.name, title="_Test Retitled")

		self.assertEqual(frappe.db.get_value("Family", family.name, "family_name"), "_Test Retitled")


class TestMergeSkills(RollbackEachTest):
	def test_the_kept_person_has_each_skill_of_both_once(self):
		teaching, mercy, giving = (
			ensure("Skill", {"skill_name": name})
			for name in ("_Test Teaching", "_Test Mercy", "_Test Giving")
		)
		kept = make_person("_Test Kept", "Skills", skills=[{"skill": teaching}, {"skill": giving}])
		removed = make_person("_Test Removed", "Skills", skills=[{"skill": teaching}, {"skill": mercy}])

		merge_people(kept.name, removed.name)

		kept.reload()
		self.assertEqual([row.skill for row in kept.skills], [teaching, giving, mercy])
		self.assertFalse(frappe.db.exists("Person Skill", {"parent": removed.name}))
