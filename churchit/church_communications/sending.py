# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Sending a message about a record: a copy for each person, filled in for them and kept on their timeline.

A Church Email goes out through `Delivery`; any other record sends with `send`, by email, text or push
notification.

Placeholders are filled by a sandboxed Jinja environment that holds only the person's names.
Church Managers write Church Emails but not Email Templates, and Frappe's own Jinja
environment would hand them frappe.db.
"""

from typing import NamedTuple

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import send_sms, validate_receiver_nos
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce
from frappe.utils import create_batch, escape_html, get_formatted_email, now_datetime, validate_email_address
from jinja2 import StrictUndefined, TemplateError, meta, nodes
from jinja2.sandbox import SandboxedEnvironment
from requests import HTTPError

from churchit.church_communications.bounces import bounced_addresses
from churchit.church_communications.consent import allowed_people
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	PUSH,
	SMS,
)
from churchit.church_communications.newsletter import UNSUBSCRIBE_METHOD, email_church, unsubscribed_emails
from churchit.church_communications.push import SUBSCRIPTION, is_push_on, send_push
from churchit.church_scope import default_church, document_church, session_person
from churchit.contacts import (
	EMAIL_DOCTYPE,
	PHONE_DOCTYPE,
	contact_key,
	get_primary_emails,
	get_primary_phone,
	get_primary_values,
)

PLACEHOLDERS = ("first_name", "last_name", "display_name", "full_name")
# The same names again, as Frappe's Email Templates write them: {{ doc.first_name }}.
DOCUMENT = "doc"

# An email copy waits in Frappe's Email Queue until the commit, so a hundred are committed at a time.
EMAILS_PER_COMMIT = 100
# A text leaves at once, so each is committed as soon as it is sent.
TEXTS_PER_COMMIT = 1

# The Communication delivery statuses a text copy gets, the same ones Frappe gives an email copy.
SENT = "Sent"
ERROR = "Error"
# What a gateway answers when it refuses one text, such as a number that is not valid or that replied
# STOP. Any other failure stops the delivery, so it goes on once the gateway works again.
REFUSED_STATUSES = (400, 422)

# Communication has no medium for a push notification.
MEDIUMS = {EMAIL: "Email", SMS: "SMS", PUSH: "Other"}

TEXT = SandboxedEnvironment(undefined=StrictUndefined)
HTML = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True)


class Recipient(NamedTuple):
	person: str
	address: str


class Sender:
	"""Copies of one message about *source*, each kept on its person's timeline and linked to *source*.

	*church* is the church the emails go out in, whose unsubscribe link they carry with *purpose*.
	"""

	def __init__(
		self,
		source: Document,
		channel: str,
		church: str | None,
		purpose: str | None,
		key: str = "",
		attachments: list[dict] | None = None,
		email_template: str | None = None,
		url: str | None = None,
	):
		self.source = source
		self.channel = channel
		self.church = church
		self.purpose = purpose
		self.key = key
		self.attachments = attachments or []
		self.email_template = email_template
		self.url = url

	def deliver(self, recipient: Recipient, copy: frappe._dict) -> bool:
		"""Send *recipient* their *copy* and return whether it left.

		A text that did not leave, or a push notification no browser took, is marked Error.
		A push notification opens *url*, else the source's desk form.
		"""
		communication = self.record(recipient, copy)
		if self.channel == EMAIL:
			self.send_email(recipient.address, copy, communication, person=recipient.person)
			return True

		if self.channel == PUSH:
			is_sent = bool(
				send_push(recipient.address, copy.subject, copy.text, self.url or self.source.get_url())
			)
		else:
			is_sent = send_text(recipient.address, copy.text)
		frappe.db.set_value(
			"Communication",
			communication,
			"delivery_status",
			SENT if is_sent else ERROR,
			update_modified=False,
		)
		return is_sent

	def record(self, recipient: Recipient, copy: frappe._dict) -> str:
		"""Keep the copy as a Communication on the person's timeline, linked to the source."""
		is_plain_text = self.channel != EMAIL
		communication = frappe.get_doc(
			{
				"doctype": "Communication",
				"communication_type": "Communication",
				"communication_medium": MEDIUMS[self.channel],
				"sent_or_received": "Sent",
				"communication_date": now_datetime(),
				"sender": get_formatted_email(frappe.session.user),
				"subject": copy.subject,
				"content": escape_html(copy.text).replace("\n", "<br>") if is_plain_text else copy.message,
				"phone_no": recipient.address if self.channel == SMS else None,
				"recipients": None if is_plain_text else recipient.address,
				"has_attachment": int(bool(self.attachments) and not is_plain_text),
				"email_template": self.email_template,
				"send_key": self.key,
				"reference_doctype": "Person",
				"reference_name": recipient.person,
			}
		)
		communication.add_link(self.source.doctype, self.source.name)
		# The copy is kept as it was sent, without the sender's signature that Frappe would add.
		communication.flags.skip_add_signature = True
		return communication.insert(ignore_permissions=True).name

	def send_email(
		self,
		address: str,
		copy: frappe._dict,
		communication: str | None = None,
		now: bool = False,
		person: str | None = None,
	):
		"""Queue *copy* for *address*, with an unsubscribe link that names *person*, the one it is for."""
		unsubscribe_params = {"church": self.church, "purpose": self.purpose}
		if person:
			unsubscribe_params["person"] = person
		queued = frappe.sendmail(
			recipients=[address],
			subject=copy.subject,
			message=copy.message,
			attachments=self.attachments,
			reference_doctype=self.source.doctype,
			reference_name=self.source.name,
			communication=communication,
			unsubscribe_method=UNSUBSCRIBE_METHOD,
			unsubscribe_params=unsubscribe_params,
			unsubscribe_message=_("Unsubscribe"),
			send_priority=0,
			now=now,
		)
		if not queued:
			frappe.throw(_("The email to {0} could not be queued. The Error Log says why.").format(address))


class Delivery(Sender):
	"""One Church Email on its way: each recipient gets a copy filled in for them, kept on their timeline."""

	def __init__(self, email: Document):
		super().__init__(
			email,
			email.consent_channel,
			email.sending_church,
			email.purpose,
			attachments=email.get_attachments(),
		)
		self.email = email

	def send_all(self) -> None:
		"""Send a copy to each recipient who has none yet.

		Each batch is committed, so a delivery that stops loses nothing and a rerun sends nobody a second copy.
		A copy that failed counts as handled too, so it is not sent again either.
		"""
		size = TEXTS_PER_COMMIT if self.email.is_text_message else EMAILS_PER_COMMIT
		for recipients in create_batch(self.email.get_recipients(), size):
			# A second worker on the same email waits here, then finds these copies sent.
			frappe.db.get_value(self.email.doctype, self.email.name, "name", for_update=True)
			handled = get_people_sent(
				self.email.name, [recipient.person for recipient in recipients], include_failed=True
			)
			waiting = [recipient for recipient in recipients if recipient.person not in handled]
			values = get_person_values([recipient.person for recipient in waiting])
			sent = sum(self.send_copy(recipient, values[recipient.person]) for recipient in waiting)
			# Saving the count also moves `modified`, which tells the stalled retry this delivery is alive.
			self.email.db_set("recipients", (self.email.recipients or 0) + sent)
			frappe.db.commit()

	def send_copy(self, recipient: Recipient, values: dict) -> bool:
		"""Send *recipient* their copy and return whether it left. A text that did not leave is marked Error."""
		return self.deliver(recipient, self.email.get_copy(values))

	def send_test(self) -> str:
		"""Send the reader a copy at once, filled in with their own name, and return where it went."""
		person = session_person()
		values = get_person_values([person])[person] if person else get_user_values(frappe.session.user)
		copy = self.email.get_copy(values)
		if self.email.is_text_message:
			number = get_own_number(person)
			send_sms([number], copy.text, success_msg=False)
			return number
		address = frappe.db.get_value("User", frappe.session.user, "email")
		self.send_email(address, copy, now=True)
		return address


def send(
	people: list[str],
	channel: str,
	purpose: str | None,
	source: Document,
	*,
	key: str = "",
	church: str | None = None,
	template: str | None = None,
	subject: str = "",
	message: str = "",
	text: str = "",
	context: dict | None = None,
	url: str | None = None,
) -> set[str]:
	"""Send each of *people* who allows *channel* for *purpose* one copy about *source*, once for each *key*.

	*channel* is EMAIL, SMS or PUSH. With *template* (an Email Template) the subject and message come from it.
	A push notification has *subject* as its title and *text* as its body, and opens *url*, a page of this site.
	Without *url* it opens the source's desk form, which members with no desk access cannot see.
	*context* adds placeholders to the person's names. Returns the people whose copy left; the caller commits.
	A text leaves at once, so a caller that texts many people calls this once per person and commits after
	each, as `Delivery.send_all` does. Otherwise a rollback forgets texts that left, and a rerun repeats them.
	Push notifications and emails leave after the commit.
	"""
	context = context or {}
	if channel not in (EMAIL, SMS, PUSH):
		frappe.throw(_("A message goes by {0}, {1} or {2}, not {3}.").format(EMAIL, SMS, PUSH, channel))
	if channel == PUSH and not text:
		frappe.throw(_("A push notification needs a text."))
	if source is None:
		frappe.throw(_("A message needs the saved record it is about."))
	if purpose and not frappe.db.exists("Communication Purpose", purpose):
		frappe.throw(_("Communication Purpose {0} does not exist.").format(purpose))
	if template:
		email_template = frappe.get_doc("Email Template", template)
		subject = email_template.subject
		message = email_template.response_html if email_template.use_html else email_template.response
	for label, content in ((_("Subject"), subject), (_("Message"), message), (_("Text"), text)):
		check_placeholders(content, label, extra=tuple(context))
	if not people:
		return set()

	# A second sender for the same source waits here, then finds these copies sent.
	if not frappe.db.get_value(source.doctype, source.name, "name", for_update=True):
		frappe.throw(_("A message needs the saved record it is about."))
	church = church or document_church(source) or default_church()
	recipients = get_recipients(people, channel, purpose, church)
	handled = get_people_sent(source.name, people, True, doctype=source.doctype, key=key)
	waiting = [recipient for recipient in recipients if recipient.person not in handled]
	values = get_person_values([recipient.person for recipient in waiting])
	sender = Sender(source, channel, email_church(church), purpose, key=key, email_template=template, url=url)
	return {
		recipient.person
		for recipient in waiting
		if sender.deliver(
			recipient, get_copy(channel, {**values[recipient.person], **context}, subject, message, text)
		)
	}


def get_copy(
	channel: str, values: dict, subject: str = "", message: str = "", text: str = ""
) -> frappe._dict:
	"""A message filled in with one person's placeholder *values*.

	A text, a push notification's title (*subject*) and text, or an email's subject and message.
	"""
	if channel == SMS:
		return frappe._dict(text=render(text, values))
	if channel == PUSH:
		return frappe._dict(subject=render(subject, values), text=render(text, values))
	return frappe._dict(subject=render(subject, values), message=render(message, values, html=True))


def render(source: str | None, values: dict, html: bool = False) -> str:
	"""*source* with its placeholders filled in from *values*. In an HTML message the names are escaped."""
	return (HTML if html else TEXT).from_string(source or "").render(values)


def check_placeholders(source: str | None, label: str, extra: tuple[str, ...] = ()) -> None:
	"""Refuse *source* unless it compiles and uses only the person placeholders and the *extra* names."""
	if not source:
		return
	try:
		unknown = get_unknown_names(TEXT.parse(source), extra)
		if not unknown:
			render(
				source,
				{**get_values({field: field for field in PLACEHOLDERS}), **{name: name for name in extra}},
			)
	except TemplateError as error:
		frappe.throw(_("{0} cannot be filled in for each person: {1}").format(label, error.message))
	if unknown:
		frappe.throw(
			_(
				"{0} uses {1}, which cannot be filled in for each person. Use only these placeholders: {2}."
			).format(
				label,
				", ".join(f"{{{{ {name} }}}}" for name in sorted(unknown)),
				", ".join(f"{{{{ {field} }}}}" for field in (*PLACEHOLDERS, *extra)),
			)
		)


def get_unknown_names(template: nodes.Template, extra: tuple[str, ...] = ()) -> set[str]:
	"""The names *template* reads that are not placeholders or *extra* names, `doc.<name>` included."""
	names = meta.find_undeclared_variables(template) - {*PLACEHOLDERS, *extra, DOCUMENT}
	fields = {
		f"{DOCUMENT}.{node.attr}"
		for node in template.find_all(nodes.Getattr)
		if isinstance(node.node, nodes.Name) and node.node.name == DOCUMENT and node.attr not in PLACEHOLDERS
	}
	return names | fields


def get_values(names: dict) -> dict:
	"""The placeholders of one person, each at the top and under `doc`, blank where not on file."""
	values = {field: names.get(field) or "" for field in PLACEHOLDERS}
	return {**values, DOCUMENT: values}


def get_person_values(people: list[str]) -> dict[str, dict]:
	"""The placeholders of each of *people*."""
	if not people:
		return {}
	# church-scope: the names of people already chosen as recipients, read by name
	rows = frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", *PLACEHOLDERS])
	return {row.name: get_values(row) for row in rows}


def get_user_values(user: str) -> dict:
	"""The placeholders of a login with no Person, for a test sent to them."""
	names = frappe.db.get_value("User", user, ["first_name", "last_name", "full_name"], as_dict=True)
	return get_values({**names, "display_name": names.full_name})


def get_own_number(person: str | None) -> str:
	"""The reader's mobile number, else their Person's primary phone, for a test text."""
	number = frappe.db.get_value("User", frappe.session.user, "mobile_no") or (
		person and get_primary_phone("Person", person)
	)
	if not number:
		frappe.throw(_("Add a mobile number to your user, or a phone to your Person, to get a test text."))
	return number


def get_recipients(people: list[str], channel: str, purpose: str | None, church: str) -> list[Recipient]:
	"""Each of *people* who allows *channel* for *purpose*, in order, each address once.

	An email also leaves out an address that stopped the emails of *church*, the church it goes out in.
	"""
	allowed = sorted(allowed_people(people, channel, purpose))
	if channel == SMS:
		return get_text_recipients(allowed)
	if channel == PUSH:
		return get_push_recipients(allowed)
	return get_email_recipients(allowed, email_church(church))


def get_email_recipients(people: list[str], church: str) -> list[Recipient]:
	"""Each of *people* at their primary email, each address once.

	Leaves out an address that is not valid, that bounced, or that stopped *church*'s emails or every email.
	"""
	emails = {
		person: validate_email_address(email)
		for person, email in get_primary_emails("Person", people).items()
	}
	refused = unsubscribed_emails(church) | bounced_addresses([email for email in emails.values() if email])
	usable = {person: email for person, email in emails.items() if email and email not in refused}
	return get_unique_recipients(people, usable, EMAIL_DOCTYPE)


def get_text_recipients(people: list[str]) -> list[Recipient]:
	"""Each of *people* at their primary phone, each number once."""
	numbers = get_primary_values(PHONE_DOCTYPE, "phone_number", "Person", people)
	return get_unique_recipients(people, numbers, PHONE_DOCTYPE)


def get_push_recipients(people: list[str]) -> list[Recipient]:
	"""Each of *people* at their User, while push is on and that User has a browser subscribed."""
	if not people or not is_push_on():
		return []
	# church-scope: the users of people already chosen as recipients, read by name
	users = dict(
		frappe.get_all(
			"Person",
			filters={"name": ("in", people), "user": ("is", "set")},
			fields=["name", "user"],
			as_list=True,
		)
	)
	subscribed = set(
		frappe.get_all(SUBSCRIPTION, filters={"user": ("in", list(users.values()))}, pluck="user")
	)
	return [Recipient(person, users[person]) for person in people if users.get(person) in subscribed]


def get_unique_recipients(
	people: list[str], addresses: dict[str, str], child_doctype: str
) -> list[Recipient]:
	"""*people* in order at their *addresses*, leaving out anyone whose address someone before them has.

	A household that shares one address gets one copy.
	"""
	taken = set()
	recipients = []
	for person in people:
		address = addresses.get(person)
		if address and (key := contact_key(child_doctype, address)) not in taken:
			taken.add(key)
			recipients.append(Recipient(person, address))
	return recipients


def send_text(number: str, text: str) -> bool:
	"""Send *text* to *number* and return whether it left.

	Frappe's gateway raises when it is refused and logs each number it took in SMS Log, so a text that is
	not in SMS Log did not leave. An app that sends texts through the `send_sms` hook keeps its own record.
	"""
	started = now_datetime()
	try:
		send_sms([number], text, success_msg=False)
	except HTTPError as error:
		if error.response is None or error.response.status_code not in REFUSED_STATUSES:
			raise
		return False

	if frappe.get_hooks("send_sms"):
		return True
	[logged_number] = validate_receiver_nos([number])
	return bool(frappe.db.exists("SMS Log", {"sent_to": logged_number, "creation": (">=", started)}))


def get_people_sent(
	email: str,
	people: list[str] | None = None,
	include_failed: bool = False,
	*,
	doctype: str = "Church Email",
	key: str = "",
) -> set[str]:
	"""The people who got a copy of *email*, a *doctype* record, sent with *key*: a Communication linked to it.

	A copy that failed is left out, unless *include_failed* asks for everyone a copy was made for.
	"""
	Communication = frappe.qb.DocType("Communication")
	Link = frappe.qb.DocType("Communication Link")
	query = (
		frappe.qb.from_(Communication)
		.join(Link)
		.on(Link.parent == Communication.name)
		.select(Communication.reference_name)
		.where((Link.parenttype == "Communication") & (Link.link_doctype == doctype))
		.where((Link.link_name == email) & (Communication.reference_doctype == "Person"))
		.where(Coalesce(Communication.send_key, "") == key)
	)
	if people is not None:
		query = query.where(Communication.reference_name.isin(people))
	if not include_failed:
		query = query.where(Coalesce(Communication.delivery_status, "") != ERROR)
	return set(query.run(pluck=True))


def can_send_texts() -> bool:
	"""True when the site can send texts: SMS Settings has a gateway, or an app sends them."""
	return bool(frappe.get_hooks("send_sms") or frappe.db.get_single_value("SMS Settings", "sms_gateway_url"))
