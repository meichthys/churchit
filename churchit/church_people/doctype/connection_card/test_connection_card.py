# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import patch

import frappe
from frappe.utils import add_years, getdate, today
from frappe.website.doctype.web_form.web_form import accept

from churchit.church_communications.consent import allowed
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.church_people.doctype.connection_card.connection_card import (
	CONNECTION_CARD,
	NEW,
	PROCESSED,
	SPAM,
)
from churchit.church_people.doctype.connection_card_interest.connection_card_interest import STARTER_INTERESTS
from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.matching import is_paired
from churchit.church_people.membership import VISITOR
from churchit.church_people.privacy import anonymize
from churchit.church_people.test_accounts import share_in_the_directory_by_default
from churchit.patches.v1_0 import add_connection_card_interests
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

WEB_FORM = "connection-card"


class ConnectionCardTestCase(RollbackEachTest):
	def setUp(self):
		super().setUp()
		# A card queues its processing after the commit a test never makes; tests call process() themselves.
		enqueue = patch("frappe.enqueue_doc")
		self.enqueue_doc = enqueue.start()
		self.addCleanup(enqueue.stop)
		frappe.db.set_single_value("People Settings", "match_threshold", 80)

	def send(self, **values):
		"""Send the web form as a guest and return the card it made."""
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)
		frappe.local.form_dict = frappe._dict()
		frappe.set_user("Guest")
		try:
			data = {"first_name": "_Test Card", "last_name": "Guest", **values}
			return frappe.get_doc("Connection Card", accept(WEB_FORM, json.dumps(data)).name)
		finally:
			frappe.set_user("Administrator")

	def make_card(self, **values):
		return frappe.get_doc(
			{"doctype": "Connection Card", "first_name": "_Test Card", "last_name": "Guest", **values}
		).insert(ignore_permissions=True)

	def processed(self, card):
		card.process()
		return frappe.get_doc("Connection Card", card.name)


class TestConnectionCardWebForm(ConnectionCardTestCase):
	def test_a_guest_sends_a_new_card_and_its_processing_is_queued(self):
		interest = ensure("Connection Card Interest", {"interest": "_Test Card Baptism"})

		card = self.send(email="_test_card_guest@example.com", interests=[{"interest": interest}])

		self.assertEqual((card.status, card.owner, card.person), (NEW, "Guest", None))
		self.assertEqual([row.interest for row in card.interests], [interest])
		self.assertEqual(self.enqueue_doc.call_args.args, ("Connection Card", card.name, "process"))
		self.assertTrue(self.enqueue_doc.call_args.kwargs["enqueue_after_commit"])

	def test_a_filled_honeypot_is_kept_as_spam_and_adds_no_one(self):
		card = self.send(first_name="_Test Card Robot", website="https://spam.example.com")
		self.assertEqual(card.status, NEW, "the sender is not told")

		card = self.processed(card)

		self.assertEqual((card.status, card.person), (SPAM, None))
		self.assertFalse(frappe.db.exists("Person", {"first_name": "_Test Card Robot"}))

	def test_a_single_church_site_keeps_no_church_from_the_address(self):
		force_single_church()
		self.assertFalse(self.send(church=ensure_root_church()).church)


class TestConnectionCardChurch(ConnectionCardTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user("_test_card_manager_a@example.com", "CardA", roles=("Church Manager",))
		make_person("_Test Card", "Manager A", church=cls.branch_a, user=cls.manager_a)

	def test_a_published_church_from_the_address_is_kept(self):
		frappe.db.set_value("Church", self.branch_b, "publish", 1)
		self.assertEqual(self.send(church=self.branch_b).church, self.branch_b)

	def test_a_church_that_is_not_published_is_ignored(self):
		frappe.db.set_value("Church", self.branch_a, "publish", 0)
		self.assertEqual(self.send(church=self.branch_a).church, self.root)

	def test_cards_are_scoped_to_their_church(self):
		mine = self.make_card(church=self.branch_a).name
		theirs = self.make_card(church=self.branch_b).name
		assert_scoped(self, "Connection Card", self.manager_a, mine, theirs)

	def test_a_card_matches_only_its_own_churchs_people(self):
		elsewhere = make_person(
			"_Test Card",
			"Elsewhere",
			church=self.branch_b,
			emails=[{"email_address": "_test_card_elsewhere@example.com"}],
		)
		card = self.processed(
			self.make_card(
				church=self.branch_a, last_name="Elsewhere", email="_test_card_elsewhere@example.com"
			)
		)

		self.assertNotEqual(card.person, elsewhere.name)
		self.assertEqual(frappe.db.get_value("Person", card.person, "church"), self.branch_a)


class TestConnectionCardProcessing(ConnectionCardTestCase):
	def test_a_strong_match_is_linked_and_never_changed(self):
		known = make_person("_Test Card", "Known", emails=[{"email_address": "_test_card_known@example.com"}])
		modified = frappe.db.get_value("Person", known.name, "modified")

		card = self.processed(
			self.make_card(last_name="Known", email="_test_card_known@example.com", phone="+1 555 010 4477")
		)

		self.assertEqual((card.status, card.person), (PROCESSED, known.name))
		self.assertTrue(card.processed_on)
		self.assertEqual(frappe.db.get_value("Person", known.name, "modified"), modified)
		self.assertFalse(frappe.get_doc("Person", known.name).phones)

	def test_a_weaker_match_adds_a_visitor_and_leaves_the_match_for_staff(self):
		known = make_person(
			"_Test Card", "Initial", emails=[{"email_address": "_test_card_initial@example.com"}]
		)
		# A shared email and the first initial reach the threshold, but the first name is not the same.
		card = self.processed(
			self.make_card(first_name="T", last_name="Initial", email="_test_card_initial@example.com")
		)

		self.assertNotEqual(card.person, known.name)
		person = frappe.get_doc("Person", card.person)
		self.assertEqual((person.membership, person.source), (VISITOR, CONNECTION_CARD))
		self.assertEqual(
			[(row.email_address, row.shared_from) for row in person.emails],
			[("_test_card_initial@example.com", known.name)],
		)
		self.assertTrue(is_paired(known.name, person.name))

	def test_two_strong_matches_add_a_new_person_rather_than_pick_one(self):
		by_email = make_person(
			"_Test Card", "Twice", emails=[{"email_address": "_test_card_twice@example.com"}]
		)
		by_phone = make_person("_Test Card", "Twice", phones=[{"phone_number": "+1 555 010 4478"}])

		card = self.processed(
			self.make_card(last_name="Twice", email="_test_card_twice@example.com", phone="+1 555 010 4478")
		)

		self.assertNotIn(card.person, (by_email.name, by_phone.name))
		self.assertTrue(is_paired(by_email.name, card.person))
		self.assertTrue(is_paired(by_phone.name, card.person))

	def test_a_new_visitor_keeps_how_they_heard(self):
		card = self.processed(self.make_card(last_name="Heard", how_heard="_Test A friend"))

		self.assertEqual(frappe.db.get_value("Person", card.person, "how_heard"), "_Test A friend")

	def test_a_strong_match_keeps_how_they_heard_first(self):
		known = make_person(
			"_Test Card",
			"Heard Before",
			how_heard="_Test The radio",
			emails=[{"email_address": "_test_card_heard@example.com"}],
		)

		card = self.processed(
			self.make_card(
				last_name="Heard Before", email="_test_card_heard@example.com", how_heard="_Test A friend"
			)
		)

		self.assertEqual(card.person, known.name)
		self.assertEqual(frappe.db.get_value("Person", known.name, "how_heard"), "_Test The radio")

	def test_a_card_is_processed_once(self):
		card = self.make_card(last_name="Once", email="_test_card_once@example.com")
		card.process()
		card.process()
		self.assertEqual(frappe.db.count("Person", {"last_name": "Once", "first_name": "_Test Card"}), 1)

	def test_anonymizing_the_person_deletes_their_cards(self):
		card = self.processed(self.make_card(last_name="Forgotten"))
		anonymize(card.person)
		self.assertFalse(frappe.db.exists("Connection Card", card.name))


class TestConnectionCardFollowUp(ConnectionCardTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.baptism = ensure("Connection Card Interest", {"interest": "_Test Card Baptism"})
		cls.serving = ensure("Connection Card Interest", {"interest": "_Test Card Serving"})
		cls.any_card = cls.make_workflow("_Test Card Welcome", None)
		cls.baptism_workflow = cls.make_workflow("_Test Card Baptism Class", cls.baptism)
		cls.serving_workflow = cls.make_workflow("_Test Card Serving Team", cls.serving)

	@staticmethod
	def make_workflow(name, interest):
		return (
			frappe.get_doc(
				{
					"doctype": "Follow-up Workflow",
					"workflow_name": name,
					"steps": [{"step": "Call"}],
					"triggers": [{"trigger": CONNECTION_CARD, "value": interest}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def started(self, card):
		cards = frappe.get_all(
			"Follow-up Card",
			filters={"person": card.person, "source_type": "Connection Card", "source_name": card.name},
			pluck="workflow",
		)
		return sorted(set(cards) & {self.any_card, self.baptism_workflow, self.serving_workflow})

	def test_a_card_starts_the_workflows_of_each_interest(self):
		card = self.processed(self.make_card(last_name="Baptism", interests=[{"interest": self.baptism}]))
		self.assertEqual(self.started(card), sorted((self.any_card, self.baptism_workflow)))

	def test_a_card_with_no_interests_starts_the_workflows_for_any_card(self):
		card = self.processed(self.make_card(last_name="Nothing Ticked"))
		self.assertEqual(self.started(card), [self.any_card])

	def test_a_guests_card_is_processed_as_the_guest(self):
		"""The job runs as whoever queued it, which is Guest for the web form."""
		card = self.send(last_name="Sent", interests=[{"interest": self.serving}])

		frappe.set_user("Guest")
		card = self.processed(card)
		frappe.set_user("Administrator")

		self.assertEqual(card.status, PROCESSED)
		self.assertEqual(self.started(card), sorted((self.any_card, self.serving_workflow)))

	def test_spam_starts_nothing(self):
		card = self.processed(self.make_card(last_name="Spam", website="https://spam.example.com"))
		self.assertFalse(frappe.db.exists("Follow-up Card", {"source_name": card.name}))


class TestConnectionCardConsent(ConnectionCardTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_communication_purposes()

	@staticmethod
	def consents(person):
		return frappe.get_all(
			"Communication Consent",
			filters={"person": person},
			fields=["channel", "purpose", "status", "method"],
			order_by="channel asc",
		)

	def test_ticked_boxes_record_church_news_by_email_and_by_text(self):
		card = self.processed(
			self.make_card(
				last_name="Ticked",
				email="_test_card_ticked@example.com",
				phone="+1 555 010 4480",
				email_consent=1,
				sms_consent=1,
			)
		)

		self.assertEqual(
			self.consents(card.person),
			[
				{"channel": EMAIL, "purpose": CHURCH_NEWS, "status": GIVEN, "method": "Web Form"},
				{"channel": SMS, "purpose": CHURCH_NEWS, "status": GIVEN, "method": "Web Form"},
			],
		)
		self.assertTrue(allowed(card.person, SMS, CHURCH_NEWS))

	def test_a_guests_ticked_box_is_recorded_as_the_guest(self):
		card = self.send(last_name="Online", email="_test_card_online@example.com", email_consent=1)

		frappe.set_user("Guest")
		card = self.processed(card)
		frappe.set_user("Administrator")

		self.assertEqual([row.channel for row in self.consents(card.person)], [EMAIL])

	def test_unticked_boxes_record_nothing(self):
		card = self.processed(
			self.make_card(
				last_name="Unticked", email="_test_card_unticked@example.com", phone="+1 555 010 4481"
			)
		)
		self.assertEqual(self.consents(card.person), [])

	def test_a_box_with_no_address_or_number_beside_it_records_nothing(self):
		card = self.processed(self.make_card(last_name="Blank", email_consent=1, sms_consent=1))
		self.assertEqual(self.consents(card.person), [])

	def test_spam_records_nothing(self):
		card = self.processed(
			self.make_card(
				last_name="Spam Consent",
				email="_test_card_spam@example.com",
				email_consent=1,
				website="https://spam.example.com",
			)
		)
		self.assertFalse(frappe.db.exists("Communication Consent", {"person": card.person}))

	def test_a_match_on_email_records_a_tick_only_for_what_the_person_holds(self):
		known = make_person(
			"_Test Card",
			"Known Number",
			emails=[{"email_address": "_test_card_known_number@example.com"}],
			phones=[{"phone_number": "(555) 010-4483"}],
		)

		card = self.processed(
			self.make_card(
				last_name="Known Number",
				email="_TEST_CARD_KNOWN_NUMBER@example.com",
				phone="+1 555 010 9999",
				email_consent=1,
				sms_consent=1,
			)
		)

		self.assertEqual(card.person, known.name)
		self.assertEqual([row.channel for row in self.consents(known.name)], [EMAIL])

	def test_a_number_on_the_persons_record_is_found_however_it_was_typed(self):
		known = make_person("_Test Card", "Same Number", phones=[{"phone_number": "(555) 010-4484"}])

		card = self.processed(self.make_card(last_name="Same Number", phone="555.010.4484", sms_consent=1))

		self.assertEqual(card.person, known.name)
		self.assertEqual([row.channel for row in self.consents(known.name)], [SMS])

	def test_a_tick_never_overrides_a_withdrawal(self):
		known = make_person("_Test Card", "Stopped", phones=[{"phone_number": "+1 555 010 4482"}])
		record([known.name], SMS, WITHDRAWN)

		card = self.processed(self.make_card(last_name="Stopped", phone="+1 555 010 4482", sms_consent=1))

		self.assertEqual(card.person, known.name)
		self.assertFalse(allowed(known.name, SMS, CHURCH_NEWS))
		self.assertEqual([row.status for row in self.consents(known.name)], [WITHDRAWN])


class TestConnectionCardHousehold(ConnectionCardTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Life Event Type", {"type": "Birth"})
		for relationship in ("Wife", "Son"):
			ensure("Person Relation Type", {"type": relationship})
		cls.child_birth_date = add_years(today(), -8)

	def household(self):
		return [
			{"first_name": "Jane", "relationship": "Wife", "birth_date": "1985-04-02"},
			{"first_name": "Sam", "relationship": "Son", "birth_date": self.child_birth_date},
			{"first_name": "Pat", "last_name": "_Test Card Lodger"},
		]

	def members(self, family):
		"""The family's members as {first name: (last name, relationship, household role)}."""
		rows = frappe.get_doc("Family", family).members
		people = {
			row.name: row
			for row in frappe.get_all(
				"Person",
				filters={"name": ("in", [row.member for row in rows])},
				fields=["name", "first_name", "last_name"],
			)
		}
		return {
			people[row.member].first_name: (
				people[row.member].last_name,
				row.relationship_to_primary_contact,
				row.household_role,
			)
			for row in rows
		}

	def test_a_new_guest_and_the_people_with_them_become_one_family(self):
		card = self.processed(self.make_card(last_name="Household", household_members=self.household()))

		guest = frappe.get_doc("Person", card.person)
		family = frappe.get_doc("Family", guest.family)
		self.assertEqual(family.primary_contact, guest.name)
		self.assertEqual(
			self.members(family.name),
			{
				"_Test Card": ("Household", None, "Adult"),
				"Jane": ("Household", "Wife", "Adult"),
				"Sam": ("Household", "Son", "Child"),
				"Pat": ("_Test Card Lodger", None, None),
			},
		)
		jane = frappe.get_doc("Person", {"family": family.name, "first_name": "Jane"})
		self.assertEqual(
			(jane.spouse, jane.gender, jane.membership, jane.source),
			(guest.name, "Female", VISITOR, CONNECTION_CARD),
		)
		sam = frappe.get_doc("Person", {"family": family.name, "first_name": "Sam"})
		self.assertEqual(getdate(sam.birth_date), getdate(self.child_birth_date))

	def test_the_people_a_card_adds_share_nothing_in_the_directory(self):
		"""A guest never saw the choice, whatever People Settings gives a new person."""
		share_in_the_directory_by_default(self)

		card = self.processed(self.make_card(last_name="Private", household_members=self.household()))

		family = frappe.db.get_value("Person", card.person, "family")
		shared = frappe.get_all("Person", filters={"family": family}, fields=list(SHARE_DEFAULTS))
		self.assertEqual(shared, [dict.fromkeys(SHARE_DEFAULTS, 0)] * 4)

	def test_a_card_that_matched_someone_adds_no_one_with_them(self):
		known = make_person(
			"_Test Card", "Regular", emails=[{"email_address": "_test_card_regular@example.com"}]
		)

		card = self.processed(
			self.make_card(
				last_name="Regular",
				email="_test_card_regular@example.com",
				household_members=self.household(),
			)
		)

		self.assertEqual(card.person, known.name)
		self.assertEqual(len(card.household_members), 3, "the rows stay on the card for staff")
		self.assertFalse(frappe.db.exists("Person", {"first_name": "Sam", "last_name": "Regular"}))
		self.assertFalse(frappe.db.get_value("Person", known.name, "family"))

	def test_spam_adds_no_one_with_it(self):
		self.processed(
			self.make_card(
				last_name="Spam Household",
				website="https://spam.example.com",
				household_members=self.household(),
			)
		)
		self.assertFalse(frappe.db.exists("Person", {"last_name": "Spam Household"}))

	def test_someone_with_the_guest_is_paired_with_who_they_may_be(self):
		known = make_person(
			"Sam",
			"Paired",
			life_events=[{"event_type": "Birth", "date": self.child_birth_date}],
		)

		card = self.processed(self.make_card(last_name="Paired", household_members=self.household()))

		sam = frappe.db.get_value(
			"Person", {"first_name": "Sam", "last_name": "Paired", "name": ("!=", known.name)}
		)
		self.assertNotEqual(card.person, known.name)
		self.assertTrue(is_paired(sam, known.name))

	def test_a_guest_sends_the_people_with_them_and_the_job_adds_them_as_the_guest(self):
		card = self.send(last_name="Sent Household", household_members=self.household())
		self.assertEqual(
			[(row.first_name, row.relationship) for row in card.household_members],
			[("Jane", "Wife"), ("Sam", "Son"), ("Pat", None)],
		)

		frappe.set_user("Guest")
		card = self.processed(card)
		frappe.set_user("Administrator")

		family = frappe.db.get_value("Person", card.person, "family")
		self.assertEqual(len(frappe.get_doc("Family", family).members), 4)


class TestConnectionCardInterests(RollbackEachTest):
	def test_the_seed_patch_is_safe_to_run_twice(self):
		add_connection_card_interests.execute()
		add_connection_card_interests.execute()

		names = [interest for interest, _description in STARTER_INTERESTS]
		self.assertEqual(frappe.db.count("Connection Card Interest", {"name": ("in", names)}), len(names))
