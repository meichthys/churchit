# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.email.receive import InboundMail
from frappe.utils import add_days, now_datetime

from churchit.church_communications.bounces import RECENT_DAYS, bounced_addresses, record_bounce
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, force_single_church, make_person

CHURCH_INBOX = frappe._dict({"email_id": "church@example.org"})

# Reports as Postfix, Gmail and Microsoft 365 send them. ORIGINAL_ID stands for the
# Message-ID of the church's email, which Gmail and Microsoft 365 quote in In-Reply-To.
POSTFIX_FAILED = b"""Return-Path: <>
Date: Tue, 20 Oct 2026 10:00:01 +0000 (UTC)
From: MAILER-DAEMON@mail.example.org (Mail Delivery System)
Subject: Undelivered Mail Returned to Sender
To: church@example.org
Auto-Submitted: auto-replied
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status;
	boundary="4F2A31C0A3B.1760954401/mail.example.org"
Content-Transfer-Encoding: 8bit
Message-Id: <20261020100001.4F2A31C0A3B@mail.example.org>

This is a MIME-encapsulated message.

--4F2A31C0A3B.1760954401/mail.example.org
Content-Description: Notification
Content-Type: text/plain; charset=us-ascii

This is the mail system at host mail.example.org.

I'm sorry to have to inform you that your message could not
be delivered to one or more recipients. It's attached below.

For further assistance, please send mail to postmaster.

If you do so, please include this problem report. You can
delete your own text from the attached returned message.

                   The mail system

<Gone.Person@example.com>: host mx.example.com[192.0.2.10] said: 550 5.1.1
    <Gone.Person@example.com>: Recipient address rejected: User unknown in
    virtual mailbox table (in reply to RCPT TO command)

--4F2A31C0A3B.1760954401/mail.example.org
Content-Description: Delivery report
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.example.org
X-Postfix-Queue-ID: 4F2A31C0A3B
X-Postfix-Sender: rfc822; church@example.org
Arrival-Date: Tue, 20 Oct 2026 09:59:58 +0000 (UTC)

Final-Recipient: rfc822; Gone.Person@example.com
Original-Recipient: rfc822;Gone.Person@example.com
Action: failed
Status: 5.1.1
Remote-MTA: dns; mx.example.com
Diagnostic-Code: smtp; 550 5.1.1 <Gone.Person@example.com>: Recipient address
    rejected: User unknown in virtual mailbox table

--4F2A31C0A3B.1760954401/mail.example.org
Content-Description: Undelivered Message
Content-Type: message/rfc822
Content-Transfer-Encoding: 8bit

Return-Path: <church@example.org>
Message-Id: <original-postfix@example.org>
Date: Tue, 20 Oct 2026 09:59:58 +0000
From: Grace Church <church@example.org>
To: Gone.Person@example.com
Subject: Church News
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8

Write to <office@example.org>: we read every message.

--4F2A31C0A3B.1760954401/mail.example.org--
"""

POSTFIX_DELAYED = b"""Return-Path: <>
Date: Tue, 20 Oct 2026 10:00:01 +0000 (UTC)
From: MAILER-DAEMON@mail.example.org (Mail Delivery System)
Subject: Delayed Mail (still being retried)
To: church@example.org
Auto-Submitted: auto-replied
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status;
	boundary="5A1B2C3D4E.1760954401/mail.example.org"
Message-Id: <20261020100001.5A1B2C3D4E@mail.example.org>

--5A1B2C3D4E.1760954401/mail.example.org
Content-Description: Notification
Content-Type: text/plain; charset=us-ascii

This is the mail system at host mail.example.org.

####################################################################
# THIS IS A WARNING ONLY.  YOU DO NOT NEED TO RESEND YOUR MESSAGE. #
####################################################################

Your message could not be delivered for 4.0 hours.
It will be retried until it is 5.0 days old.

                   The mail system

<gone.person@example.com>: connect to mx.example.com[192.0.2.10]:25: Connection
    timed out

--5A1B2C3D4E.1760954401/mail.example.org
Content-Description: Delivery report
Content-Type: message/delivery-status

Reporting-MTA: dns; mail.example.org
Arrival-Date: Tue, 20 Oct 2026 06:00:00 +0000 (UTC)

Final-Recipient: rfc822; gone.person@example.com
Action: delayed
Status: 4.4.1
Diagnostic-Code: X-Postfix; connect to mx.example.com[192.0.2.10]:25: Connection
    timed out
Will-Retry-Until: Sun, 25 Oct 2026 06:00:00 +0000 (UTC)

--5A1B2C3D4E.1760954401/mail.example.org
Content-Description: Undelivered Message Headers
Content-Type: text/rfc822-headers

From: Grace Church <church@example.org>
To: gone.person@example.com
Subject: Church News

--5A1B2C3D4E.1760954401/mail.example.org--
"""

GMAIL_FAILED = b"""Return-Path: <>
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: church@example.org
Auto-Submitted: auto-replied
Subject: Delivery Status Notification (Failure)
References: <ORIGINAL_ID>
In-Reply-To: <ORIGINAL_ID>
X-Failed-Recipients: gone.person@gmail.com
Message-ID: <6512c0de.050a0220.failure@mx.google.com>
Date: Tue, 20 Oct 2026 03:00:02 -0700 (PDT)
MIME-Version: 1.0
Content-Type: multipart/report; boundary="000000000000a1b2c3"; report-type=delivery-status

--000000000000a1b2c3
Content-Type: multipart/alternative; boundary="000000000000d4e5f6"

--000000000000d4e5f6
Content-Type: text/plain; charset="UTF-8"


** Address not found **

Your message wasn't delivered to gone.person@gmail.com because the address couldn't be found, or is unable to receive mail.

Learn more here: https://support.google.com/mail/?p=NoSuchUser

The response was:

The email account that you tried to reach does not exist. Please try double-checking the recipient's email address for typos or unnecessary spaces.

--000000000000d4e5f6
Content-Type: text/html; charset="UTF-8"

<html><body><h2>Address not found</h2><p>Your message wasn't delivered to <b>gone.person@gmail.com</b> because the address couldn't be found, or is unable to receive mail.</p></body></html>
--000000000000d4e5f6--

--000000000000a1b2c3
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com
Arrival-Date: Tue, 20 Oct 2026 03:00:01 -0700 (PDT)
X-Original-Message-ID: <ORIGINAL_ID>

Final-Recipient: rfc822; gone.person@gmail.com
Action: failed
Status: 5.1.1
Remote-MTA: dns; gmail-smtp-in.l.google.com. (2607:f8b0:4864:20::42a, the server for the domain gmail.com.)
Diagnostic-Code: smtp; 550-5.1.1 The email account that you tried to reach does not exist.
Last-Attempt-Date: Tue, 20 Oct 2026 03:00:02 -0700 (PDT)

--000000000000a1b2c3
Content-Type: message/rfc822

From: Grace Church <church@example.org>
To: gone.person@gmail.com
Subject: Church News
Message-ID: <ORIGINAL_ID>
Date: Tue, 20 Oct 2026 10:00:00 +0000
Content-Type: text/plain; charset=utf-8

Hello from church.

--000000000000a1b2c3--
"""

GMAIL_DELAYED = b"""Return-Path: <>
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: church@example.org
Auto-Submitted: auto-replied
Subject: Delivery Status Notification (Delay)
References: <ORIGINAL_ID>
In-Reply-To: <ORIGINAL_ID>
Message-ID: <6512c0de.050a0220.delay@mx.google.com>
Date: Tue, 20 Oct 2026 03:00:02 -0700 (PDT)
MIME-Version: 1.0
Content-Type: multipart/report; boundary="000000000000b2c3d4"; report-type=delivery-status

--000000000000b2c3d4
Content-Type: text/plain; charset="UTF-8"

** Delivery incomplete **

There was a temporary problem delivering your message to gone.person@gmail.com. Gmail will retry for 47 more hours. You'll be notified if the delivery fails permanently.

The response was:

The recipient server did not accept our requests to connect. [mx.example.com. 192.0.2.10: timed out]

--000000000000b2c3d4
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com

Final-Recipient: rfc822; gone.person@gmail.com
Action: delayed
Status: 4.4.1
Will-Retry-Until: Thu, 22 Oct 2026 03:00:02 -0700 (PDT)

--000000000000b2c3d4--
"""

MICROSOFT_FAILED = b"""From: Microsoft Outlook <postmaster@grace.onmicrosoft.com>
To: <church@example.org>
Date: Tue, 20 Oct 2026 10:00:03 +0000
Content-Type: multipart/report; report-type=delivery-status;
	boundary="_000_a1b2c3d4ndr_"
X-MS-Exchange-Message-Is-Ndr:
Content-Language: en-US
Message-ID: <a1b2c3d4-ndr@BN8PR04MB1234.namprd04.prod.outlook.com>
In-Reply-To: <ORIGINAL_ID>
References: <ORIGINAL_ID>
Thread-Topic: Church News
Subject: Undeliverable: Church News
Auto-Submitted: auto-replied
MIME-Version: 1.0

--_000_a1b2c3d4ndr_
Content-Type: multipart/alternative;
	boundary="_002_a1b2c3d4ndr_"

--_002_a1b2c3d4ndr_
Content-Type: text/plain; charset="us-ascii"
Content-Transfer-Encoding: quoted-printable

Your message to moved.away@example.net couldn't be delivered.
moved.away wasn't found at example.net.

church             Office 365      moved.away
Action Required                    Recipient
Unknown To address

How to Fix It
The address may be misspelled or may not exist. Try one or more of the foll=
owing:
- Retype the recipient's address, then resend the message.

More Info for Email Admins
Status code: 550 5.1.10

Original Message Details
Created Date:    10/20/2026 10:00:01 AM
Sender Address:    church@example.org
Recipient Address:    moved.away@example.net
Subject:    Church News

Error Details
Reported error:    550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient not=
 found by SMTP address lookup
DSN generated by:    BN8PR04MB1234.namprd04.prod.outlook.com

--_002_a1b2c3d4ndr_
Content-Type: text/html; charset="us-ascii"
Content-Transfer-Encoding: quoted-printable

<html><body><p><b>Your message to <a href=3D"mailto:moved.away@example.net">=
moved.away@example.net</a> couldn't be delivered.</b></p><p>Status code: 550=
 5.1.10</p></body></html>
--_002_a1b2c3d4ndr_--

--_000_a1b2c3d4ndr_
Content-Type: message/delivery-status

Reporting-MTA: dns;BN8PR04MB1234.namprd04.prod.outlook.com
Arrival-Date: Tue, 20 Oct 2026 10:00:01 +0000

Final-Recipient: rfc822;moved.away@example.net
Action: failed
Status: 5.1.10
Diagnostic-Code: smtp;550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient not found by SMTP address lookup

--_000_a1b2c3d4ndr_
Content-Type: message/rfc822

From: Grace Church <church@example.org>
To: <moved.away@example.net>
Subject: Church News
Message-ID: <ORIGINAL_ID>
Date: Tue, 20 Oct 2026 10:00:00 +0000
MIME-Version: 1.0
Content-Type: text/plain

--_000_a1b2c3d4ndr_--
"""

MEMBER_REPLY = b"""From: Ruth Member <member@example.com>
To: church@example.org
Subject: Re: Church News
In-Reply-To: <ORIGINAL_ID>
Message-ID: <reply-1@example.com>
Date: Tue, 20 Oct 2026 11:00:00 +0000
Content-Type: text/plain; charset=utf-8

Thank you! My brother says your message wasn't delivered to gone.person@gmail.com, error 5.1.1.
"""

HTML_ONLY_FAILED = b"""From: postmaster@mail.example.org
To: church@example.org
Subject: Undeliverable: Church News
Message-ID: <html-only-1@mail.example.org>
Date: Tue, 20 Oct 2026 10:00:00 +0000
Content-Type: text/html; charset=utf-8

<p>Your message to <a href="mailto:moved.away@example.net">moved.away@example.net</a> couldn't be delivered.</p>
"""


def receive(raw: bytes, original_id: str = "") -> str:
	"""Pass *raw* through Frappe's own inbound mail handling and return the Communication's name."""
	return InboundMail(raw.replace(b"ORIGINAL_ID", original_id.encode()), CHURCH_INBOX).process().name


def mail_sent_to(*recipients: str, days_ago: int = 0):
	"""Keep an Email Queue the site sent to *recipients* *days_ago* days back, as Frappe does."""
	queue = frappe.get_doc(
		{
			"doctype": "Email Queue",
			"status": "Sent",
			"message": "Church News",
			"recipients": [{"recipient": recipient, "status": "Sent"} for recipient in recipients],
		}
	).insert(ignore_permissions=True)
	if days_ago:
		sent_on = add_days(now_datetime(), -days_ago)
		frappe.db.set_value("Email Queue Recipient", {"parent": queue.name}, "creation", sent_on)


def is_bounced(parenttype, parent):
	return frappe.db.get_value("Email Address", {"parenttype": parenttype, "parent": parent}, "is_bounced")


class TestRecordBounce(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()

	def setUp(self):
		super().setUp()
		mail_sent_to(
			"Gone Person <gone.person@example.com>",
			"gone.person@gmail.com",
			"moved.away@example.net",
			"office@example.org",
			"church@example.org",
		)
		self.original_id = f"{frappe.generate_hash()}@{frappe.local.site}"
		self.sent = (
			frappe.get_doc(
				{
					"doctype": "Communication",
					"communication_type": "Communication",
					"communication_medium": "Email",
					"sent_or_received": "Sent",
					"subject": "Church News",
					"recipients": "gone.person@gmail.com",
					"message_id": self.original_id,
					"delivery_status": "Sent",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def delivery_status(self):
		return frappe.db.get_value("Communication", self.sent, "delivery_status")

	def test_a_postfix_report_marks_the_address_on_every_record_holding_it(self):
		owner = make_person("_Test Bounce", "Owner", emails=[{"email_address": "gone.person@example.com"}])
		sharer = make_person(
			"_Test Bounce",
			"Sharer",
			emails=[
				{
					"email_address": "gone.person@example.com",
					"shared_from": owner.name,
					"shared_from_type": "Person",
				}
			],
		)
		family = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": "_Test Bounce Family",
				"emails": [{"email_address": "gone.person@example.com"}],
			}
		).insert(ignore_permissions=True)
		office = make_person("_Test Bounce", "Office", emails=[{"email_address": "office@example.org"}])
		modified = frappe.db.get_value("Person", owner.name, "modified")

		receive(POSTFIX_FAILED)

		self.assertEqual(
			[
				is_bounced("Person", owner.name),
				is_bounced("Person", sharer.name),
				is_bounced("Family", family.name),
			],
			[1, 1, 1],
		)
		self.assertEqual(
			is_bounced("Person", office.name), 0, "an address in the returned message is not a failure"
		)
		self.assertNotEqual(frappe.db.get_value("Person", owner.name, "modified"), modified)
		self.assertNotEqual(frappe.db.get_value("Family", family.name, "modified"), family.modified)
		self.assertEqual(bounced_addresses(["Gone.Person@example.com"]), {"Gone.Person@example.com"})
		self.assertEqual(
			self.delivery_status(), "Sent", "a Postfix report does not say which email it answers"
		)

	def test_a_form_opened_before_the_bounce_cannot_untick_it(self):
		person = make_person("_Test Bounce", "Stale", emails=[{"email_address": "gone.person@example.com"}])
		opened = frappe.get_doc("Person", person.name)

		receive(POSTFIX_FAILED)

		opened.emails[0].is_bounced = 0
		with self.assertRaises(frappe.TimestampMismatchError):
			opened.save(ignore_permissions=True)
		self.assertEqual(is_bounced("Person", person.name), 1)

	def test_a_postfix_report_without_a_status_code_counts_by_its_words(self):
		person = make_person("_Test Bounce", "Domain", emails=[{"email_address": "gone.person@example.com"}])

		receive(POSTFIX_FAILED.replace(b"said: 550 5.1.1", b"said: Host or domain name not found"))

		self.assertEqual(is_bounced("Person", person.name), 1)

	def test_a_gmail_report_marks_the_address_and_the_email_it_answers(self):
		person = make_person("_Test Bounce", "Gmail", emails=[{"email_address": "gone.person@gmail.com"}])

		receive(GMAIL_FAILED, self.original_id)

		self.assertEqual(is_bounced("Person", person.name), 1)
		self.assertEqual(self.delivery_status(), "Bounced")

	def test_a_microsoft_365_report_marks_the_address_and_the_email_it_answers(self):
		person = make_person(
			"_Test Bounce", "Microsoft", emails=[{"email_address": "moved.away@example.net"}]
		)
		church = make_person("_Test Bounce", "Church", emails=[{"email_address": "church@example.org"}])

		receive(MICROSOFT_FAILED, self.original_id)

		self.assertEqual(is_bounced("Person", person.name), 1)
		self.assertEqual(is_bounced("Person", church.name), 0, "the sender address is not a failure")
		self.assertEqual(self.delivery_status(), "Bounced")

	def test_a_report_in_html_alone_is_read_too(self):
		person = make_person("_Test Bounce", "Html", emails=[{"email_address": "moved.away@example.net"}])

		receive(HTML_ONLY_FAILED)

		self.assertEqual(is_bounced("Person", person.name), 1)

	def test_a_report_marks_only_addresses_the_site_mailed_lately(self):
		people = [
			make_person("_Test Bounce", "Mailed", emails=[{"email_address": "gone.person@example.com"}]),
			make_person("_Test Bounce", "Never", emails=[{"email_address": "never.mailed@example.com"}]),
			make_person("_Test Bounce", "Old", emails=[{"email_address": "long.ago@example.com"}]),
		]
		mail_sent_to("long.ago@example.com", days_ago=RECENT_DAYS + 1)
		forged = b"\n".join(
			f"<{address}>: host mx.example.com said: 550 5.1.1 User unknown".encode()
			for address in ("never.mailed@example.com", "long.ago@example.com", "gone.person@example.com")
		)

		receive(
			POSTFIX_FAILED.replace(b"<Gone.Person@example.com>: host", forged + b"\n<x@example.com>: host")
		)

		self.assertEqual([is_bounced("Person", person.name) for person in people], [1, 0, 0])

	def test_a_policy_block_or_a_full_mailbox_marks_nothing(self):
		person = make_person("_Test Bounce", "Blocked", emails=[{"email_address": "gone.person@example.com"}])

		for code in ("5.7.1", "5.7.26", "5.2.2"):
			with self.subTest(code):
				receive(
					POSTFIX_FAILED.replace(b"said: 550 5.1.1", f"said: 550 {code}".encode()).replace(
						b"4F2A31C0A3B@mail", f"{code}@mail".encode()
					)
				)
				self.assertEqual(is_bounced("Person", person.name), 0)

	def test_a_delay_warning_changes_nothing(self):
		people = [
			make_person("_Test Bounce", "Delayed", emails=[{"email_address": "gone.person@example.com"}]),
			make_person("_Test Bounce", "Waiting", emails=[{"email_address": "gone.person@gmail.com"}]),
		]

		receive(POSTFIX_DELAYED)
		receive(GMAIL_DELAYED, self.original_id)

		self.assertEqual([is_bounced("Person", person.name) for person in people], [0, 0])
		self.assertEqual(self.delivery_status(), "Sent")

	def test_a_reply_from_a_person_changes_nothing(self):
		person = make_person("_Test Bounce", "Replied", emails=[{"email_address": "gone.person@gmail.com"}])

		receive(MEMBER_REPLY, self.original_id)

		self.assertEqual(is_bounced("Person", person.name), 0)
		self.assertEqual(self.delivery_status(), "Sent")

	def test_odd_mail_from_a_mail_system_is_skipped_quietly(self):
		person = make_person("_Test Bounce", "Odd", emails=[{"email_address": "gone.person@example.com"}])
		odd_mail = (
			b"From: MAILER-DAEMON@mail.example.org\nSubject: Undelivered Mail\nMessage-ID: <odd-1@x>\n\n",
			b"From: postmaster@mail.example.org\nMessage-ID: <odd-2@x>\nContent-Type: multipart/report;"
			b' boundary="b"\n\n--b\nContent-Type: message/delivery-status\n\nAction: failed\nStatus: 5.1.1\n\n--b--\n',
			b"From: mailer-daemon@mail.example.org\nMessage-ID: <odd-3@x>\n\n\xff\xfe 5.1.1 <not an address>:\n",
		)

		for raw in odd_mail:
			receive(raw)
		record_bounce(frappe._dict(sent_or_received="Received", communication_medium="Email"))
		record_bounce(
			frappe._dict(sent_or_received="Received", communication_medium="Email", sender="postmaster@x.org")
		)

		self.assertEqual(is_bounced("Person", person.name), 0)

	def test_a_sent_email_is_never_read_as_a_report(self):
		person = make_person("_Test Bounce", "Sent", emails=[{"email_address": "gone.person@example.com"}])

		frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_medium": "Email",
				"sent_or_received": "Sent",
				"sender": "postmaster@example.org",
				"subject": "Undelivered Mail Returned to Sender",
				"text_content": "<gone.person@example.com>: 550 5.1.1 User unknown",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(is_bounced("Person", person.name), 0)
