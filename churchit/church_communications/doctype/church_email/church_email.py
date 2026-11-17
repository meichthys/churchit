# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.core.doctype.sms_settings.sms_settings import check_sms_permission
from frappe.model.document import Document
from frappe.utils import add_to_date, cstr, get_datetime, now_datetime, strip_html
from jinja2 import TemplateError
from rq.timeouts import JobTimeoutException

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL, SMS
from churchit.church_communications.newsletter import email_church
from churchit.church_communications.sending import (
	PLACEHOLDERS,
	Delivery,
	Recipient,
	can_send_texts,
	check_placeholders,
	get_copy,
	get_left_out,
	get_people_sent,
	get_person_values,
	get_recipients,
	get_values,
	render,
	uses_only_placeholders,
)
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_people import household, smart_lists
from churchit.church_people.membership import ACTIVE, MEMBER, living_people_filter
from churchit.church_scope import default_church, document_church, is_multi_church

# Church Office edits a message; only these roles send or unschedule it.
SENDER_ROLES = ("Church Manager", "System Manager")

DRAFT = "Draft"
SCHEDULED = "Scheduled"
SENDING = "Sending"
SENT = "Sent"

EMAIL_CHANNEL = "Email"
TEXT_CHANNEL = "Text Message"

ACTIVE_MEMBERS = "Active Members"
GROUP = "Group"
SMART_LIST = "Smart List"
CHOSEN_PEOPLE = "Chosen People"

# Household Members: the household roles each choice adds, None for every member
HOUSEHOLD_ROLES = {
	"Everyone": None,
	"Adults": [household.ADULT],
	"Adults and Other Adults": [household.ADULT, household.OTHER_ADULT],
}

# A delivery job lost to a worker restart is picked up again after this long.
STALLED_AFTER_MINUTES = 15

# The preview and the Send question name the people left out for one reason up to this many, else count them.
LEFT_OUT_NAMES = 10


class ChurchEmail(Document):
	def validate(self):
		if self.is_text_message:
			self.subject = self.get_text_title()
		self.clear_other_audiences()
		self.refuse_another_churches_group()
		self.refuse_another_churches_people()
		if self.send_to == SMART_LIST and not smart_lists.is_smart_list(self.smart_list):
			frappe.throw(
				_("Choose a smart list: a saved Report Builder list of people or a saved Attendance Count.")
			)
		self.validate_placeholders()
		self.keep_status()

	def get_text_title(self) -> str:
		"""A text has no subject, so its first words name it, each placeholder shown as [name]."""
		text = self.text_message or ""
		try:
			text = render(text, get_values({field: f"[{field}]" for field in PLACEHOLDERS}))
		except TemplateError:
			pass

		return text[:140]

	def clear_other_audiences(self):
		"""Keep only the group, smart list or people that Send To uses."""
		if self.send_to != GROUP:
			self.group = None
		if self.send_to != SMART_LIST:
			self.smart_list = None
		if self.send_to != CHOSEN_PEOPLE:
			self.set("people", [])

	def refuse_another_churches_group(self):
		"""The group's members are messaged in this church's name, so it must be this church's group."""
		if not self.group or not is_multi_church():
			return
		if frappe.db.get_value("Group", self.group, "church") != self.own_church:
			frappe.throw(_("Group {0} belongs to another church.").format(self.group))

	def refuse_another_churches_people(self):
		"""Chosen people are messaged in this church's name, so each must be one of its people."""
		if not self.people or not is_multi_church():
			return
		# church-scope: comparing each chosen person's church with this message's own
		rows = frappe.get_all(
			"Person",
			filters={"name": ("in", [row.person for row in self.people])},
			fields=["full_name", "church"],
		)
		others = sorted(row.full_name for row in rows if row.church != self.own_church)
		if others:
			frappe.throw(_("These people belong to another church: {0}.").format(", ".join(others)))

	def validate_placeholders(self):
		"""Refuse a subject, message or text that cannot be filled in for each person."""
		for fieldname in ("text_message",) if self.is_text_message else ("subject", "message"):
			check_placeholders(self.get(fieldname), _(self.meta.get_label(fieldname)))

	def keep_status(self):
		"""Only Send, Unschedule and the delivery move the status, and a message on its way stays as it is."""
		before = self.get_doc_before_save()
		if not before:
			self.status = DRAFT
			return
		if before.status in (SENDING, SENT):
			frappe.throw(_("This message has been sent, so it can no longer be changed."))
		# A scheduled message goes out unchanged by anyone who may not send it.
		if before.status == SCHEDULED and not set(SENDER_ROLES) & set(frappe.get_roles()):
			frappe.throw(
				_(
					"This message is scheduled to send. Ask a Church Manager to unschedule it before you change it."
				),
				frappe.PermissionError,
			)
		self.status = before.status
		if self.status == SCHEDULED and not self.send_after:
			frappe.throw(_("Set Send At, or choose Actions, Unschedule to keep this message as a draft."))

	@property
	def is_text_message(self) -> bool:
		return self.channel == TEXT_CHANNEL

	@property
	def consent_channel(self) -> str:
		"""The consent channel this message goes out on."""
		return SMS if self.is_text_message else EMAIL

	@property
	def own_church(self) -> str | None:
		"""This message's church, worked out before ensure_church fills it on a new one."""
		return document_church(self) or default_church()

	@property
	def sending_church(self) -> str:
		return email_church(self.church)

	def onload(self):
		self.set_onload(
			"sending_problems",
			{channel: get_sending_problem(channel) for channel in (EMAIL_CHANNEL, TEXT_CHANNEL)},
		)

	@frappe.whitelist()
	def get_recipient_count(self) -> dict:
		"""How many people the saved message goes to, and who is left out and why, before it is sent. Reads only.

		Refuses a message with nothing in it, or one the site or the user cannot send.
		"""
		self.load_saved("read")
		self.require_content()
		self.require_sending_set_up()
		recipients, left_out = self.get_reach()
		return {"count": len(recipients), "left_out": left_out}

	@frappe.whitelist()
	def get_preview(self, person: str | None = None) -> dict:
		"""How *person*, or else the first person it goes to, gets this message, and how many people get it. Reads only.

		`left_out` says who gets no copy of their own and why.
		"""
		self.load_saved("read")
		recipients, left_out = self.get_reach()
		preview: dict = {"count": len(recipients), "left_out": left_out}
		recipient = self.get_recipient(recipients, person)
		if recipient:
			frappe.has_permission("Person", "read", doc=recipient.person, throw=True)
			values = get_person_values([recipient.person], self.sending_church)[recipient.person]
			copy = self.get_copy(values)
			preview.update(person=recipient.person, to=recipient.address, **copy)
		return preview

	@frappe.whitelist(methods=["POST"])
	def send_test(self) -> str:
		"""Send this message to the reader alone, straight away, with their own name. Sends messages.

		Returns where it went.
		"""
		self.load_saved("write")
		self.require_content()
		self.require_sending_set_up()
		return Delivery(self).send_test()

	@frappe.whitelist(methods=["POST"])
	def send(self) -> str:
		"""Send it now, or schedule it when Send At is still ahead. Sends messages.

		Returns the new status. Only a Church Manager or System Manager may send.
		"""
		frappe.only_for(SENDER_ROLES)
		self.load_saved("write")
		self.require_content()
		self.require_sending_set_up()
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) != DRAFT:
			frappe.throw(_("This message has already been sent or scheduled."))

		if self.send_after and get_datetime(self.send_after) > now_datetime():
			self.db_set("status", SCHEDULED)
			return SCHEDULED

		self.db_set("status", SENDING)
		enqueue_delivery(self.name)
		return SENDING

	@frappe.whitelist(methods=["POST"])
	def unschedule(self):
		"""Turn a scheduled message back into a draft, so it is not sent at Send At. Changes data."""
		frappe.only_for(SENDER_ROLES)
		self.load_saved("write")
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) == SCHEDULED:
			self.db_set("status", DRAFT)

	def load_saved(self, ptype: str):
		"""Act on the saved message, once the user may *ptype* it.

		Frappe builds a whitelisted method's document from the browser's copy and checks only read on that copy.
		"""
		self.load_from_db()
		self.check_permission(ptype)

	def require_content(self):
		"""Refuse a message with nothing to send. A draft made from the Person list is saved before anything is written."""
		if self.is_text_message:
			if not cstr(self.text_message).strip():
				frappe.throw(_("Write the Text before you send."))
			return
		message = cstr(self.message)
		if not cstr(self.subject).strip() or not (strip_html(message).strip() or "<img" in message):
			frappe.throw(_("Write the Subject and the Message before you send."))

	def require_sending_set_up(self):
		"""Refuse a message the site cannot deliver, or a text the user may not send."""
		if problem := get_sending_problem(self.channel):
			frappe.throw(problem)
		if self.is_text_message:
			check_sms_permission()

	def get_recipient(self, recipients: list[Recipient], person: str | None) -> Recipient | None:
		"""The recipient who is *person*, or the first one when no person is given."""
		if not person:
			return recipients[0] if recipients else None
		recipient = next((recipient for recipient in recipients if recipient.person == person), None)
		if not recipient:
			frappe.throw(_("{0} does not get this message. Pick someone it goes to.").format(person))
		return recipient

	def get_recipients(self) -> list[Recipient]:
		"""Everyone this is for who allows its purpose, in order, each address once."""
		return get_recipients(self.get_people(), self.consent_channel, self.purpose, self.church)

	def get_reach(self) -> tuple[list[Recipient], dict[str, dict]]:
		"""Everyone this goes to, and who is left out for each reason (see `describe_left_out`)."""
		people = self.get_people()
		recipients = get_recipients(people, self.consent_channel, self.purpose, self.church)
		left_out = get_left_out(people, recipients, self.consent_channel, self.purpose, self.church)
		return recipients, describe_left_out(left_out)

	def get_people(self) -> list[str]:
		"""The people this is for, worked out now so that nobody who died or left is included."""
		people = self.get_audience()
		if self.include_household:
			people = list(dict.fromkeys(people + self.get_household_members(people)))
		return people

	def get_audience(self) -> list[str]:
		"""The living people Send To names, before their households are added."""
		if self.send_to == GROUP:
			return self.get_group_members()
		if self.send_to == SMART_LIST:
			return smart_lists.get_people(self.smart_list, self.own_church)

		Person = frappe.qb.DocType("Person")
		if self.send_to == CHOSEN_PEOPLE:
			chosen = [row.person for row in self.people]
			# church-scope: the people this message names, which validate keeps to its own church
			living = set(
				frappe.get_all(
					"Person", filters=[{"name": ("in", chosen)}, living_people_filter(Person)], pluck="name"
				)
			)
			return [person for person in chosen if person in living]

		filters: dict = {"membership_status": ACTIVE}
		if self.send_to == ACTIVE_MEMBERS:
			filters["membership"] = MEMBER
		if is_multi_church():
			filters["church"] = self.own_church
		# church-scope: the people of this message's own church; a Person is never shared
		return frappe.get_all("Person", filters=[filters, living_people_filter(Person)], pluck="name")

	def get_household_members(self, people: list[str]) -> list[str]:
		"""The living members of *people*'s families who hold the roles Household Members picks.

		On a multi-church site only this message's own church's people are added.
		"""
		if not people:
			return []
		# church-scope: the families of people this message already reaches
		families = frappe.get_all(
			"Person", filters={"name": ("in", people), "family": ("is", "set")}, pluck="family", distinct=True
		)
		roles = HOUSEHOLD_ROLES.get(self.household_roles)
		added = [member for family in families for member in household.members(family, roles)]
		if not added or not is_multi_church():
			return added
		# church-scope: keeps the added people of this message's own church; a Person is never shared
		own = set(
			frappe.get_all("Person", filters={"name": ("in", added), "church": self.own_church}, pluck="name")
		)
		return [person for person in added if person in own]

	def get_group_members(self) -> list[str]:
		Person = frappe.qb.DocType("Person")
		GroupMember = frappe.qb.DocType("Group Member")
		# church-scope: the members listed on one group, which validate keeps to this message's church
		return (
			frappe.qb.from_(GroupMember)
			.join(Person)
			.on(Person.name == GroupMember.person)
			.select(Person.name)
			.where((GroupMember.parenttype == "Group") & (GroupMember.parent == self.group))
			.where(living_people_filter(Person))
			.run(pluck=True)
		)

	def get_copy(self, values: dict) -> frappe._dict:
		"""This message filled in with one person's placeholder *values*: a text, or a subject and message."""
		return get_copy(self.consent_channel, values, self.subject, self.message, self.text_message)

	def get_attachments(self) -> list[dict]:
		files = frappe.get_all(
			"File", filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name}, pluck="name"
		)
		return [{"fid": file} for file in files]


def get_sending_problem(channel: str) -> str | None:
	"""Why this site cannot send on *channel* yet, naming who sets it up and where, or None."""
	if channel == TEXT_CHANNEL:
		if not can_send_texts():
			return _(
				"This site cannot send texts yet. Ask a System Manager to fill in SMS Settings "
				"(Settings > Module Settings > SMS Settings)."
			)
	elif not can_send_email():
		return _(
			"This site cannot send emails yet. Ask a System Manager to add an outgoing Email Account "
			"(Settings > Email > Email Accounts)."
		)
	return None


def describe_left_out(left_out: dict[str, list[str]]) -> dict[str, dict]:
	"""{reason: {"count", "names"}} for the people `sending.get_left_out` gives.

	The names come only for a few people, each of whom the reader may read; otherwise the count says it.
	"""
	few = [person for people in left_out.values() if len(people) <= LEFT_OUT_NAMES for person in people]
	names = dict(
		frappe.get_list(
			"Person",
			filters={"name": ("in", few)},
			fields=["name", "full_name"],
			limit=len(few),
			as_list=True,
		)
		if few
		else ()
	)
	described = {}
	for reason, people in left_out.items():
		readable = [names[person] or person for person in people if person in names]
		described[reason] = {"count": len(people), "names": readable if len(readable) == len(people) else []}
	return described


def enqueue_delivery(name: str):
	frappe.enqueue(
		deliver,
		queue="long",
		name=name,
		job_id=f"church_email::{name}",
		deduplicate=True,
		enqueue_after_commit=True,
	)


def deliver(name: str):
	"""Background job: send a copy to everyone it is for, once however often the job runs.

	A job that runs out of time stays Sending, so the stalled retry goes on with the people still waiting.
	"""
	if frappe.db.get_value("Church Email", name, "status", for_update=True) != SENDING:
		return

	email = frappe.get_doc("Church Email", name)
	try:
		Delivery(email).send_all()
	except JobTimeoutException:
		raise
	except Exception as error:
		# The copies already committed stay sent, so sending again reaches only the people still waiting.
		frappe.db.rollback()
		frappe.db.set_value("Church Email", name, "status", DRAFT)
		email.add_comment(
			"Comment",
			_(
				"This message is a draft again, because sending stopped: {0}. "
				"Anyone who already got it does not get it again."
			).format(str(error)),
		)
		frappe.db.commit()
		raise
	email.db_set({"status": SENT, "recipients": len(get_people_sent(name)), "sent_on": now_datetime()})


def send_scheduled():
	"""Scheduler: queue each scheduled message whose Send At has come, and retry stalled deliveries."""
	channels = get_ready_channels()
	if not channels:
		return
	# church-scope: scheduled job; each message goes to its own church's people
	due = frappe.get_all(
		"Church Email",
		filters={"status": SCHEDULED, "send_after": ("<=", now_datetime()), "channel": ("in", channels)},
		pluck="name",
	)
	stalled = frappe.get_all(
		"Church Email",
		filters={
			"status": SENDING,
			"modified": ("<", add_to_date(now_datetime(), minutes=-STALLED_AFTER_MINUTES)),
			"channel": ("in", channels),
		},
		pluck="name",
	)
	for name in due + stalled:
		# The lists were read in an older snapshot; a commit lets the claim see what other workers committed.
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		if claim(name):
			enqueue_delivery(name)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (the claims must outlive the job)


def get_ready_channels() -> list[str]:
	"""The channels the site can send on now: a scheduled message waits until its channel is set up."""
	ready = {EMAIL_CHANNEL: can_send_email(), TEXT_CHANNEL: can_send_texts()}
	return [channel for channel, is_ready in ready.items() if is_ready]


def claim(name: str) -> bool:
	"""Move a due message to Sending, or keep a stalled one there, unless another worker got to it."""
	status = frappe.db.get_value("Church Email", name, "status", for_update=True)
	if status == SCHEDULED:
		frappe.db.set_value("Church Email", name, "status", SENDING)
	return status in (SCHEDULED, SENDING)


@frappe.whitelist(methods=["GET"])
@frappe.validate_and_sanitize_search_inputs
def search_email_templates(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | list | None
) -> list[list[str]]:
	"""Link search for a Church Email's Template: those whose subject and message use only the person placeholders. Reads only.

	The automatic emails' templates use other names, so a Church Email would refuse them on save.
	"""
	templates = frappe.get_list(
		"Email Template",
		filters={"name": ("like", f"%{txt}%")},
		fields=["name", "subject", "use_html", "response", "response_html"],
		order_by="name asc",
		limit=0,
	)
	usable = [
		[template.name]
		for template in templates
		if uses_only_placeholders(template.subject)
		and uses_only_placeholders(template.response_html if template.use_html else template.response)
	]
	return usable[start : start + page_len]
