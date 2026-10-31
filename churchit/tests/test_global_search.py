# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The search bar (Ctrl+K) finds churchit's records by title, and only the ones the reader may open.

The search table keeps its rows through a rollback, so each test deletes the rows it left.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.global_search import search, sync_global_search

from churchit.church_people.privacy import PERSONAL_DOCTYPES, RECORDS_ABOUT_THE_PERSON, anonymize
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.church_people.test_merge import make_family
from churchit.patches.v1_0 import add_churchit_to_global_search
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_person,
	make_two_churches,
	set_private_people,
)

SEARCHED_DOCTYPES = add_churchit_to_global_search.get_searched_doctypes()
# Records about one person's care, prayer or history, which the search bar never shows.
SENSITIVE_DOCTYPES = {
	"Prayer",
	*(doctype for doctype, _field in PERSONAL_DOCTYPES + RECORDS_ABOUT_THE_PERSON),
}
SURNAME = "Zebulonquix"


def found(text: str) -> set[tuple[str, str]]:
	"""The (doctype, name) of each search bar result for *text* that the current user may open."""
	return {(row.doctype, row.name) for row in search(text)}


def forget_search_rows(word: str, *records) -> None:
	"""Delete the search rows holding *word* or naming one of *records*, once the queued rows are written."""
	sync_global_search()
	frappe.db.delete("__global_search", {"content": ("like", f"%{word}%")})
	for doc in records:
		frappe.db.delete("__global_search", {"doctype": doc.doctype, "name": doc.name})


def allow_searched_doctypes(case) -> None:
	"""List the searched doctypes in Global Search Settings for the class of *case*, whatever the site holds."""
	add_churchit_to_global_search.execute()
	case.addClassCleanup(frappe.cache.hdel, "global_search", "search_priorities")


def churchit_doctypes() -> list[str]:
	return frappe.get_all(
		"DocType", filters={"module": ("in", frappe.get_module_list("churchit"))}, pluck="name"
	)


class TestSearchedFields(FrappeTestCase):
	def test_the_hook_lists_every_doctype_with_a_searched_field(self):
		searched = {
			doctype for doctype in churchit_doctypes() if frappe.get_meta(doctype).get_global_search_fields()
		}

		self.assertEqual(searched, set(SEARCHED_DOCTYPES))

	def test_only_the_title_field_is_searched_and_never_one_of_a_higher_level(self):
		for doctype in churchit_doctypes():
			meta = frappe.get_meta(doctype)
			for field in meta.get_global_search_fields():
				self.assertEqual(field.fieldname, meta.title_field, f"{doctype} searches {field.fieldname}")
				self.assertFalse(
					field.permlevel, f"{doctype} searches {field.fieldname} of level {field.permlevel}"
				)

	def test_no_record_about_one_persons_care_prayer_or_history_is_searched(self):
		for doctype in SENSITIVE_DOCTYPES:
			self.assertFalse(frappe.get_meta(doctype).get_global_search_fields(), doctype)


class TestAddChurchitToGlobalSearch(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.cache.hdel, "global_search", "search_priorities")

	def set_listed(self, *doctypes: str) -> None:
		settings = frappe.get_single("Global Search Settings")
		settings.allowed_in_global_search = []
		for doctype in doctypes:
			settings.append("allowed_in_global_search", {"document_type": doctype})
		settings.save()

	def get_listed(self) -> list[str]:
		settings = frappe.get_single("Global Search Settings")
		return [row.document_type for row in settings.allowed_in_global_search]

	def test_the_missing_doctypes_go_first_and_their_records_are_indexed(self):
		self.addCleanup(forget_search_rows, SURNAME)
		self.set_listed("Web Page", "Group", "Contact")
		# A save only queues its search row, and the queue is written every 15 minutes.
		group = frappe.get_doc({"doctype": "Group", "group_name": f"{SURNAME} Choir"}).insert(
			ignore_permissions=True
		)
		self.assertNotIn(("Group", group.name), found(SURNAME))

		add_churchit_to_global_search.execute()
		add_churchit_to_global_search.execute()

		missing = [doctype for doctype in SEARCHED_DOCTYPES if doctype != "Group"]
		self.assertEqual(self.get_listed(), [*missing, "Web Page", "Group", "Contact"])
		self.assertIn(("Group", group.name), found(SURNAME))

	def test_a_later_addition_keeps_the_rows_the_site_took_out(self):
		self.set_listed("Person", "Group", "Contact")

		add_churchit_to_global_search.add_to_global_search(["Belief"])

		self.assertEqual(self.get_listed(), ["Person", "Group", "Belief", "Contact"])

	def test_a_row_of_an_uninstalled_apps_doctype_is_dropped(self):
		self.set_listed("Contact")
		# Uninstalling an app leaves its rows, which the settings refuse on save.
		frappe.get_doc(
			{
				"doctype": "Global Search DocType",
				"parent": "Global Search Settings",
				"parenttype": "Global Search Settings",
				"parentfield": "allowed_in_global_search",
				"idx": 2,
				"document_type": "Uninstalled App Record",
			}
		).db_insert()
		self.assertEqual(self.get_listed(), ["Contact", "Uninstalled App Record"])

		add_churchit_to_global_search.execute()

		self.assertEqual(self.get_listed(), [*SEARCHED_DOCTYPES, "Contact"])


class TestSearchFollowsReadPermission(FrappeTestCase):
	"""Branch managers in A and B, and two households of the main church, one with a portal login."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		allow_searched_doctypes(cls)
		cls.addClassCleanup(forget_search_rows, SURNAME)
		_root, branch_a, branch_b = make_two_churches()
		cls.manager_b = ensure_user(
			"_test_search_manager_b@example.com", "SearchB", roles=("Church Manager",)
		)
		make_person("SearchB", SURNAME, church=branch_b, user=cls.manager_b)
		cls.person_a = make_person("Alpha", SURNAME, church=branch_a).name
		cls.person_b = make_person("Bravo", SURNAME, church=branch_b).name
		cls.family_a = make_family(f"{SURNAME} Alpha", church=branch_a).name
		set_adult_age(18)
		cls.family, cls.father, _mother, cls.son, _grandmother = make_household(f"{SURNAME} - John", SURNAME)
		cls.member = link_user(cls.father, "_test_search_member@example.com")
		make_household(f"{SURNAME} - Next Door", SURNAME)
		sync_global_search()

	def tearDown(self):
		frappe.set_user("Administrator")

	def assert_finds_what_the_list_shows(self, user):
		frappe.set_user(user)
		listed = {
			("Person", name)
			for name in frappe.get_list("Person", filters={"last_name": SURNAME}, pluck="name")
		}
		families = frappe.get_list("Family", filters={"family_name": ("like", f"%{SURNAME}%")}, pluck="name")
		listed |= {("Family", name) for name in families}

		self.assertEqual(found(SURNAME), listed)
		return listed

	def test_an_open_directory_finds_every_churchs_people_as_the_list_does(self):
		set_private_people(False)

		results = self.assert_finds_what_the_list_shows(self.manager_b)

		self.assertTrue({("Person", self.person_a), ("Person", self.person_b)} <= results)

	def test_a_private_directory_hides_another_churchs_people_and_families(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		results = self.assert_finds_what_the_list_shows(self.manager_b)

		self.assertIn(("Person", self.person_b), results)
		self.assertNotIn(("Person", self.person_a), results)
		self.assertNotIn(("Family", self.family_a), results)

	def test_a_portal_member_finds_only_their_own_household(self):
		results = self.assert_finds_what_the_list_shows(self.member)

		self.assertEqual(results, {("Person", self.father), ("Person", self.son), ("Family", self.family)})


class TestRemovePersonalData(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		allow_searched_doctypes(cls)

	def test_the_search_bar_stops_finding_the_removed_name(self):
		first_name, sermon_word = "Ezekielqua", "Psalmquest"
		person = make_person(first_name, SURNAME)
		wife = make_person("Adaqua", SURNAME)
		family = make_family(f"{SURNAME} - {first_name}", person, wife)
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": f"{first_name} {SURNAME} {sermon_word}",
				"prepared_by": person.name,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(forget_search_rows, SURNAME, person, wife, family, sermon)
		sync_global_search()
		self.assertEqual(
			found(first_name), {("Person", person.name), ("Family", family.name), ("Sermon", sermon.name)}
		)

		anonymize(person.name)

		self.assertEqual(found(first_name), set())
		sync_global_search()
		self.assertEqual(found(first_name), set())
		self.assertEqual(found(sermon_word), {("Sermon", sermon.name)})
		self.assertEqual(found(SURNAME), {("Person", wife.name), ("Family", family.name)})
