# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Contact verification cards: who gets a card, what a card prints, and what a returned card changes."""

import frappe
from frappe.utils import add_days, get_datetime, getdate, now_datetime, today

from churchit.church_communications.consent import latest_statuses
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	GIVEN,
	PAPER_FORM,
	SMS,
)
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.contact_cards import (
	ANSWERED_ONLINE,
	CONFIRMED,
	STALE,
	UPDATED,
	VERIFICATION,
	get_returned_card,
	record_returned_card,
)
from churchit.church_people.derived import BIRTH, DEATH
from churchit.church_people.doctype.contact_verification.contact_verification import (
	CARD_LINK_DAYS,
	COMPLETED,
	IN_PROGRESS,
)
from churchit.church_people.privacy import anonymize
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_address,
	make_person,
	make_two_churches,
)

EDITOR_B = "_test_verification_editor_b@example.com"


def make_verification(people, **values):
	return frappe.get_doc(
		{"doctype": VERIFICATION, "title": "_Test Cards", "people": [{"person": p} for p in people], **values}
	).insert()


def contacts(**values):
	return {
		"emails": [{"email_address": "_test.cards.ann@example.com", "is_primary": 1}],
		"phones": [{"phone_number": "+1 217 555 0181", "phone_type": "Mobile", "is_primary": 1}],
		**values,
	}


class TestContactVerification(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.ann = make_person("_Test Cards", "Ann", **contacts())
		self.bob = make_person("_Test Cards", "Bob")

	def returned(self, verification, person, **changes):
		"""The card as get_returned_card gives it, with *changes*, as the dialog sends it."""
		card = get_returned_card(verification.name, person)
		card.update(changes)
		return card

	def test_a_group_adds_its_living_members_once(self):
		gone = make_person("_Test Cards", "Gone", life_events=[{"event_type": DEATH, "date": "2020-01-01"}])
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Cards Group",
				"members": [{"person": self.ann.name}, {"person": self.bob.name}, {"person": gone.name}],
			}
		).insert()
		verification = make_verification([self.ann.name], group=group.name)

		self.assertEqual([row.person for row in verification.people], [self.ann.name, self.bob.name])
		self.assertEqual((verification.card_count, verification.returned_count), (2, 0))
		self.assertEqual(verification.status, IN_PROGRESS)
		verification.save()
		self.assertEqual(len(verification.people), 2)

	def test_a_person_listed_twice_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			make_verification([self.ann.name, self.ann.name])

	def test_a_card_prints_each_value_and_blank_lines_for_what_is_missing(self):
		verification = make_verification([self.ann.name, self.bob.name], show_emergency_contact=1)
		ann, bob = verification.get_cards()

		ann_lines = {line["label"]: line for line in ann["lines"]}
		self.assertEqual(ann_lines["Email"]["value"], "_test.cards.ann@example.com")
		self.assertEqual(ann_lines["Mobile Phone"]["value"], "+1 217 555 0181")
		self.assertIsNone(ann_lines["Address"]["value"])
		self.assertEqual([add["label"] for add in ann["adds"]], ["Another email", "Another phone"])
		self.assertTrue(ann["qr_code"].startswith("data:image/svg+xml"))
		self.assertIsNone(ann["photo"])
		self.assertIn("Emergency Contact", ann_lines)
		self.assertTrue(ann["asks_texting"])
		self.assertEqual([line["value"] for line in bob["lines"]], [None] * len(bob["lines"]))

	def test_print_only_cards_not_returned(self):
		verification = make_verification([self.ann.name, self.bob.name])
		record_returned_card(verification.name, self.ann.name, self.returned(verification, self.ann.name))
		verification.reload()
		verification.print_only_not_returned = 1
		self.assertEqual([card["person"] for card in verification.get_cards()], [self.bob.name])

	def test_an_unchanged_card_is_confirmed_and_stamps_the_person(self):
		verification = make_verification([self.ann.name])
		status = record_returned_card(
			verification.name, self.ann.name, self.returned(verification, self.ann.name)
		)

		verification.reload()
		self.assertEqual(status, CONFIRMED)
		self.assertEqual(verification.people[0].returned_on, getdate(today()))
		self.assertEqual((verification.returned_count, verification.status), (1, COMPLETED))
		self.assertEqual(
			frappe.db.get_value("Person", self.ann.name, "contact_verified_on"), getdate(today())
		)

	def test_a_corrected_card_changes_the_contact_tables(self):
		verification = make_verification([self.ann.name])
		card = get_returned_card(verification.name, self.ann.name)
		card["emails"][0]["email_address"] = "_test.cards.ann.new@example.com"
		card["phones"][0]["remove"] = 1
		card["phones"].append({"phone_number": "+1 217 555 0182", "phone_type": "Home", "is_primary": 1})
		card["addresses"] = [
			{
				"address_line1": "9 Elm St",
				"city": "Port Crane",
				"state": "NY",
				"pincode": "13833",
				"country": "United States",
				"is_primary": 1,
			}
		]

		self.assertEqual(record_returned_card(verification.name, self.ann.name, card), UPDATED)
		ann = frappe.get_doc("Person", self.ann.name)
		self.assertEqual([row.email_address for row in ann.emails], ["_test.cards.ann.new@example.com"])
		self.assertEqual(
			[(row.phone_number, row.phone_type) for row in ann.phones], [("+1 217 555 0182", "Home")]
		)
		address = frappe.get_doc("Address", ann.addresses[0].address)
		self.assertEqual(
			(address.address_line1, address.city, address.pincode), ("9 Elm St", "Port Crane", "13833")
		)
		self.assertTrue(ann.addresses[0].is_primary)

	def test_a_household_address_changes_on_the_family(self):
		address = make_address("_Test Cards Household", address_line1="1 Old Rd")
		family = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": "_Test Cards Family",
				"addresses": [{"address": address.name, "is_primary": 1, "is_mailing_address": 1}],
			}
		).insert()
		self.bob.family = family.name
		self.bob.save()
		verification = make_verification([self.bob.name])
		card = get_returned_card(verification.name, self.bob.name)
		self.assertEqual(card["address_holder"], "Family")
		card["addresses"][0]["address_line1"] = "2 New Rd"

		record_returned_card(verification.name, self.bob.name, card)
		family.reload()
		self.assertEqual(
			frappe.db.get_value("Address", family.addresses[0].address, "address_line1"), "2 New Rd"
		)
		self.assertFalse(frappe.get_doc("Person", self.bob.name).addresses)

	def test_a_corrected_state_alone_gives_a_new_address(self):
		address = make_address("_Test Cards Ann Home", state="IL")
		self.ann.append("addresses", {"address": address.name, "is_primary": 1, "is_mailing_address": 1})
		self.ann.save()
		verification = make_verification([self.ann.name])
		card = get_returned_card(verification.name, self.ann.name)
		card["addresses"][0]["state"] = "NY"

		self.assertEqual(record_returned_card(verification.name, self.ann.name, card), UPDATED)
		row = frappe.get_doc("Person", self.ann.name).addresses[0]
		self.assertNotEqual(row.address, address.name)
		self.assertEqual(frappe.db.get_value("Address", row.address, "state"), "NY")
		self.assertTrue(row.is_mailing_address)

	def test_a_birthday_without_a_year_and_a_yes_to_texts(self):
		verification = make_verification([self.bob.name])
		card = self.returned(
			verification, self.bob.name, birthday="2000-03-14", birthday_year_unknown=1, texting="Yes"
		)

		record_returned_card(verification.name, self.bob.name, card)
		bob = frappe.get_doc("Person", self.bob.name)
		birth = next(row for row in bob.life_events if row.event_type == BIRTH)
		self.assertEqual((str(birth.date), birth.year_unknown), ("2000-03-14", 1))
		self.assertEqual(latest_statuses([bob.name], SMS), {bob.name: GIVEN})
		consent = frappe.get_last_doc("Communication Consent", filters={"person": bob.name})
		self.assertEqual(consent.method, PAPER_FORM)

		card = self.returned(verification, self.bob.name, texting="Yes")
		self.assertEqual(record_returned_card(verification.name, self.bob.name, card), CONFIRMED)
		self.assertEqual(frappe.db.count("Communication Consent", {"person": bob.name}), 1)

	def test_a_person_changed_since_the_card_opened_is_not_overwritten(self):
		verification = make_verification([self.ann.name])
		card = get_returned_card(verification.name, self.ann.name)
		ann = frappe.get_doc("Person", self.ann.name)
		ann.append("emails", {"email_address": "_test.cards.ann.other@example.com"})
		ann.save()

		with self.assertRaisesRegex(frappe.ValidationError, STALE.split(".")[0]):
			record_returned_card(verification.name, self.ann.name, card)

	def test_a_returned_date_in_the_future_and_a_person_not_listed_are_refused(self):
		verification = make_verification([self.ann.name])
		card = self.returned(verification, self.ann.name, returned_on=add_days(today(), 1))
		with self.assertRaises(frappe.ValidationError):
			record_returned_card(verification.name, self.ann.name, card)
		with self.assertRaises(frappe.ValidationError):
			get_returned_card(verification.name, self.bob.name)

	def test_a_card_photo_must_be_private_and_attached_to_the_verification(self):
		verification = make_verification([self.ann.name])
		public = frappe.get_doc(
			{"doctype": "File", "file_name": "_test_card.txt", "content": "card", "is_private": 0}
		).insert()
		card = self.returned(verification, self.ann.name, card_photo=public.file_url)
		with self.assertRaises(frappe.ValidationError):
			record_returned_card(verification.name, self.ann.name, card)

	def test_another_churchs_people_cannot_be_added_or_recorded(self):
		_root, branch_a, branch_b = make_two_churches()
		ensure_user(EDITOR_B, "Editor B", roles=("Church People Editor",))
		set_user_church(EDITOR_B, branch_b)
		frappe.db.set_value("Person", self.ann.name, "church", branch_a)
		with self.assertRaisesRegex(frappe.ValidationError, "another church"):
			make_verification([self.ann.name], church=branch_b)

		verification = make_verification([self.ann.name], church=branch_a)
		card = self.returned(verification, self.ann.name)
		frappe.set_user(EDITOR_B)
		with self.assertRaises(frappe.PermissionError):
			record_returned_card(verification.name, self.ann.name, card)

	def test_what_the_cards_show_is_kept_once_a_card_came_back(self):
		verification = make_verification([self.ann.name, self.bob.name])
		verification.show_anniversary = 1
		verification.save()
		record_returned_card(verification.name, self.ann.name, self.returned(verification, self.ann.name))
		verification.reload()
		verification.show_birthday = 0
		with self.assertRaisesRegex(frappe.ValidationError, "cannot change"):
			verification.save()

	def test_the_print_format_renders_a_card_for_each_person(self):
		verification = make_verification([self.ann.name, self.bob.name])
		html = frappe.get_print(VERIFICATION, verification.name, "Contact Verification Cards")
		self.assertEqual(html.count("Is your information correct?"), 2)
		self.assertIn("_test.cards.ann@example.com", html)
		self.assertIn("Cut here", html)

	def test_contact_verified_on_never_moves_back(self):
		verification = make_verification([self.ann.name])
		record_returned_card(verification.name, self.ann.name, self.returned(verification, self.ann.name))
		earlier = add_days(today(), -10)
		card = self.returned(verification, self.ann.name, returned_on=earlier)
		record_returned_card(verification.name, self.ann.name, card)
		self.assertEqual(
			frappe.db.get_value("Person", self.ann.name, "contact_verified_on"), getdate(today())
		)

	def test_a_value_of_the_household_is_shared_and_another_persons_is_refused(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Cards Family"}).insert()
		for person in (self.ann, self.bob):
			person.reload()
			person.family = family.name
			person.save()
		verification = make_verification([self.bob.name])
		card = get_returned_card(verification.name, self.bob.name)
		card["emails"] = [{"email_address": "_test.cards.ann@example.com", "is_primary": 1}]
		record_returned_card(verification.name, self.bob.name, card)
		self.assertEqual(frappe.get_doc("Person", self.bob.name).emails[0].shared_from, self.ann.name)

		carl = make_person("_Test Cards", "Carl")
		verification = make_verification([carl.name])
		card = get_returned_card(verification.name, carl.name)
		card["emails"] = [{"email_address": "_test.cards.ann@example.com", "is_primary": 1}]
		with self.assertRaises(frappe.ValidationError):
			record_returned_card(verification.name, carl.name, card)

	def test_anonymizing_deletes_the_photo_of_the_persons_card(self):
		verification = make_verification([self.ann.name])
		photo = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "_test_card.txt",
				"content": "card",
				"is_private": 1,
				"attached_to_doctype": VERIFICATION,
				"attached_to_name": verification.name,
			}
		).insert()
		card = self.returned(verification, self.ann.name, card_photo=photo.file_url)
		record_returned_card(verification.name, self.ann.name, card)

		anonymize(self.ann.name)
		self.assertFalse(frappe.db.exists("File", photo.name))
		self.assertIsNone(frappe.get_doc(VERIFICATION, verification.name).people[0].card_photo)

	def test_each_card_not_returned_gets_a_link_that_ends_after_handed_out_on(self):
		verification = make_verification([self.ann.name, self.bob.name], handed_out_on="2026-01-05")
		requests = [row.details_request for row in verification.people]
		self.assertTrue(all(requests))
		ends = frappe.db.get_value("Web Form Request", requests[0], "expires_on")
		self.assertEqual(get_datetime(ends), get_datetime(add_days("2026-01-05", CARD_LINK_DAYS)))
		self.assertTrue(all(card["online_qr_code"] is None for card in verification.get_cards()))

		verification.handed_out_on = today()
		verification.save()
		self.assertEqual([row.details_request for row in verification.people], requests)
		self.assertTrue(all(card["online_qr_code"] for card in verification.get_cards()))

		verification.show_online_link = 0
		verification.save()
		ends = frappe.db.get_value("Web Form Request", requests[0], "expires_on")
		self.assertLessEqual(get_datetime(ends), now_datetime())

	def test_using_the_link_marks_the_card_answered_online(self):
		verification = make_verification([self.ann.name, self.bob.name])
		request = frappe.get_doc("Web Form Request", verification.people[0].details_request)

		frappe.set_user("Guest")
		request.first_used_on = now_datetime()
		request.save(ignore_permissions=True)
		frappe.set_user("Administrator")

		verification.reload()
		self.assertEqual(verification.people[0].status, ANSWERED_ONLINE)
		self.assertEqual(verification.returned_count, 1)
		self.assertEqual(
			frappe.db.get_value("Person", self.ann.name, "contact_verified_on"), getdate(today())
		)
		self.assertIsNone(verification.get_cards()[0]["online_qr_code"])
