# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.utils import add_days, now_datetime, today
from requests import HTTPError, Response

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHILD_SAFETY,
	create_communication_purposes,
)
from churchit.church_communications.test_preferences import send_sms_hooks
from churchit.church_communications.test_sending import log_sms
from churchit.church_ministries.page.check_in.paging import PAGE_KEY, page_parents
from churchit.church_people.test_household import make_household, set_adult_age
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

MODULE = "churchit.church_ministries.page.check_in.paging"


def add_contacts(person, email, phone=None):
	doc = frappe.get_doc("Person", person)
	doc.append("emails", {"email_address": email, "is_primary": 1})
	if phone:
		doc.append("phones", {"phone_number": phone, "is_primary": 1})
	doc.save(ignore_permissions=True)


def set_sms_settings(roles):
	settings = frappe.get_single("SMS Settings")
	settings.update(
		{
			"sms_gateway_url": "https://sms.example.com/send",
			"message_parameter": "text",
			"receiver_parameter": "to",
		}
	)
	settings.set("allowed_roles", [{"role": role} for role in roles])
	settings.save(ignore_permissions=True)


class TestPageParents(RollbackEachTest):
	"""A page reaches the child's household Adults who allow the Child Safety purpose, by text or email."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		set_adult_age(18)
		create_communication_purposes()
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household(
			"_Test Paging Household", "Pageley"
		)
		add_contacts(cls.father, "_test_paging_father@example.com", "555 010 0201")
		add_contacts(cls.mother, "_test_paging_mother@example.com", "555 010 0202")
		add_contacts(cls.grandmother, "_test_paging_gran@example.com", "555 010 0203")
		cls.neighbour = make_person(
			"Ned",
			"_Test Paging Neighbour",
			emails=[{"email_address": "_test_paging_ned@example.com", "is_primary": 1}],
			phones=[{"phone_number": "555 010 0204", "is_primary": 1}],
		).name
		record([cls.father, cls.grandmother, cls.neighbour], SMS, GIVEN, CHILD_SAFETY)
		record([cls.mother], SMS, WITHDRAWN, CHILD_SAFETY)

		cls.function = make_function("_Test Paging Service", church=cls.church, start_date=today())
		cls.check_in = (
			frappe.get_doc({"doctype": "Function Check-In", "function": cls.function.name, "person": cls.son})
			.insert(ignore_permissions=True)
			.name
		)
		cls.volunteer = cls.bind_volunteer("_test_paging_volunteer@example.com", "PagingA", cls.church)
		cls.other_volunteer = cls.bind_volunteer(
			"_test_paging_other@example.com", "PagingB", cls.other_church
		)

	@classmethod
	def bind_volunteer(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Check-In",))
		make_person(first_name, "_Test Paging Volunteer", church=church, user=user)
		return user

	def setUp(self):
		super().setUp()
		frappe.cache.delete_value(PAGE_KEY.format(self.check_in))
		self.addCleanup(frappe.cache.delete_value, PAGE_KEY.format(self.check_in))
		for patcher in (
			send_sms_hooks([]),
			mock.patch("churchit.church_communications.sending.send_sms", side_effect=log_sms),
			mock.patch(f"{MODULE}.can_send_email", return_value=True),
			mock.patch.object(frappe.db, "commit"),
		):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.addCleanup(mock.patch.stopall)
		set_sms_settings(["Church Check-In"])

	def copies(self):
		"""(person, medium) of each copy made about the child."""
		names = frappe.get_all(
			"Communication Link",
			filters={
				"link_doctype": "Person",
				"link_name": self.son,
				"parenttype": "Communication",
			},
			pluck="parent",
		)
		rows = frappe.get_all(
			"Communication",
			filters={"name": ("in", names)},
			fields=["reference_name", "communication_medium"],
		)
		return {(row.reference_name, row.communication_medium) for row in rows}

	def test_a_page_reaches_only_the_childs_household_adults(self):
		"""The father allows texts; the mother refused texts, so she gets an email. No one else is paged."""
		frappe.set_user(self.volunteer)

		reached = page_parents(self.check_in)

		self.assertEqual(reached, ["John Pageley", "Jane Pageley"])
		self.assertEqual(self.copies(), {(self.father, SMS), (self.mother, EMAIL)})
		self.assertEqual(self.sendmail.call_args.kwargs["recipients"], ["_test_paging_mother@example.com"])
		self.assertIn("Tim", self.sendmail.call_args.kwargs["message"])

	def test_an_adult_who_allows_nothing_is_not_reached(self):
		record([self.mother], EMAIL, WITHDRAWN, CHILD_SAFETY)
		record([self.father], SMS, WITHDRAWN, CHILD_SAFETY)
		record([self.father], EMAIL, WITHDRAWN, CHILD_SAFETY)
		frappe.set_user(self.volunteer)

		self.assertEqual(page_parents(self.check_in), [])
		self.assertEqual(self.copies(), set())
		self.assertEqual(page_parents(self.check_in), [], "a page that reached no one can be tried again")

	def test_an_adult_a_pickup_restriction_names_is_not_paged(self):
		restriction = frappe.get_doc(
			{
				"doctype": "Pickup Restriction",
				"child": self.son,
				"restricted_person": self.father,
				"description": "_Test Call the office",
			}
		).insert()
		frappe.set_user(self.volunteer)

		self.assertEqual(page_parents(self.check_in), ["Jane Pageley"])
		self.assertEqual(self.copies(), {(self.mother, EMAIL)})

		frappe.set_user("Administrator")
		restriction.db_set("valid_until", add_days(today(), -1))
		frappe.cache.delete_value(PAGE_KEY.format(self.check_in))
		frappe.set_user(self.volunteer)
		self.assertIn("John Pageley", page_parents(self.check_in), "a restriction that ended pages the Adult")

	def test_a_second_page_within_two_minutes_is_refused(self):
		frappe.set_user(self.volunteer)
		page_parents(self.check_in)

		with self.assertRaisesRegex(frappe.ValidationError, "2 minutes"):
			page_parents(self.check_in)

	def test_a_collected_child_cannot_be_paged(self):
		frappe.db.set_value("Function Check-In", self.check_in, "collected_at", now_datetime())
		frappe.set_user(self.volunteer)

		with self.assertRaisesRegex(frappe.ValidationError, "collected"):
			page_parents(self.check_in)
		self.assertEqual(self.copies(), set())

	def test_a_volunteer_not_allowed_to_text_pages_by_email_with_no_error(self):
		set_sms_settings([])
		frappe.set_user(self.volunteer)
		frappe.clear_messages()

		reached = page_parents(self.check_in)

		self.assertEqual(reached, ["John Pageley", "Jane Pageley"])
		self.assertEqual(self.copies(), {(self.father, EMAIL), (self.mother, EMAIL)})
		self.assertEqual(frappe.get_message_log(), [])

	def test_a_site_with_no_text_gateway_pages_by_email(self):
		frappe.db.set_single_value("SMS Settings", "sms_gateway_url", "")
		frappe.set_user(self.volunteer)

		self.assertEqual(page_parents(self.check_in), ["John Pageley", "Jane Pageley"])
		self.assertEqual(self.copies(), {(self.father, EMAIL), (self.mother, EMAIL)})

	def test_a_text_gateway_failure_pages_by_email(self):
		"""A gateway that is down stops the texts, and each Adult not reached gets an email instead."""
		response = Response()
		response.status_code = 503
		frappe.set_user(self.volunteer)

		with mock.patch(
			"churchit.church_communications.sending.send_sms", side_effect=HTTPError(response=response)
		):
			reached = page_parents(self.check_in)

		self.assertEqual(reached, ["John Pageley", "Jane Pageley"])
		self.assertEqual(self.copies(), {(self.father, EMAIL), (self.mother, EMAIL)})
		self.assertTrue(frappe.db.exists("Error Log", {"reference_name": self.son}))

	def test_no_check_in_row_is_locked_while_the_gateway_answers(self):
		"""A gateway can hang, and every code draw on the site locks the day's coded check-ins."""
		events = []
		get_value = frappe.db.get_value

		def read(doctype, *args, **kwargs):
			if kwargs.get("for_update"):
				events.append(doctype)
			return get_value(doctype, *args, **kwargs)

		def gateway(*args, **kwargs):
			events.append("gateway")
			log_sms(*args, **kwargs)

		frappe.db.commit.side_effect = lambda: events.append("commit")
		frappe.set_user(self.volunteer)
		with (
			mock.patch.object(frappe.db, "get_value", side_effect=read),
			mock.patch("churchit.church_communications.sending.send_sms", side_effect=gateway),
		):
			self.assertEqual(page_parents(self.check_in), ["John Pageley", "Jane Pageley"])

		claimed = events.index("commit")
		self.assertEqual(events[:claimed], ["Function Check-In"])
		self.assertIn("gateway", events[claimed:])
		self.assertNotIn("Function Check-In", events[claimed:])

	def test_a_page_needs_the_check_in_right_and_a_check_in_of_the_users_church(self):
		staff = ensure_user("_test_paging_staff@example.com", "PagingStaff", roles=("Church Staff",))
		for user in (staff, self.other_volunteer):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				page_parents(self.check_in)
		frappe.set_user("Administrator")
		self.assertEqual(self.copies(), set())
