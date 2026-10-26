# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import threading
from unittest.mock import patch

import frappe
from frappe.api.v1 import update_doc
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, now_datetime

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	SIGN_UP_SOURCE,
	is_open_for_sign_up,
	link_registrant,
)
from churchit.church_ministries.report.function_sign_up_items.function_sign_up_items import execute
from churchit.church_ministries.web_form.function_sign_up.function_sign_up import get_context
from churchit.church_people.membership import VISITOR
from churchit.patches.v1_0 import confirm_existing_sign_ups
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.tests.test_questions import make_question_set

SIGN_UP = "Function Sign-Up"


class SignUpTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.function = make_function(
			"_Test Guest Sign-Up Function", allow_sign_ups=1, publish=1, allow_guest_sign_ups=1
		).name
		cls.member_user = ensure_user("_test_guest_signup_member@example.com", "_Test Member")
		cls.member = make_person("_Test Signup", "Member", user=cls.member_user).name

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("People Settings", "match_threshold", 80)
		# A guest sign-up queues its person job after the commit a test never makes; tests run it themselves.
		enqueue = patch("frappe.enqueue")
		self.enqueue = enqueue.start()
		self.addCleanup(enqueue.stop)

	def sign_up(self, user="Administrator", **values):
		frappe.set_user(user)
		try:
			return frappe.get_doc({"doctype": SIGN_UP, "function": self.function, **values}).insert(
				ignore_permissions=True
			)
		finally:
			frappe.set_user("Administrator")

	def guest_sign_up(self, **values):
		values = {"registrant_name": "_Test Gina Guest", "email": "_test_gina@example.com", **values}
		return self.sign_up(user="Guest", **values)


class TestGuestSignUps(SignUpTestCase):
	def test_a_guest_sign_up_is_confirmed_with_no_person_and_queues_the_person_job(self):
		sign_up = self.guest_sign_up(phone="555 0100")

		self.assertEqual((sign_up.status, sign_up.person), (CONFIRMED, None))
		self.assertEqual(sign_up.title, "_Test Guest Sign-Up Function - _Test Gina Guest")
		self.assertEqual(self.enqueue.call_args.args, (link_registrant,))
		self.assertEqual(self.enqueue.call_args.kwargs["sign_up"], sign_up.name)
		self.assertTrue(self.enqueue.call_args.kwargs["enqueue_after_commit"])

	def test_a_sign_up_with_no_person_needs_a_name_and_an_email(self):
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(registrant_name="_Test Nameonly")
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(email="_test_nobody@example.com")

	def test_a_guest_never_names_the_person(self):
		self.assertIsNone(self.guest_sign_up(person=self.member).person)

	def test_a_second_guest_sign_up_for_the_function_is_accepted(self):
		self.guest_sign_up()
		self.guest_sign_up(registrant_name="_Test Other Guest", email="_test_other_guest@example.com")

		self.assertEqual(
			frappe.db.count(SIGN_UP, {"function": self.function, "person": ("is", "not set")}), 2
		)

	def test_the_job_links_the_one_strongly_matched_person(self):
		person = make_person("_Test Gina", "Guest")
		person.append("emails", {"email_address": "_test_gina@example.com"})
		person.save(ignore_permissions=True)
		sign_up = self.guest_sign_up()

		frappe.set_user("Guest")
		link_registrant(sign_up.name)

		frappe.set_user("Administrator")
		sign_up.reload()
		self.assertEqual(sign_up.person, person.name)
		self.assertEqual(sign_up.title, f"_Test Guest Sign-Up Function - {person.full_name}")

	def test_the_job_adds_a_visitor_with_the_sign_up_source_when_nobody_matches(self):
		sign_up = self.guest_sign_up(registrant_name="_Test Newcomer Person", phone="555 0199")

		frappe.set_user("Guest")
		link_registrant(sign_up.name)

		frappe.set_user("Administrator")
		person = frappe.get_doc("Person", frappe.db.get_value(SIGN_UP, sign_up.name, "person"))
		self.assertEqual((person.first_name, person.last_name), ("_Test Newcomer", "Person"))
		self.assertEqual((person.membership, person.source), (VISITOR, SIGN_UP_SOURCE))
		self.assertEqual([row.email_address for row in person.emails], ["_test_gina@example.com"])

	def test_the_job_leaves_a_person_already_signed_up_and_names_that_sign_up(self):
		person = make_person("_Test Gina", "Guest")
		person.append("emails", {"email_address": "_test_gina@example.com"})
		person.save(ignore_permissions=True)
		theirs = self.sign_up(person=person.name)
		sign_up = self.guest_sign_up()

		link_registrant(sign_up.name)

		self.assertIsNone(frappe.db.get_value(SIGN_UP, sign_up.name, "person"))
		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": SIGN_UP, "reference_name": sign_up.name},
			pluck="content",
		)
		self.assertTrue(any(theirs.name in comment for comment in comments), comments)

	def test_the_job_does_nothing_once_the_sign_up_has_a_person(self):
		sign_up = self.guest_sign_up()
		frappe.db.set_value(SIGN_UP, sign_up.name, "person", self.member)

		link_registrant(sign_up.name)

		self.assertEqual(frappe.db.get_value(SIGN_UP, sign_up.name, "person"), self.member)
		self.assertFalse(frappe.db.exists("Person", {"source": SIGN_UP_SOURCE, "first_name": "_Test Gina"}))


class TestLinkRegistrantRace(FrappeTestCase):
	"""Two person jobs at once, each with its own connection. Commits real data, deleted at the end."""

	def test_two_jobs_for_one_person_link_one_sign_up(self):
		threshold = frappe.db.get_single_value("People Settings", "match_threshold")
		frappe.db.set_single_value("People Settings", "match_threshold", 80)
		function = make_function("_Test Link Race", allow_sign_ups=1, publish=1, allow_guest_sign_ups=1).name
		person = make_person("_Test Rae", "Racer")
		person.append("emails", {"email_address": "_test_rae@example.com"})
		person.save(ignore_permissions=True)
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		sign_ups = []
		try:
			for _index in range(2):
				values = {"registrant_name": "_Test Rae Racer", "email": "_test_rae@example.com"}
				doc = frappe.get_doc({"doctype": SIGN_UP, "function": function, **values})
				sign_ups.append(doc.insert(ignore_permissions=True).name)
			frappe.db.commit()

			errors = race_to_link(sign_ups)
			self.assertEqual(errors, [])
			people = [frappe.db.get_value(SIGN_UP, name, "person") for name in sign_ups]
			self.assertCountEqual(people, [person.name, None])
		finally:
			enqueue.stop()
			frappe.db.rollback()
			frappe.db.delete(
				"Comment", {"reference_doctype": SIGN_UP, "reference_name": ("in", sign_ups or [""])}
			)
			for doctype, name in [
				*((SIGN_UP, name) for name in sign_ups),
				("Function", function),
				("Person", person.name),
			]:
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
			frappe.db.set_single_value("People Settings", "match_threshold", threshold)
			frappe.db.commit()


def race_to_link(sign_ups: list[str]) -> list:
	"""Run link_registrant for each of *sign_ups* at once, as the guest, each in a thread with its own connection."""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	# Each job reads before either commits, so a plain read would answer from a snapshot without the other link.
	barrier = threading.Barrier(len(sign_ups), timeout=30)
	errors = []

	def link(sign_up):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			frappe.set_user("Guest")
			frappe.db.get_value(SIGN_UP, sign_up, "person")
			barrier.wait()
			link_registrant(sign_up)
			frappe.db.commit()
		except Exception as error:
			errors.append(error)
		finally:
			frappe.destroy()

	threads = [threading.Thread(target=link, args=(sign_up,)) for sign_up in sign_ups]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return errors


class TestSignUpItemsReport(SignUpTestCase):
	def test_a_guest_sign_up_shows_the_typed_name_escaped(self):
		item = frappe.get_doc({"doctype": "Sign-Up Item", "item": "_Test Guest Dish"}).insert(
			ignore_permissions=True
		)
		sign_up = frappe.new_doc(SIGN_UP, function=self.function, registrant_name="<b>_Test Gina</b>")
		sign_up.email = "_test_gina@example.com"
		sign_up.append("table_iprj", {"item": item.name, "my_quantity": 2})
		sign_up.insert(ignore_permissions=True)

		_columns, rows = execute({"function": self.function})

		self.assertEqual([row["person_display"] for row in rows], ["&lt;b&gt;_Test Gina&lt;/b&gt;"])
		self.assertNotIn("<b>", rows[0]["sign_up_display"])


class TestProtectedFields(SignUpTestCase):
	def test_a_rest_put_by_the_owner_keeps_the_stored_status_and_payment(self):
		sign_up = self.sign_up(user=self.member_user)
		frappe.set_user(self.member_user)
		frappe.local.form_dict = frappe._dict(
			data=json.dumps(
				{
					"status": CANCELLED,
					"amount_paid": 50,
					"payment_status": "Paid",
					"approved_by": self.member_user,
					"hold_expires_on": str(add_days(now_datetime(), 30)),
					"notes": "_Test changed",
				}
			)
		)
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

		update_doc(SIGN_UP, sign_up.name)

		stored = frappe.db.get_value(
			SIGN_UP,
			sign_up.name,
			["status", "amount_paid", "payment_status", "approved_by", "hold_expires_on", "notes"],
			as_dict=True,
		)
		self.assertEqual(stored.notes, "_Test changed")
		self.assertEqual(
			(stored.status, stored.amount_paid, stored.approved_by, stored.hold_expires_on),
			(CONFIRMED, 0, None, None),
		)
		self.assertNotEqual(stored.payment_status, "Paid")

	def test_a_new_sign_up_takes_no_status_or_payment_the_caller_sent(self):
		sign_up = self.sign_up(person=self.member, status=CANCELLED, amount_paid=50, payment_status="Paid")
		self.assertEqual((sign_up.status, flt(sign_up.amount_paid)), (CONFIRMED, 0))
		self.assertNotEqual(sign_up.payment_status, "Paid")


class TestCancelRegistration(SignUpTestCase):
	def test_the_owner_cancels_and_may_then_sign_up_again(self):
		sign_up = self.sign_up(user=self.member_user)
		frappe.set_user(self.member_user)

		sign_up.cancel_registration()

		self.assertEqual(frappe.db.get_value(SIGN_UP, sign_up.name, "status"), CANCELLED)
		self.assertEqual(self.sign_up(user=self.member_user).status, CONFIRMED)

	def test_a_member_cannot_cancel_someone_elses_sign_up(self):
		sign_up = self.sign_up(person=make_person("_Test Signup", "Other").name)
		frappe.set_user(self.member_user)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(SIGN_UP, sign_up.name).cancel_registration()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(SIGN_UP, sign_up.name, "status"), CONFIRMED)

	def test_cancelling_gives_the_seats_to_the_waitlist(self):
		sign_up = self.sign_up(person=self.member)
		with patch(
			"churchit.church_ministries.doctype.function_sign_up.function_sign_up.promote_waitlist"
		) as promote_waitlist:
			sign_up.cancel_registration()
		promote_waitlist.assert_called_once_with(self.function)


class TestConfirmExistingSignUpsPatch(SignUpTestCase):
	def test_every_sign_up_without_a_status_reads_confirmed_and_a_rerun_keeps_a_cancellation(self):
		attending = self.sign_up(person=self.member, attending=1)
		items_only = self.sign_up(person=make_person("_Test Signup", "Bringer").name, attending=0)
		cancelled = self.sign_up(person=make_person("_Test Signup", "Gone").name)
		frappe.db.set_value(SIGN_UP, {"name": ("in", [attending.name, items_only.name])}, "status", None)
		frappe.db.set_value(SIGN_UP, cancelled.name, "status", CANCELLED)

		confirm_existing_sign_ups.execute()
		confirm_existing_sign_ups.execute()

		self.assertEqual(frappe.db.get_value(SIGN_UP, attending.name, "status"), CONFIRMED)
		self.assertEqual(frappe.db.get_value(SIGN_UP, items_only.name, "status"), CONFIRMED)
		self.assertEqual(frappe.db.get_value(SIGN_UP, cancelled.name, "status"), CANCELLED)


class TestSignUpWindow(SignUpTestCase):
	"""Members and guests sign up only between Sign-Ups Open On and Sign-Ups Close On; the desk is not refused."""

	def set_window(self, opens=None, closes=None):
		frappe.db.set_value(
			"Function", self.function, {"sign_ups_open_on": opens, "sign_ups_close_on": closes}
		)

	def offered_by_web_form(self):
		frappe.set_user(self.member_user)
		web_form = frappe.get_doc("Web Form", "function-sign-up")
		field = next(field for field in web_form.web_form_fields if field.fieldname == "function")
		field.options = self.function
		context = frappe._dict(web_form_doc=web_form)
		get_context(context)
		frappe.set_user("Administrator")
		return self.function in field.options.split("\n")

	def test_with_both_dates_blank_members_and_guests_sign_up_as_before(self):
		self.set_window()
		self.assertTrue(self.offered_by_web_form())
		self.assertEqual(self.sign_up(user=self.member_user).status, CONFIRMED)
		self.assertEqual(self.guest_sign_up().status, CONFIRMED)

	def test_before_the_window_opens_members_and_guests_are_refused_and_the_form_offers_nothing(self):
		self.set_window(opens=add_days(now_datetime(), 1))
		self.assert_closed()

	def test_after_the_window_closes_members_and_guests_are_refused_and_the_form_offers_nothing(self):
		self.set_window(opens=add_days(now_datetime(), -5), closes=add_days(now_datetime(), -1))
		self.assert_closed()

	def test_the_form_leaves_out_a_function_with_selections_or_questions(self):
		self.set_window()
		function = frappe.get_doc("Function", self.function)
		function.append("selections", {"selection": "Adult"})
		function.save()
		self.assertFalse(self.offered_by_web_form())

		function.selections = []
		function.save()
		self.assertTrue(self.offered_by_web_form())

		question_set = make_question_set("_Test Sign-Up Form Questions").name
		frappe.db.set_value("Function", self.function, "question_set", question_set)
		self.assertFalse(self.offered_by_web_form())

	def assert_closed(self):
		self.assertFalse(self.offered_by_web_form())
		for user in (self.member_user, "Guest"):
			frappe.set_user(user)
			self.assertFalse(is_open_for_sign_up(self.function))
		frappe.set_user("Administrator")
		with self.assertRaises(frappe.PermissionError):
			self.sign_up(user=self.member_user)
		with self.assertRaises(frappe.PermissionError):
			self.guest_sign_up()
		# Staff can still add a late sign-up in the desk.
		self.assertEqual(self.sign_up(person=self.member).status, CONFIRMED)

	def test_a_member_may_still_cancel_once_sign_ups_close(self):
		sign_up = self.sign_up(user=self.member_user)
		self.set_window(closes=add_days(now_datetime(), -1))
		frappe.set_user(self.member_user)

		sign_up.cancel_registration()

		self.assertEqual(frappe.db.get_value(SIGN_UP, sign_up.name, "status"), CANCELLED)

	def test_a_guest_signs_up_only_for_a_published_function_with_guest_sign_ups(self):
		for values in ({"publish": 0}, {"allow_guest_sign_ups": 0}):
			frappe.db.set_value(
				"Function", self.function, {"publish": 1, "allow_guest_sign_ups": 1, **values}
			)
			with self.assertRaises(frappe.PermissionError):
				self.guest_sign_up()


class TestSharedFunctionGuest(RollbackEachTest):
	def setUp(self):
		super().setUp()
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)

	def test_a_guest_of_a_shared_function_is_added_at_the_church_that_shared_it(self):
		_root, branch_a, branch_b = make_two_churches()
		self.addCleanup(frappe.clear_cache)
		function = make_function(
			"_Test Guest Shared Camp",
			church=branch_a,
			is_shared=1,
			allow_sign_ups=1,
			publish=1,
			allow_guest_sign_ups=1,
		).name
		frappe.set_user("Guest")
		# The branch whose public page took the sign-up is not the church that shared the function.
		frappe.local.form_dict = frappe._dict(church=branch_b)
		sign_up = frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": function,
				"registrant_name": "_Test Shared Newby",
				"email": "_test_shared_newby@example.com",
			}
		).insert(ignore_permissions=True)
		frappe.local.form_dict = frappe._dict()

		link_registrant(sign_up.name)

		frappe.set_user("Administrator")
		person = frappe.db.get_value(SIGN_UP, sign_up.name, "person")
		self.assertEqual(frappe.db.get_value("Person", person, "church"), branch_a)
