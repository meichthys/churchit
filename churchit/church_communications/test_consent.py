# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from churchit.church_communications import newsletter
from churchit.church_communications.consent import (
	allowed,
	allowed_people,
	consent_renewal_link,
	refused_values,
	renew,
)
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	EMAIL_LINK,
	GIVEN,
	PHONE,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.patches.v1_0 import date_future_consent_when_entered, record_consent_from_unsubscribes
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	force_single_church,
	make_person,
	make_two_churches,
)
from churchit.tests.test_notification_templates import shipped_templates

SHARED_EMAIL = "_test_consent_shared@example.com"


def consents(person, **filters):
	return frappe.get_all(
		"Communication Consent",
		filters={"person": person, **filters},
		fields=["status", "purpose", "method"],
		order_by="recorded_on asc, creation asc",
	)


def make_household(case):
	"""Two people on one address: the second shares it from the first."""
	owner = make_person(case, "Owner", emails=[{"email_address": SHARED_EMAIL}])
	sharer = make_person(
		case,
		"Sharer",
		emails=[{"email_address": SHARED_EMAIL, "shared_from": owner.name, "shared_from_type": "Person"}],
	)
	return owner, sharer


def insert_unsubscribe(**values):
	return frappe.get_doc({"doctype": "Email Unsubscribe", "email": SHARED_EMAIL, **values}).insert(
		ignore_permissions=True
	)


class TestAllowed(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		create_communication_purposes()
		ensure("Life Event Type", {"type": "Death"})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Consent", "Person")

	def test_people_may_be_contacted_until_they_withdraw(self):
		self.assertTrue(allowed(self.person.name, EMAIL))
		record([self.person.name], EMAIL, WITHDRAWN)
		self.assertFalse(allowed(self.person.name, EMAIL))
		self.assertFalse(allowed(self.person.name, EMAIL, CHURCH_NEWS))
		self.assertTrue(allowed(self.person.name, PHONE))

	def test_nobody_who_has_died_is_contacted(self):
		departed = make_person(
			"_Test Consent", "Departed", life_events=[{"event_type": "Death", "date": "2024-01-01"}]
		)
		record([departed.name], EMAIL, GIVEN)
		self.assertFalse(allowed(departed.name, EMAIL))

	def test_a_church_that_asks_first_contacts_only_people_who_agreed(self):
		frappe.db.set_value("Church", self.church, "contact_only_with_consent", 1)
		self.assertFalse(allowed(self.person.name, EMAIL))

		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS)
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))
		self.assertFalse(allowed(self.person.name, EMAIL, PASTORAL_CARE))

	def test_the_newest_record_decides_whatever_order_it_was_entered_in(self):
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on="2025-06-01 10:00:00")
		record([self.person.name], EMAIL, GIVEN, recorded_on="2024-06-01 10:00:00")
		self.assertFalse(allowed(self.person.name, EMAIL))

		record([self.person.name], EMAIL, GIVEN, recorded_on="2026-06-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL))

	def test_a_newer_record_for_one_purpose_beats_an_older_one_for_every_purpose(self):
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on="2024-01-01 10:00:00")
		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS, recorded_on="2025-01-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))
		self.assertFalse(allowed(self.person.name, EMAIL, PASTORAL_CARE))
		self.assertFalse(allowed(self.person.name, EMAIL))

		record([self.person.name], EMAIL, GIVEN, recorded_on="2026-01-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL, PASTORAL_CARE))

	def test_a_yes_for_every_purpose_never_undoes_a_no_for_one_purpose(self):
		record([self.person.name], EMAIL, WITHDRAWN, CHURCH_NEWS, recorded_on="2024-01-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL), "One purpose says nothing about the rest")

		record([self.person.name], EMAIL, GIVEN, recorded_on="2025-01-01 10:00:00")
		self.assertFalse(allowed(self.person.name, EMAIL, CHURCH_NEWS))
		self.assertTrue(allowed(self.person.name, EMAIL, PASTORAL_CARE))

		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS, recorded_on="2026-01-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))

	def test_a_no_for_every_purpose_undoes_every_yes_before_it(self):
		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS, recorded_on="2024-01-01 10:00:00")
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on="2025-01-01 10:00:00")
		self.assertFalse(allowed(self.person.name, EMAIL, CHURCH_NEWS))

		record([self.person.name], EMAIL, GIVEN, recorded_on="2026-01-01 10:00:00")
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))

	def test_at_the_same_moment_the_later_entry_wins(self):
		moment = "2025-03-01 09:00:00"
		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS, recorded_on=moment)
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on=moment)
		self.assertFalse(allowed(self.person.name, EMAIL, CHURCH_NEWS))

		later = "2025-04-01 09:00:00"
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on=later)
		record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS, recorded_on=later)
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))

	def test_a_recorded_on_in_the_future_is_refused(self):
		soon = add_to_date(now_datetime(), minutes=2)
		record([self.person.name], EMAIL, WITHDRAWN, recorded_on=soon)

		consent = frappe.get_doc(
			{
				"doctype": "Communication Consent",
				"person": self.person.name,
				"channel": EMAIL,
				"status": GIVEN,
				"recorded_on": "2062-01-01 10:00:00",
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "future"):
			consent.insert()
		self.assertFalse(allowed(self.person.name, EMAIL))

	def test_the_patch_dates_a_future_consent_when_it_was_entered(self):
		(future,) = record([self.person.name], EMAIL, GIVEN)
		frappe.db.set_value("Communication Consent", future, "recorded_on", "2062-01-01 10:00:00")
		record([self.person.name], EMAIL, WITHDRAWN)
		self.assertTrue(allowed(self.person.name, EMAIL))

		date_future_consent_when_entered.execute()

		self.assertEqual(
			frappe.db.get_value("Communication Consent", future, "recorded_on"),
			frappe.db.get_value("Communication Consent", future, "creation"),
		)
		self.assertFalse(allowed(self.person.name, EMAIL))

	def test_many_people_are_answered_at_once(self):
		withdrawn = make_person("_Test Consent", "Withdrawn")
		record([withdrawn.name], EMAIL, WITHDRAWN)
		people = [self.person.name, withdrawn.name, "_Test No Such Person"]
		self.assertEqual(allowed_people(people, EMAIL), {self.person.name})

	def test_a_shared_address_is_refused_only_when_everyone_holding_it_is(self):
		owner, sharer = make_household("_Test Refused")
		record([owner.name], EMAIL, WITHDRAWN)
		self.assertEqual(refused_values([SHARED_EMAIL, "_test_nobody@example.com"], EMAIL), set())

		record([sharer.name], EMAIL, WITHDRAWN)
		self.assertEqual(refused_values([SHARED_EMAIL.upper()], EMAIL), {SHARED_EMAIL.upper()})

	def test_texts_go_only_to_people_who_agreed(self):
		self.assertTrue(allowed(self.person.name, EMAIL))
		self.assertFalse(allowed(self.person.name, SMS))
		record([self.person.name], SMS, GIVEN)
		self.assertTrue(allowed(self.person.name, SMS, CHURCH_NEWS))

	def test_a_phone_number_is_matched_on_its_digits(self):
		texted = make_person("_Test Consent", "Texted", phones=[{"phone_number": "(555) 010-0199"}])
		record([texted.name], SMS, WITHDRAWN)
		self.assertEqual(refused_values(["555 010 0199"], SMS), {"555 010 0199"})


class TestUnsubscribes(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		create_communication_purposes()

	def setUp(self):
		super().setUp()
		self.owner, self.sharer = make_household("_Test Unsubscribe")

	def test_a_global_unsubscribe_withdraws_every_purpose_from_everyone_on_the_address(self):
		insert_unsubscribe(global_unsubscribe=1)
		for person in (self.owner, self.sharer):
			self.assertEqual(
				consents(person.name), [{"status": WITHDRAWN, "purpose": None, "method": "Unsubscribe Link"}]
			)
			self.assertFalse(allowed(person.name, EMAIL, PASTORAL_CARE))
			self.assertTrue(allowed(person.name, PHONE))

	def test_a_church_unsubscribe_withdraws_church_news_from_everyone_on_the_address(self):
		newsletter.set_subscribed(SHARED_EMAIL, self.church, False)
		for person in (self.owner, self.sharer):
			self.assertEqual([row.purpose for row in consents(person.name, status=WITHDRAWN)], [CHURCH_NEWS])
			self.assertFalse(allowed(person.name, EMAIL, CHURCH_NEWS))
			self.assertTrue(allowed(person.name, EMAIL, PASTORAL_CARE))

	def test_the_link_in_a_church_email_records_how_the_person_stopped(self):
		frappe.set_user("Guest")
		with mock.patch.object(frappe.db, "commit"):
			newsletter.unsubscribe(email=SHARED_EMAIL, church=self.church, doctype="Church Email", name="x")
		frappe.set_user("Administrator")
		self.assertEqual(consents(self.owner.name)[0].method, "Unsubscribe Link")

	def test_leaving_one_conversation_records_no_consent(self):
		insert_unsubscribe(reference_doctype="Person", reference_name=self.owner.name)
		self.assertEqual(consents(self.owner.name), [])

	def test_the_office_resubscribing_someone_records_their_consent_alone(self):
		newsletter.set_subscribed(SHARED_EMAIL, self.church, False)
		newsletter.resubscribe(self.sharer)

		self.assertEqual(
			consents(self.sharer.name)[-1], {"status": GIVEN, "purpose": CHURCH_NEWS, "method": "Desk"}
		)
		self.assertTrue(allowed(self.sharer.name, EMAIL, CHURCH_NEWS))
		self.assertFalse(allowed(self.owner.name, EMAIL, CHURCH_NEWS))

	def test_the_backfill_turns_todays_unsubscribes_into_consent_once(self):
		for values in (
			{"global_unsubscribe": 1},
			{"reference_doctype": "Church", "reference_name": self.church},
		):
			unsubscribe = frappe.get_doc({"doctype": "Email Unsubscribe", "email": SHARED_EMAIL, **values})
			unsubscribe.set_user_and_timestamp()
			unsubscribe.db_insert()

		record_consent_from_unsubscribes.execute()
		record_consent_from_unsubscribes.execute()

		for person in (self.owner, self.sharer):
			purposes = sorted(row.purpose or "" for row in consents(person.name, status=WITHDRAWN))
			self.assertEqual(purposes, ["", CHURCH_NEWS])


class TestUnsubscribesPerChurch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		create_communication_purposes()

	def test_a_church_unsubscribe_leaves_another_churchs_people_alone(self):
		mine = make_person(
			"_Test Branch Consent", "Mine", church=self.branch_a, emails=[{"email_address": SHARED_EMAIL}]
		)
		theirs = make_person(
			"_Test Branch Consent",
			"Theirs",
			church=self.branch_b,
			emails=[{"email_address": SHARED_EMAIL, "shared_from": mine.name, "shared_from_type": "Person"}],
		)
		newsletter.set_subscribed(SHARED_EMAIL, self.branch_a, False)
		self.assertFalse(allowed(mine.name, EMAIL, CHURCH_NEWS))
		self.assertTrue(allowed(theirs.name, EMAIL, CHURCH_NEWS))

	def test_each_church_decides_for_its_own_people_without_a_record(self):
		frappe.db.set_value("Church", self.branch_a, "contact_only_with_consent", 1)
		asked = make_person("_Test Branch Consent", "Asked", church=self.branch_a)
		told = make_person("_Test Branch Consent", "Told", church=self.branch_b)
		self.assertEqual(allowed_people([asked.name, told.name], EMAIL), {told.name})


RENEWAL_EMAIL = "_test_consent_renewal@example.com"


class TestConsentRenewal(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		create_communication_purposes()

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Church", self.church, "contact_only_with_consent", 1)
		self.person = make_person("_Test Renewal", "Person", emails=[{"email_address": RENEWAL_EMAIL}])

	def consent(self, *args, **values):
		return frappe.get_doc("Communication Consent", record([self.person.name], EMAIL, *args, **values)[0])

	def test_the_newest_email_yes_of_a_church_that_asks_first_is_due(self):
		self.consent(GIVEN, CHURCH_NEWS, recorded_on="2024-06-01 10:00:00")
		self.assertTrue(
			self.consent(GIVEN, PASTORAL_CARE, recorded_on="2024-06-02 10:00:00").is_due_for_renewal
		)

	def test_a_newer_record_of_either_answer_ends_the_reminder(self):
		older = self.consent(GIVEN, CHURCH_NEWS, recorded_on="2024-06-01 10:00:00")
		withdrawal = self.consent(WITHDRAWN, CHURCH_NEWS, recorded_on="2025-06-01 10:00:00")
		self.assertFalse(older.is_due_for_renewal)
		self.assertFalse(withdrawal.is_due_for_renewal)

	def test_two_yeses_at_one_moment_ask_once(self):
		moment = "2024-06-01 10:00:00"
		first = self.consent(GIVEN, CHURCH_NEWS, recorded_on=moment)
		second = self.consent(GIVEN, PASTORAL_CARE, recorded_on=moment)
		self.assertEqual([first.is_due_for_renewal, second.is_due_for_renewal], [False, True])

	def test_only_a_church_that_asks_first_reminds_and_never_for_texts_or_the_dead(self):
		self.assertFalse(
			frappe.get_doc(
				"Communication Consent", record([self.person.name], SMS, GIVEN)[0]
			).is_due_for_renewal
		)
		consent = self.consent(GIVEN)
		frappe.db.set_value("Person", self.person.name, "is_deceased", 1)
		self.assertFalse(consent.is_due_for_renewal)
		frappe.db.set_value("Person", self.person.name, "is_deceased", 0)
		frappe.db.set_value("Church", self.church, "contact_only_with_consent", 0)
		self.assertFalse(consent.is_due_for_renewal)

	def test_the_link_says_yes_again_to_what_the_person_allows_once_a_day(self):
		self.consent(GIVEN, CHURCH_NEWS, recorded_on="2024-06-01 10:00:00")
		self.consent(GIVEN, PASTORAL_CARE, recorded_on="2024-06-01 10:00:00")
		self.consent(WITHDRAWN, PASTORAL_CARE, recorded_on="2024-07-01 10:00:00")

		self.assertEqual(len(renew(self.person.name)), 1)
		self.assertEqual(renew(self.person.name), [])
		renewed = frappe.get_all(
			"Communication Consent",
			filters={"person": self.person.name, "method": EMAIL_LINK},
			fields=["purpose", "status"],
		)
		self.assertEqual(renewed, [{"purpose": CHURCH_NEWS, "status": GIVEN}])
		self.assertTrue(allowed(self.person.name, EMAIL, CHURCH_NEWS))
		self.assertFalse(allowed(self.person.name, EMAIL, PASTORAL_CARE))

	def test_the_shipped_reminder_reaches_the_person_with_a_signed_link(self):
		notification, message = shipped_templates("church_communications", "Consent Renewal")
		consent = self.consent(GIVEN, CHURCH_NEWS)

		self.assertTrue(frappe.safe_eval(notification["condition"], None, {"doc": consent}))
		self.assertEqual(
			frappe.render_template(notification["recipients"][0]["cc"], {"doc": consent}), RENEWAL_EMAIL
		)
		html = frappe.render_template(message, {"doc": consent})
		self.assertIn(consent_renewal_link(consent), html)
		self.assertIn("renew_consent?", consent_renewal_link(consent))
		self.assertIn("_signature=", consent_renewal_link(consent))
