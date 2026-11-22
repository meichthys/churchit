# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member directory in the app: the living people of the member's church who do not hide, with only
what each one shares."""

import frappe

from churchit.church_people.derived import BIRTH
from churchit.church_people.directory import get_vcard
from churchit.portal.directory import get_directory
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_address,
	make_person,
	make_primary_contact,
	make_two_churches,
)

ROBERT_EMAIL = "_test_directory_robert@example.com"
MARY_EMAIL = "_test_directory_mary@example.com"
ROBERT_PHONE = "555 010 0101"
MARY_PHONE = "555 010 0102"
JOHNSONS = "_Test Johnson, Robert & Mary"


def born(date, year_unknown=0):
	return [{"event_type": BIRTH, "date": date, "year_unknown": year_unknown}]


def make_sharer(*args, **values):
	"""make_person sharing only what *values* say, whatever People Settings gives new people."""
	shares = {f"share_{detail}": 0 for detail in ("email", "phone", "address", "birthday")}
	return make_person(*args, **{**shares, **values})


class TestPortalDirectory(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, church, other_church = make_two_churches()
		frappe.db.set_single_value("People Settings", "member_directory", 1)
		cls.member = ensure_user("_test_portal_dir_member@example.com", "Member")
		make_person("_Test Dir", "Member", church=church, user=cls.member, share_email=0)
		make_person("_Test Dir", "Neighbour", church=church, share_email=0)
		make_person("_Test Dir", "Stranger", church=other_church)
		cls.visitor = ensure_user("_test_portal_dir_visitor@example.com", "Visitor")
		make_person("_Test Dir", "Visitor", church=church, user=cls.visitor, membership="Visitor")
		cls.loner = ensure_user("_test_portal_dir_loner@example.com", "Loner")

	def titles(self):
		return [entry["title"] for entry in get_directory()["entries"]]

	def test_a_member_sees_their_own_church_only(self):
		frappe.set_user(self.member)
		titles = self.titles()

		self.assertIn("Neighbour, _Test Dir", titles)
		self.assertNotIn("Stranger, _Test Dir", titles)
		self.assertEqual(get_directory()["status"], "ok")

	def test_an_entry_carries_no_person_id(self):
		frappe.set_user(self.member)
		entry = get_directory()["entries"][0]

		self.assertEqual(
			set(entry),
			{"name", "title", "photo", "emails", "phones", "addresses", "birthdays", "vcard", "search"},
		)

	def test_a_visitor_is_told_they_are_not_a_member(self):
		frappe.set_user(self.visitor)

		self.assertEqual(get_directory(), {"status": "not_member", "entries": []})

	def test_a_login_without_a_person_is_refused(self):
		frappe.set_user(self.loner)

		with self.assertRaises(frappe.PermissionError):
			get_directory()

	def test_a_guest_is_refused(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			get_directory()

	def test_the_directory_is_not_found_until_it_is_on(self):
		frappe.db.set_single_value("People Settings", "member_directory", 0)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.DoesNotExistError):
			get_directory()

	def test_a_page_switched_off_is_refused(self):
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": "directory"})[0].enabled = 0
		features.save()
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			get_directory()


class TestDirectoryEntries(RollbackEachTest):
	"""In one church: the member, the Johnsons, David Thompson, someone hidden and someone who died. A stranger
	belongs to another church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Life Event Type", {"type": BIRTH})
		_root, church, other_church = make_two_churches()
		frappe.db.set_single_value("People Settings", "member_directory", 1)
		cls.church = church
		cls.user = ensure_user("_test_directory_member@example.com", "Member")
		make_sharer("_Test Directory", "Member", church=church, user=cls.user)

		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Johnson - Robert"})
		family.insert(ignore_permissions=True)
		mary = make_sharer(
			"Mary",
			"_Test Johnson",
			church=church,
			family=family.name,
			photo="/files/_test_directory_mary.png",
			emails=[{"email_address": MARY_EMAIL}],
			phones=[{"phone_number": MARY_PHONE}],
			life_events=born("1982-06-09"),
			share_phone=1,
			share_address=1,
			share_birthday=1,
		)
		make_primary_contact(
			make_sharer(
				"Robert",
				"_Test Johnson",
				church=church,
				family=family.name,
				photo="/private/files/_test_directory_robert.png",
				emails=[{"email_address": ROBERT_EMAIL}],
				phones=[{"phone_number": ROBERT_PHONE}],
				life_events=born("1980-03-03"),
				share_email=1,
				share_birthday=1,
			)
		)
		address = make_address("_Test Directory Home", address_line1="12 Elm Street")
		family.reload()
		family.append("addresses", {"address": address.name, "is_mailing_address": 1})
		family.save(ignore_permissions=True)
		cls.mary = mary.name

		make_sharer(
			"David",
			"_Test Thompson",
			church=church,
			life_events=born("1900-07-04", year_unknown=1),
			share_birthday=1,
		)
		make_sharer("_Test Hidden", "Person", church=church, hide_from_directory=1, share_email=1)
		late = make_sharer("_Test Late", "Person", church=church, share_email=1)
		frappe.db.set_value("Person", late.name, "is_deceased", 1)
		make_sharer("_Test Stranger", "Person", church=other_church, share_email=1)
		make_sharer("_Test Guest", "Person", church=church, membership="Visitor", share_email=1)
		make_sharer("_Test Moved", "Away", church=church, membership_status="Inactive", share_email=1)

	def setUp(self):
		super().setUp()
		frappe.set_user(self.user)

	def entries(self):
		return {entry["title"]: entry for entry in get_directory()["entries"]}

	def view_as(self, key, **values):
		"""Sign in as a new user whose Person in the member's church has *values*."""
		frappe.set_user("Administrator")
		user = ensure_user(f"_test_directory_{key}@example.com", "_Test Viewer")
		make_sharer("_Test Viewer", key.title(), church=self.church, user=user, **values)
		frappe.set_user(user)

	def test_it_lists_the_living_people_of_the_members_church_who_do_not_hide(self):
		self.assertEqual(list(self.entries()), [JOHNSONS, "_Test Thompson, David", "Member, _Test Directory"])

	def test_a_family_is_one_entry_with_only_what_each_person_shares(self):
		johnsons = self.entries()[JOHNSONS]

		self.assertEqual(johnsons["emails"], [ROBERT_EMAIL])
		self.assertEqual(johnsons["phones"], [MARY_PHONE])
		self.assertEqual(johnsons["addresses"], ["12 Elm Street, Springfield"])
		self.assertEqual(johnsons["birthdays"], ["Robert Mar 3", "Mary Jun 9"])

	def test_nothing_a_person_keeps_to_themselves_is_sent(self):
		sent = frappe.as_json(get_directory())

		self.assertIn(ROBERT_EMAIL, sent)
		for kept in (MARY_EMAIL, ROBERT_PHONE, "_Test Hidden", "_Test Late", "_Test Stranger"):
			self.assertNotIn(kept, sent)

	def test_someone_who_shares_nothing_shows_by_name_only(self):
		member = self.entries()["Member, _Test Directory"]

		self.assertEqual(
			(member["emails"], member["phones"], member["addresses"], member["birthdays"]), ([], [], [], [])
		)

	def test_a_birthday_shows_its_day_and_month_even_when_the_year_is_unknown(self):
		self.assertEqual(self.entries()["_Test Thompson, David"]["birthdays"], ["David Jul 4"])

	def test_a_private_photo_gives_way_to_one_every_member_may_see(self):
		self.assertEqual(self.entries()[JOHNSONS]["photo"], "/files/_test_directory_mary.png")

		frappe.db.set_value("Person", self.mary, "photo", "/private/files/_test_directory_mary.png")
		self.assertIsNone(self.entries()[JOHNSONS]["photo"])

	def test_a_visitor_a_contact_or_someone_inactive_sees_no_one(self):
		"""Every Website User gets a Visitor Person on first sign-in, so signing up alone must not open the directory."""
		ensure("Membership Type", {"type": "Contact"})
		for key, values in (
			("visitor", {"membership": "Visitor"}),
			("contact", {"membership": "Contact"}),
			("inactive", {"membership_status": "Inactive"}),
		):
			self.view_as(key, **values)

			self.assertEqual(get_directory(), {"status": "not_member", "entries": []}, key)

	def test_a_member_who_hides_from_the_directory_still_sees_it(self):
		self.view_as("hider", hide_from_directory=1)

		self.assertIn(JOHNSONS, self.entries())

	def test_a_vcard_holds_only_the_email_phone_and_address_its_entry_shows(self):
		self.assertEqual(
			self.entries()[JOHNSONS]["vcard"],
			"BEGIN:VCARD\r\n"
			"VERSION:3.0\r\n"
			"N:_Test Johnson\\, Robert & Mary;;;;\r\n"
			"FN:_Test Johnson\\, Robert & Mary\r\n"
			f"EMAIL;TYPE=INTERNET:{ROBERT_EMAIL}\r\n"
			f"TEL:{MARY_PHONE}\r\n"
			"ADR:;;12 Elm Street\\, Springfield;;;;\r\n"
			"END:VCARD\r\n",
		)

	def test_an_entry_that_shares_no_phone_has_no_tel_line(self):
		vcard = self.entries()["Member, _Test Directory"]["vcard"]

		self.assertIn("FN:Member\\, _Test Directory\r\n", vcard)
		for kept in ("TEL", "EMAIL", "ADR"):
			self.assertNotIn(kept, vcard)

	def test_a_semicolon_and_a_backslash_in_a_title_are_escaped(self):
		self.assertIn("FN:Smith\\; Jones\\\\Lee\r\n", get_vcard("Smith; Jones\\Lee", [], [], []))

	def test_a_line_break_in_a_value_cannot_start_a_line(self):
		vcard = get_vcard("Lee\r\nTEL:1", [], [], ["1 Elm\nEND:VCARD"])

		properties = [line.split(":")[0] for line in vcard.split("\r\n") if line]
		self.assertEqual(properties, ["BEGIN", "VERSION", "N", "FN", "ADR", "END"])
		self.assertIn("ADR:;;1 Elm\\nEND:VCARD;;;;\r\n", vcard)
