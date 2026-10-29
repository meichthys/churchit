# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.handler import run_doc_method
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime
from rq.timeouts import JobTimeoutException

from churchit.church_communications.consent import allowed
from churchit.church_communications.doctype.church_email.church_email import deliver, send_scheduled
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.church_communications.newsletter import UNSUBSCRIBE_METHOD, set_subscribed, unsubscribe
from churchit.church_communications.sending import Delivery, Recipient
from churchit.church_communications.test_sending import log_sms
from churchit.church_people.test_household import born, label
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_primary_contact,
	make_smart_list,
	make_two_churches,
)

MODULE = "churchit.church_communications.doctype.church_email.church_email"
SENDING = "churchit.church_communications.sending"


def make_reader(first_name, **values):
	email = f"_test_church_email_{first_name.lower()}@example.com"
	return make_person(first_name, "_Test Church Email", emails=[{"email_address": email}], **values)


def email_of(person):
	return person.emails[0].email_address


def addresses(email):
	return [recipient.address for recipient in email.get_recipients()]


def deliver_now(name):
	"""Run the delivery job without committing the test's transaction."""
	with mock.patch.object(frappe.db, "commit"):
		deliver(name)


def run_scheduler():
	"""Run the scheduled job without committing, and return the names it queued for delivery."""
	with mock.patch.object(frappe.db, "commit"), mock.patch(f"{MODULE}.enqueue_delivery") as enqueue:
		send_scheduled()
	return [call.args[0] for call in enqueue.call_args_list]


def call_from_browser(method, doc, **args):
	"""Run a Church Email method as the desk does: on the copy of the document the browser sends."""
	frappe.local.request = frappe._dict(method="POST")
	try:
		run_doc_method(method, docs=frappe.as_json(doc), args=frappe.as_json(args))
	finally:
		del frappe.local.request
	return frappe.response.pop("message", None)


def copies_of(email):
	"""The Communications a Church Email made, as (person, medium, subject, content)."""
	names = frappe.get_all(
		"Communication Link",
		filters={"parenttype": "Communication", "link_doctype": "Church Email", "link_name": email},
		pluck="parent",
	)
	return frappe.get_all(
		"Communication",
		filters={"name": ("in", names), "reference_doctype": "Person"},
		fields=["reference_name", "communication_medium", "subject", "content", "phone_no", "recipients"],
		order_by="reference_name asc",
	)


class ChurchEmailTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		for status in ("Active", "Inactive"):
			ensure("Member Status", {"status": status})
		for membership in ("Member", "Visitor"):
			ensure("Membership Type", {"type": membership})
		ensure("Life Event Type", {"type": "Death"})
		create_communication_purposes()
		cls.member = make_reader("Member", membership="Member")
		cls.visitor = make_reader("Visitor", membership="Visitor")
		cls.inactive = make_reader("Inactive", membership="Member", membership_status="Inactive")
		cls.departed = make_reader(
			"Departed", membership="Member", life_events=[{"event_type": "Death", "date": "2024-01-01"}]
		)
		cls.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Church Email Group",
				"members": [{"person": p.name} for p in (cls.member, cls.inactive, cls.departed)],
			}
		).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		self.sendmail = self.start(mock.patch("frappe.sendmail"))
		self.start(mock.patch(f"{MODULE}.can_send_email", return_value=True))

	def start(self, patcher):
		self.addCleanup(patcher.stop)
		return patcher.start()

	def make_email(self, **values):
		return frappe.get_doc(
			{"doctype": "Church Email", "subject": "_Test Church Email", "message": "<p>Hello</p>", **values}
		).insert()


class TestChurchEmail(ChurchEmailTestCase):
	def test_active_people_leave_out_the_inactive_the_departed_and_the_unsubscribed(self):
		unsubscribed = make_reader("Unsubscribed", membership="Member")
		set_subscribed(email_of(unsubscribed), self.church, False)

		recipients = addresses(self.make_email())

		for person in (self.member, self.visitor):
			self.assertIn(email_of(person), recipients)
		for person in (self.inactive, self.departed, unsubscribed):
			self.assertNotIn(email_of(person), recipients)

	def test_only_people_who_allow_the_purpose_get_it(self):
		record([self.member.name], EMAIL, WITHDRAWN, CHURCH_NEWS)
		record([self.visitor.name], EMAIL, WITHDRAWN, PASTORAL_CARE)

		news = addresses(self.make_email())
		care = addresses(self.make_email(purpose=PASTORAL_CARE))

		self.assertNotIn(email_of(self.member), news)
		self.assertIn(email_of(self.visitor), news)
		self.assertIn(email_of(self.member), care)
		self.assertNotIn(email_of(self.visitor), care)

	def test_a_church_that_asks_first_emails_only_people_who_agreed(self):
		frappe.db.set_value("Church", self.church, "contact_only_with_consent", 1)
		record([self.visitor.name], EMAIL, GIVEN, CHURCH_NEWS)
		self.assertEqual(addresses(self.make_email()), [email_of(self.visitor)])

	def test_an_address_whose_mail_came_back_is_left_out(self):
		frappe.db.set_value("Email Address", self.visitor.emails[0].name, "is_bounced", 1)
		self.assertNotIn(email_of(self.visitor), addresses(self.make_email()))

	def test_a_household_sharing_an_address_gets_one_copy(self):
		sharer = make_person(
			"Sharer",
			"_Test Church Email",
			membership="Member",
			emails=[
				{
					"email_address": email_of(self.member),
					"shared_from": self.member.name,
					"shared_from_type": "Person",
				}
			],
		)
		recipients = self.make_email().get_recipients()

		self.assertEqual([r.address for r in recipients].count(email_of(self.member)), 1)
		self.assertNotIn(sharer.name, [r.person for r in recipients])

	def test_active_members_leave_out_visitors(self):
		recipients = addresses(self.make_email(send_to="Active Members"))
		self.assertIn(email_of(self.member), recipients)
		self.assertNotIn(email_of(self.visitor), recipients)

	def test_a_group_email_goes_to_the_groups_living_members(self):
		email = self.make_email(send_to="Group", group=self.group.name)
		self.assertEqual(sorted(addresses(email)), sorted([email_of(self.member), email_of(self.inactive)]))

	def test_a_smart_list_email_goes_to_the_living_people_on_the_list(self):
		smart_list = make_smart_list(
			"_Test Church Email Members",
			[["Person", "last_name", "=", "_Test Church Email"], ["Person", "membership", "=", "Member"]],
		)
		email = self.make_email(send_to="Smart List", smart_list=smart_list.name)
		self.assertEqual(sorted(addresses(email)), sorted([email_of(self.member), email_of(self.inactive)]))

	def test_a_smart_list_must_be_a_saved_list_of_people(self):
		families = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "_Test Church Email Families",
				"ref_doctype": "Family",
				"report_type": "Report Builder",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)
		with self.assertRaisesRegex(frappe.ValidationError, "smart list"):
			self.make_email(send_to="Smart List", smart_list=families.name)

	def test_chosen_people_get_it_and_nobody_else(self):
		email = self.make_email(
			send_to="Chosen People", people=[{"person": self.visitor.name}, {"person": self.departed.name}]
		)
		self.assertEqual(addresses(email), [email_of(self.visitor)])

	def test_an_audience_that_send_to_does_not_use_is_cleared(self):
		email = self.make_email(group=self.group.name, people=[{"person": self.visitor.name}])
		self.assertEqual((email.group, email.people), (None, []))

	def test_each_person_gets_a_copy_with_their_own_name_kept_on_their_timeline(self):
		email = self.make_email(
			send_to="Group",
			group=self.group.name,
			subject="Hello {{ first_name }}",
			message="<p>Dear {{ doc.display_name }}</p>",
		)
		with mock.patch("frappe.enqueue") as enqueue:
			self.assertEqual(email.send(), "Sending")
		self.assertEqual(enqueue.call_args.kwargs["name"], email.name)

		deliver_now(email.name)
		deliver_now(email.name)

		self.assertEqual(self.sendmail.call_count, 2)
		sent = {call.kwargs["recipients"][0]: call.kwargs for call in self.sendmail.call_args_list}
		member = sent[email_of(self.member)]
		self.assertEqual(member["subject"], "Hello Member")
		self.assertIn("Dear Member _Test Church Email", member["message"])
		self.assertEqual(member["unsubscribe_method"], UNSUBSCRIBE_METHOD)
		self.assertEqual(
			member["unsubscribe_params"],
			{"church": self.church, "purpose": CHURCH_NEWS, "person": self.member.name},
		)
		self.assertEqual(member["reference_name"], email.name)

		copies = copies_of(email.name)
		self.assertEqual(
			[copy.reference_name for copy in copies], sorted([self.member.name, self.inactive.name])
		)
		copy = next(copy for copy in copies if copy.reference_name == self.member.name)
		self.assertEqual((copy.communication_medium, copy.subject), ("Email", "Hello Member"))
		self.assertIn("Dear Member _Test Church Email", copy.content)
		self.assertEqual(
			member["communication"], frappe.db.get_value("Communication", {"subject": "Hello Member"})
		)
		email.reload()
		self.assertEqual((email.status, email.recipients), ("Sent", 2))

	def test_a_delivery_that_stopped_part_way_sends_only_to_the_people_still_waiting(self):
		email = self.make_email(send_to="Group", group=self.group.name)
		Delivery(email).record(
			Recipient(self.member.name, email_of(self.member)), frappe._dict(subject="x", message="y")
		)
		frappe.db.set_value("Church Email", email.name, "status", "Sending")

		deliver_now(email.name)

		self.sendmail.assert_called_once()
		self.assertEqual(self.sendmail.call_args.kwargs["recipients"], [email_of(self.inactive)])
		self.assertEqual(frappe.db.get_value("Church Email", email.name, "recipients"), 2)

	def test_each_queued_copy_carries_a_link_to_stop_the_churchs_emails(self):
		"""Frappe only adds the footer link when it is given a message for it, so this runs the real sendmail."""
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Church Email Outgoing",
				"email_id": "_test_church_email_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		email = self.make_email(send_to="Group", group=self.group.name)
		frappe.db.set_value("Church Email", email.name, "status", "Sending")

		with (
			mock.patch("frappe.sendmail", wraps=frappe.email.sendmail),
			mock.patch.object(frappe.db, "rollback"),
		):
			deliver_now(email.name)

		queues = frappe.get_all(
			"Email Queue",
			filters={"reference_name": email.name},
			fields=["name", "message", "unsubscribe_params", "communication"],
		)
		self.assertEqual(len(queues), 2)
		for queue in queues:
			self.assertIn("<!--unsubscribe_url-->", queue.message)
			person = frappe.db.get_value("Communication", queue.communication, "reference_name")
			self.assertEqual(
				frappe.parse_json(queue.unsubscribe_params),
				{"church": self.church, "purpose": CHURCH_NEWS, "person": person},
			)
			self.assertEqual(
				frappe.db.get_value("Communication", queue.communication, "reference_doctype"), "Person"
			)

	def test_a_delivery_lost_with_its_worker_is_picked_up_again(self):
		email = self.make_email()
		frappe.db.set_value(
			"Church Email",
			email.name,
			{"status": "Sending", "modified": add_to_date(now_datetime(), hours=-1)},
			update_modified=False,
		)

		self.assertIn(email.name, run_scheduler())
		deliver_now(email.name)

		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Sent")

	def test_a_send_at_ahead_waits_for_the_scheduled_job(self):
		email = self.make_email(send_after=add_to_date(now_datetime(), hours=1))
		self.assertEqual(email.send(), "Scheduled")
		self.assertNotIn(email.name, run_scheduler())

		frappe.db.set_value("Church Email", email.name, "send_after", add_to_date(now_datetime(), hours=-1))
		self.assertIn(email.name, run_scheduler())
		deliver_now(email.name)

		self.sendmail.assert_called()
		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Sent")

	def test_an_unscheduled_email_is_not_sent(self):
		email = self.make_email(send_after=add_to_date(now_datetime(), hours=1))
		email.send()
		email.unschedule()
		frappe.db.set_value("Church Email", email.name, "send_after", add_to_date(now_datetime(), hours=-1))

		self.assertNotIn(email.name, run_scheduler())
		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Draft")

	def test_the_scheduled_job_claims_each_due_email_and_queues_it_on_the_long_queue(self):
		emails = [
			self.make_email(send_to="Chosen People", people=[{"person": person.name}])
			for person in (self.member, self.visitor)
		]
		for email in emails:
			frappe.db.set_value(
				"Church Email",
				email.name,
				{"status": "Scheduled", "send_after": add_to_date(now_datetime(), hours=-1)},
			)

		with mock.patch.object(frappe.db, "commit"), mock.patch("frappe.enqueue") as enqueue:
			send_scheduled()

		self.sendmail.assert_not_called()
		queued = [call.kwargs["name"] for call in enqueue.call_args_list]
		self.assertTrue(all(email.name in queued for email in emails))
		self.assertEqual({call.kwargs["queue"] for call in enqueue.call_args_list}, {"long"})
		statuses = {frappe.db.get_value("Church Email", e.name, "status") for e in emails}
		self.assertEqual(statuses, {"Sending"})

	def test_each_claim_starts_after_a_commit(self):
		email = self.make_email(send_after=add_to_date(now_datetime(), hours=1))
		email.send()
		frappe.db.set_value("Church Email", email.name, "send_after", add_to_date(now_datetime(), hours=-1))
		calls = []

		with (
			mock.patch.object(frappe.db, "commit", side_effect=lambda: calls.append("commit")),
			mock.patch(f"{MODULE}.claim", side_effect=lambda name: calls.append("claim")),
		):
			send_scheduled()

		self.assertEqual(calls[:2], ["commit", "claim"])

	def test_a_failed_delivery_returns_the_email_to_draft_and_says_why(self):
		email = self.make_email()
		frappe.db.set_value("Church Email", email.name, "status", "Sending")
		self.sendmail.side_effect = frappe.OutgoingEmailError("_Test mail server down")

		with mock.patch.object(frappe.db, "commit"), mock.patch.object(frappe.db, "rollback"):
			with self.assertRaises(frappe.OutgoingEmailError):
				deliver(email.name)

		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Draft")
		comments = frappe.get_all(
			"Comment", filters={"reference_name": email.name, "comment_type": "Comment"}, pluck="content"
		)
		self.assertTrue([comment for comment in comments if "_Test mail server down" in comment])

	def test_a_delivery_that_runs_out_of_time_stays_sending_for_the_retry(self):
		email = self.make_email()
		frappe.db.set_value("Church Email", email.name, "status", "Sending")
		self.sendmail.side_effect = JobTimeoutException("_Test job timed out")

		with mock.patch.object(frappe.db, "commit"), mock.patch.object(frappe.db, "rollback"):
			with self.assertRaises(JobTimeoutException):
				deliver(email.name)

		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Sending")
		self.assertFalse(
			frappe.db.exists("Comment", {"reference_name": email.name, "comment_type": "Comment"})
		)

	def test_an_email_is_sent_only_once(self):
		email = self.make_email()
		with mock.patch("frappe.enqueue"):
			email.send()
			with self.assertRaisesRegex(frappe.ValidationError, "already been sent"):
				email.send()

	def test_a_sent_email_cannot_be_changed(self):
		email = self.make_email()
		frappe.db.set_value("Church Email", email.name, "status", "Sent")
		email.reload()
		email.subject = "_Test Changed"
		with self.assertRaisesRegex(frappe.ValidationError, "can no longer be changed"):
			email.save()

	def test_staff_who_may_only_read_cannot_send(self):
		email = self.make_email()
		frappe.set_user(ensure_user("_test_church_email_staff@example.com", "Staff", roles=("Church Staff",)))
		for action in (email.send, email.send_test, email.unschedule):
			with self.subTest(action.__name__), self.assertRaises(frappe.PermissionError):
				action()

	def test_the_status_moves_only_by_sending(self):
		email = self.make_email(status="Sent")
		self.assertEqual(email.status, "Draft")

		email.status = "Sending"
		email.save()
		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Draft")

	def test_a_scheduled_email_keeps_its_send_at(self):
		email = self.make_email(send_after=add_to_date(now_datetime(), hours=1))
		email.send()
		email.reload()
		email.send_after = None
		with self.assertRaisesRegex(frappe.ValidationError, "Unschedule"):
			email.save()

	def test_nothing_is_sent_without_an_outgoing_email_account(self):
		email = self.make_email()
		with mock.patch(f"{MODULE}.can_send_email", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "outgoing Email Account"):
				email.send()

	def test_a_test_email_goes_to_the_reader_alone_at_once_with_their_name(self):
		self.make_email(subject="For {{ first_name }}").send_test()
		sent = self.sendmail.call_args.kwargs
		self.assertEqual(sent["recipients"], [frappe.db.get_value("User", "Administrator", "email")])
		self.assertEqual(sent["subject"], "For Administrator")
		self.assertTrue(sent["now"])
		self.assertIsNone(sent["communication"])


class TestChurchEmailPlaceholders(ChurchEmailTestCase):
	def test_a_placeholder_outside_the_persons_names_is_refused(self):
		for message in ("{{ frappe.db.sql('select 1') }}", "{{ doc.name }}", "{{ amount }}"):
			with self.subTest(message), self.assertRaisesRegex(frappe.ValidationError, "first_name"):
				self.make_email(message=message)

	def test_a_message_that_does_not_compile_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be filled in"):
			self.make_email(subject="Hello {{ first_name")

	def test_a_text_is_checked_and_named_by_its_first_words(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Text"):
			self.make_email(channel="Text Message", text_message="Hi {{ frappe }}")
		text = self.make_email(
			channel="Text Message", subject="{{ ignored", text_message="Hi {{ first_name }}"
		)
		self.assertEqual(text.subject, "Hi {{ first_name }}")

	def test_the_preview_shows_the_first_person_it_goes_to_unless_another_is_picked(self):
		email = self.make_email(
			send_to="Group",
			group=self.group.name,
			subject="Hi {{ first_name }}",
			message="<p>{{ last_name }}</p>",
		)
		first, second = sorted([self.member.name, self.inactive.name])

		preview = email.get_preview()
		self.assertEqual((preview["person"], preview["count"]), (first, 2))

		picked = email.get_preview(self.inactive.name)
		self.assertEqual(picked["to"], email_of(self.inactive))
		self.assertEqual(picked["subject"], "Hi Inactive")
		self.assertEqual(picked["message"], "<p>_Test Church Email</p>")

		with self.assertRaisesRegex(frappe.ValidationError, "does not get this message"):
			email.get_preview(self.visitor.name)

	def test_a_name_in_an_html_message_is_escaped(self):
		person = make_person(
			"<b>Bold</b>", "_Test Church Email", emails=[{"email_address": "_test_bold@example.com"}]
		)
		email = self.make_email(
			send_to="Chosen People",
			people=[{"person": person.name}],
			subject="Hi {{ first_name }}",
			message="<p>{{ first_name }}</p>",
		)
		preview = email.get_preview()
		self.assertEqual(preview["subject"], "Hi <b>Bold</b>")
		self.assertEqual(preview["message"], "<p>&lt;b&gt;Bold&lt;/b&gt;</p>")


class TestChurchTextMessage(ChurchEmailTestCase):
	def setUp(self):
		super().setUp()
		self.send_sms = self.start(mock.patch(f"{SENDING}.send_sms", side_effect=log_sms))
		self.start(mock.patch(f"{MODULE}.can_send_texts", return_value=True))
		self.texter = make_person(
			"Texter", "_Test Church Email", membership="Member", phones=[{"phone_number": "+1 555 0101"}]
		)
		self.silent = make_person(
			"Silent", "_Test Church Email", membership="Member", phones=[{"phone_number": "+1 555 0102"}]
		)
		record([self.texter.name], SMS, GIVEN, CHURCH_NEWS)

	def make_text(self, **values):
		return self.make_email(
			channel="Text Message",
			send_to="Chosen People",
			people=[{"person": self.texter.name}, {"person": self.silent.name}],
			text_message="Hi {{ first_name }}",
			**values,
		)

	def test_a_text_goes_only_to_people_who_agreed_to_texts(self):
		text = self.make_text()
		frappe.db.set_value("Church Email", text.name, "status", "Sending")

		deliver_now(text.name)

		self.send_sms.assert_called_once_with(["+1 555 0101"], "Hi Texter", success_msg=False)
		self.sendmail.assert_not_called()
		[copy] = copies_of(text.name)
		self.assertEqual(
			(copy.reference_name, copy.communication_medium, copy.phone_no),
			(self.texter.name, "SMS", "+1 555 0101"),
		)
		self.assertEqual(copy.content, "Hi Texter")
		self.assertEqual(frappe.db.get_value("Church Email", text.name, "recipients"), 1)

	def test_texts_are_refused_until_sms_is_set_up(self):
		with mock.patch(f"{MODULE}.can_send_texts", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "SMS Settings"):
				self.make_text().send()

	def test_a_user_who_may_not_send_texts_is_refused_on_send(self):
		text = self.make_text()
		frappe.set_user(
			ensure_user("_test_church_email_manager@example.com", "Manager", roles=("Church Manager",))
		)
		with self.assertRaisesRegex(frappe.PermissionError, "SMS"):
			text.send()

	def test_a_test_text_goes_to_the_readers_own_mobile(self):
		frappe.db.set_value("User", "Administrator", "mobile_no", "+1 555 0199")
		self.assertEqual(self.make_text().send_test(), "+1 555 0199")
		self.send_sms.assert_called_once_with(["+1 555 0199"], "Hi Administrator", success_msg=False)


class TestChurchEmailPerChurch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Member Status", {"status": "Active"})
		create_communication_purposes()

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_group(self, name, church, people):
		return frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": name,
				"church": church,
				"members": [{"person": person.name} for person in people],
			}
		).insert(ignore_permissions=True)

	def make_church_email(self, church, **values):
		return frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Branch",
				"message": "Hi",
				"church": church,
				**values,
			}
		).insert()

	def test_a_purpose_unsubscribe_reaches_another_churchs_person_in_the_group(self):
		theirs = make_reader("GroupTheirs", church=self.branch_b)
		group = self.make_group("_Test Church Email Mixed Group", self.branch_a, [theirs])
		email = self.make_church_email(
			self.branch_a, send_to="Group", group=group.name, purpose=PASTORAL_CARE
		)
		frappe.db.set_value("Church Email", email.name, "status", "Sending")
		with mock.patch("frappe.sendmail") as sendmail:
			deliver_now(email.name)
		params = sendmail.call_args.kwargs["unsubscribe_params"]

		frappe.set_user("Guest")
		with mock.patch.object(frappe.db, "commit"):
			unsubscribe(email=email_of(theirs), doctype="Church Email", name=email.name, **params)
		frappe.set_user("Administrator")

		self.assertFalse(allowed(theirs.name, EMAIL, PASTORAL_CARE))
		self.assertTrue(allowed(theirs.name, EMAIL, CHURCH_NEWS))

	def test_a_reader_gets_the_saved_messages_people_not_the_ones_they_send(self):
		mine = make_reader("SavedMine", church=self.branch_a)
		theirs = [make_reader(f"Probed{n}", church=self.branch_b) for n in (1, 2)]
		group_b = self.make_group("_Test Church Email Probed Group", self.branch_b, theirs)
		email = self.make_church_email(self.branch_a, send_to="Chosen People", people=[{"person": mine.name}])
		staff = ensure_user("_test_church_email_staff_a@example.com", "StaffA", roles=("Church Staff",))
		make_person("_Test Church Email Staff", "A", church=self.branch_a, user=staff)
		forged = {**email.as_dict(), "send_to": "Group", "group": group_b.name, "people": []}

		frappe.set_user(staff)
		count = call_from_browser("get_recipient_count", forged)
		preview = call_from_browser("get_preview", forged)

		self.assertEqual(count, 1)
		self.assertEqual((preview["count"], preview["person"]), (1, mine.name))

	def test_another_churchs_message_cannot_be_sent_by_naming_my_church(self):
		email = self.make_church_email(self.branch_b, send_after=add_to_date(now_datetime(), hours=1))
		manager = ensure_user(
			"_test_church_email_manager_a@example.com", "ManagerA", roles=("Church Manager",)
		)
		make_person("_Test Church Email Manager", "A", church=self.branch_a, user=manager)
		forged = {**email.as_dict(), "church": self.branch_a}

		frappe.set_user(manager)
		with mock.patch(f"{MODULE}.can_send_email", return_value=True), mock.patch("frappe.enqueue"):
			for method in ("send", "send_test", "unschedule"):
				with self.subTest(method), self.assertRaises(frappe.PermissionError):
					call_from_browser(method, forged)
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Church Email", email.name, "status"), "Draft")

	def test_an_unsubscribe_from_one_church_leaves_the_others_emails_coming(self):
		reader = make_reader("Both", church=self.branch_b)
		set_subscribed(email_of(reader), self.branch_a, False)
		email = frappe.get_doc(
			{"doctype": "Church Email", "subject": "_Test Branch B", "message": "Hi", "church": self.branch_b}
		).insert()
		self.assertIn(email_of(reader), addresses(email))

	def test_a_church_email_goes_only_to_its_own_churchs_people(self):
		mine = make_reader("Mine", church=self.branch_a)
		theirs = make_reader("Theirs", church=self.branch_b)
		email = frappe.get_doc(
			{"doctype": "Church Email", "subject": "_Test Branch", "message": "Hi", "church": self.branch_a}
		).insert()

		recipients = addresses(email)

		self.assertIn(email_of(mine), recipients)
		self.assertNotIn(email_of(theirs), recipients)
		self.assertEqual(email.sending_church, self.branch_a)

	def test_a_smart_list_reaches_only_its_own_churchs_people(self):
		mine = make_reader("ListedMine", church=self.branch_a)
		theirs = make_reader("ListedTheirs", church=self.branch_b)
		smart_list = make_smart_list(
			"_Test Church Email Branch List", [["Person", "last_name", "=", "_Test Church Email"]]
		)
		email = frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Branch List",
				"message": "Hi",
				"church": self.branch_a,
				"send_to": "Smart List",
				"smart_list": smart_list.name,
			}
		).insert()

		recipients = addresses(email)

		self.assertIn(email_of(mine), recipients)
		self.assertNotIn(email_of(theirs), recipients)

	def test_another_churchs_person_cannot_be_chosen(self):
		theirs = make_reader("ChosenTheirs", church=self.branch_b)
		email = frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Branch Chosen",
				"message": "Hi",
				"church": self.branch_a,
				"send_to": "Chosen People",
				"people": [{"person": theirs.name}],
			}
		)
		with self.assertRaisesRegex(frappe.ValidationError, "belong to another church"):
			email.insert()


class TestChurchEmailHouseholds(RollbackEachTest):
	"""A group of church A holds a father and a single woman. The father's family holds his wife, a son of 10, his
	mother of 70, his father who died, and a lodger of church B."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Member Status", {"status": "Active"})
		ensure("Life Event Type", {"type": "Death"})
		create_communication_purposes()

		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Church Email Household", "church": cls.church}
		).insert(ignore_permissions=True)
		cls.father = make_primary_contact(make_reader("HouseFather", church=cls.church, family=family.name))
		cls.mother = make_reader(
			"HouseMother",
			church=cls.church,
			family=family.name,
			gender="Female",
			marital_status="Married",
			spouse=cls.father.name,
		)
		cls.son = make_reader("HouseSon", church=cls.church, family=family.name, life_events=[born(10)])
		cls.gran = make_reader("HouseGran", church=cls.church, family=family.name, life_events=[born(70)])
		cls.late = make_reader(
			"HouseLate",
			church=cls.church,
			family=family.name,
			life_events=[born(75), {"event_type": "Death", "date": "2024-01-01"}],
		)
		cls.lodger = make_reader(
			"HouseLodger", church=other_church, family=family.name, life_events=[born(40)]
		)
		label(
			family.name,
			{
				cls.son.name: "Son",
				cls.gran.name: "Mother",
				cls.late.name: "Father",
			},
		)
		cls.single = make_reader("HouseSingle", church=cls.church)
		cls.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Church Email Household Group",
				"church": cls.church,
				"members": [{"person": cls.father.name}, {"person": cls.single.name}],
			}
		).insert(ignore_permissions=True)

	def make_email(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Household",
				"message": "Hi",
				"church": self.church,
				"send_to": "Group",
				"group": self.group.name,
				**values,
			}
		).insert()

	def assertReaches(self, email, people):
		self.assertEqual(sorted(addresses(email)), sorted(email_of(person) for person in people))

	def test_the_adults_of_each_members_household_get_it_once_and_count(self):
		email = self.make_email(include_household=1, household_roles="Adults")

		self.assertReaches(email, [self.father, self.mother, self.single])
		self.assertEqual(email.get_recipient_count(), 3)

	def test_everyone_adds_the_living_household_of_the_messages_church(self):
		self.assertReaches(
			self.make_email(include_household=1),
			[self.father, self.mother, self.son, self.gran, self.single],
		)

	def test_other_adults_come_with_the_adults_when_chosen(self):
		self.assertReaches(
			self.make_email(include_household=1, household_roles="Adults and Other Adults"),
			[self.father, self.mother, self.gran, self.single],
		)

	def test_an_added_adult_who_withdrew_for_the_purpose_gets_nothing(self):
		record([self.mother.name], EMAIL, WITHDRAWN, CHURCH_NEWS)

		self.assertReaches(
			self.make_email(include_household=1, household_roles="Adults"), [self.father, self.single]
		)

	def test_without_households_only_the_group_gets_it(self):
		self.assertReaches(self.make_email(), [self.father, self.single])
