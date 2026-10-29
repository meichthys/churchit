# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from collections import defaultdict

import frappe
from frappe import _
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.model.document import Document
from frappe.utils import format_date, format_time, get_url, get_url_to_form, getdate, now_datetime, nowdate
from requests import RequestException

from churchit.church_communications.consent import allowed_people
from churchit.church_communications.doctype.communication_consent.communication_consent import SMS
from churchit.church_communications.doctype.communication_purpose.communication_purpose import SERVING
from churchit.church_communications.sending import can_send_texts, send
from churchit.church_ministries import availability
from churchit.church_ministries.doctype.function.function import TIME_FORMAT, get_time_window
from churchit.church_scope import refuse_another_churches_parent, refuse_another_churches_record, scoped
from churchit.contacts import get_primary_email, get_primary_emails

PENDING = "Pending"
ACCEPTED = "Accepted"
DECLINED = "Declined"
ANSWERS = (ACCEPTED, DECLINED)

REQUEST_TEMPLATE = "Ministry Team Request"
REMINDER_TEMPLATE = "Ministry Team Reminder"
DECLINE_TEMPLATE = "Ministry Team Decline"
REPLACEMENT_TEMPLATE = "Ministry Team Replacement"
REQUEST_TEXT = (
	"{{ first_name }}, can you serve as {{ position }} at {{ function }} on {{ date }}? "
	"Please answer here: {{ response_link }}"
)
REMINDER_TEXT = (
	"{{ first_name }}, a reminder: you serve as {{ position }} at {{ function }} on {{ date }}"
	"{% if time %} at {{ time }}{% endif %}. If you cannot come, answer here: {{ response_link }}"
)


class MinistryTeamAssignment(Document):
	def before_insert(self):
		self.response_key = frappe.generate_hash(length=32)

	def validate(self):
		if self.is_new():
			refuse_another_churches_parent(
				self,
				"function",
				_("{0} belongs to another church, so only that church can schedule people for it."),
			)
			self.refuse_a_person_not_on_the_position()
			self.refuse_a_repeat()
			refuse_another_churches_record(self, "Ministry Team Position", self.position)
			self.refuse_without_checks()
			self.validate_replacement()
			self.warn_about_conflicts()

		self.title = f"{self.person_name} as {self.position_doc.position_name} at {self.function_doc.title}"
		if self.status in ANSWERS and self.has_value_changed("status"):
			self.responded_on = now_datetime()

	def on_update(self):
		before = self.get_doc_before_save()
		if before and (before.replaces or None) != (self.replaces or None):
			frappe.throw(_("An assignment cannot change the assignment it replaces."))
		if self.status not in ANSWERS or not self.has_value_changed("status"):
			return

		original = self.get_replaced_assignment()
		if original:
			self.answer_for(original)
		elif self.status == DECLINED:
			self.tell_the_coordinator()

	@property
	def function_doc(self):
		return frappe.get_cached_doc("Function", self.function)

	@property
	def position_doc(self):
		return frappe.get_cached_doc("Ministry Team Position", self.position)

	@property
	def has_started(self) -> bool:
		return get_time_window(self.function_doc)[0] <= now_datetime()

	@property
	def replaced_by(self) -> str | None:
		"""The name of the person who accepted this assignment's place."""
		return frappe.db.get_value(self.doctype, {"replaces": self.name, "status": ACCEPTED}, "person_name")

	def refuse_a_person_not_on_the_position(self):
		if self.person not in {row.person for row in self.position_doc.people}:
			frappe.throw(
				_("{0} is not one of the people who can fill {1}. Add them to the position first.").format(
					frappe.bold(self.person_name), frappe.bold(self.position_doc.title)
				)
			)

	def refuse_a_repeat(self):
		if frappe.db.exists(
			"Ministry Team Assignment",
			{"function": self.function, "position": self.position, "person": self.person},
		):
			frappe.throw(
				_("{0} is already assigned to this position at this function.").format(self.person_name)
			)

	def refuse_without_checks(self):
		if not self.position_doc.block_without_checks:
			return
		start, _end = get_time_window(self.function_doc)
		problem = availability.get_check_problem(self.person, self.position, start.date())
		if problem:
			frappe.throw(problem, title=_("Not cleared to serve"))

	def validate_replacement(self):
		"""Only `member_ministry_team.ask_replacement` sets Replaces, after its checks."""
		if self.replaces and not self.flags.is_replacement_request:
			frappe.throw(_("Ask for a replacement on the Ministry Team page."))

	def warn_about_conflicts(self):
		warnings = self.get_warnings()
		if warnings:
			frappe.msgprint(warnings, title=_("Check this assignment"), indicator="orange", as_list=True)

	def get_warnings(self) -> list[str]:
		start, end = get_time_window(self.function_doc)
		warnings = availability.get_problems(self.person, start, end, self.position, self.function)
		if not get_primary_email("Person", self.person):
			warnings.append(
				_("{0} has no email address, so the request shows only in their portal.").format(
					self.person_name
				)
			)
		return warnings

	def respond(self, status: str, reason: str | None = None):
		"""Record the person's answer. The caller checks that whoever answers may."""
		if status not in ANSWERS:
			frappe.throw(_("Answer with Accepted or Declined."))
		if self.has_started:
			frappe.throw(_("{0} has already started.").format(self.function_doc.function_name))
		if status == ACCEPTED and self.replaced_by:
			frappe.throw(_("Your place went to {0}.").format(self.replaced_by))
		self.status = status
		self.decline_reason = reason if status == DECLINED else None

	def get_email_context(self) -> frappe._dict:
		start, _end = get_time_window(self.function_doc)
		return frappe._dict(
			first_name=frappe.db.get_value("Person", self.person, "first_name"),
			person_name=self.person_name,
			position=self.position_doc.position_name,
			ministry=frappe.db.get_value("Ministry", self.position_doc.ministry, "ministry_name"),
			function=self.function_doc.function_name,
			date=format_date(start, "EEEE, MMMM d, yyyy"),
			time=format_time(start, TIME_FORMAT)
			if self.function_doc.start_time and not self.function_doc.all_day
			else "",
			status=self.status,
			decline_reason=self.decline_reason,
			response_link=get_url(f"/ministry-team-response?key={self.response_key}"),
			assignment_link=get_url_to_form(self.doctype, self.name),
		)

	def tell_the_coordinator(self):
		coordinator = frappe.db.get_value("Ministry", self.position_doc.ministry, "team_coordinator")
		email = coordinator and get_primary_email("Person", coordinator)
		if email and can_send_email():
			context = self.get_email_context()
			context.update(replaced_by=self.flags.replaced_by or "")
			send_team_email(DECLINE_TEMPLATE, email, context, self)

	def get_replaced_assignment(self) -> Document | None:
		"""The assignment this one replaces, locked, while its person still serves."""
		if not self.replaces:
			return None
		original = frappe.get_doc(self.doctype, self.replaces, for_update=True)
		return original if original.status != DECLINED else None

	def answer_for(self, original: Document):
		"""An accepted replacement takes *original*'s place. Either answer tells its person."""
		if self.status == ACCEPTED:
			original.status = DECLINED
			original.decline_reason = _("Replaced by {0}").format(self.person_name)
			# The person asked for this. The decline emails the coordinator and names who takes the place.
			original.flags.replaced_by = self.person_name
			original.save(ignore_permissions=True)

		email = get_primary_email("Person", original.person)
		if email and can_send_email():
			context = original.get_email_context()
			context.update(replacement_name=self.person_name, has_accepted=self.status == ACCEPTED)
			send_team_email(REPLACEMENT_TEMPLATE, email, context, original)


def can_send_email() -> bool:
	return bool(EmailAccount.find_outgoing())


def send_team_email(template: str, recipient: str, context: dict, assignment: Document):
	email = frappe.get_doc("Email Template", template).get_formatted_email(context)
	frappe.sendmail(
		recipients=[recipient],
		subject=email["subject"],
		message=email["message"],
		reference_doctype=assignment.doctype,
		reference_name=assignment.name,
	)


class TeamTexts:
	"""The texts of one run: on when the site sends texts and the user passes SMS Settings Allowed Roles.

	When the site sends texts but the user may not, the people who allow them wait for the daily job, so
	their texts are not lost. A gateway failure is logged and turns the texts off, so the emails still go.
	"""

	def __init__(self):
		from churchit.church_ministries.page.check_in.paging import can_text  # paging imports this module

		self.is_on = can_text()
		self.is_held = not self.is_on and can_send_texts()

	def is_waiting(self, person: str) -> bool:
		"""Whether *person* allows texts for Serving that the user may not send, so the daily job asks them."""
		return self.is_held and bool(allowed_people([person], SMS, SERVING))

	def send_about(self, assignment: Document, key: str, text: str) -> int:
		"""Text the person about *assignment* if they allow texts for Serving, and return how many left.

		A text leaves at once, so the caller commits as soon as it marks the assignment sent.
		"""
		if not self.is_on:
			return 0

		frappe.db.savepoint("team_text")
		try:
			sent = send(
				[assignment.person],
				SMS,
				SERVING,
				assignment,
				key=key,
				text=text,
				context=assignment.get_email_context(),
			)
		except RequestException:
			frappe.db.rollback(save_point="team_text")  # the copy of a text that did not leave
			frappe.log_error(
				title=f"Could not text the ministry team {key} for {assignment.name}",
				reference_doctype=assignment.doctype,
				reference_name=assignment.name,
			)
			self.is_on = False
			return 0
		return len(sent)


def send_team_emails() -> int:
	"""Daily scheduler: ask people about new assignments, then remind them as each function nears.

	Emails go when the site has an outgoing email account, texts when it can send texts. With neither,
	it waits, so nothing is marked as sent that was not. Returns the number of emails and texts sent.
	"""
	texts = TeamTexts()
	if not (can_send_email() or texts.is_on):
		return 0
	return send_requests(texts) + send_reminders(texts)


@frappe.whitelist(methods=["POST"])
def send_team_emails_now() -> int:
	"""Send what the daily job would send next, for the churches the user may see."""
	frappe.has_permission("Ministry Team Assignment", "create", throw=True)
	if not (can_send_email() or TeamTexts().is_on):
		frappe.throw(_("Set up an outgoing Email Account or SMS Settings first."))
	return send_team_emails()


@frappe.whitelist()
def get_team_emails(function: str) -> frappe._dict:
	"""Email addresses of the people asked to serve at *function* who did not decline, and who has none."""
	frappe.has_permission("Function", doc=function, throw=True)
	assignments = frappe.get_list(
		"Ministry Team Assignment",
		filters={"function": function, "status": ("!=", DECLINED)},
		fields=["person", "person_name"],
		order_by="person_name asc",
	)
	people = {row.person: row.person_name for row in assignments}
	emails = get_primary_emails("Person", list(people))
	return frappe._dict(
		emails=[emails[person] for person in people if person in emails],
		without_email=[name for person, name in people.items() if person not in emails],
	)


def get_upcoming_assignments() -> list[frappe._dict]:
	"""Assignments at functions from today on, soonest first, with their ministry's reminder days.

	Scoped to the user's churches. The daily job runs as Administrator, so it covers every church.
	"""
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	Function = frappe.qb.DocType("Function")
	Position = frappe.qb.DocType("Ministry Team Position")
	Ministry = frappe.qb.DocType("Ministry")
	query = (
		frappe.qb.from_(Assignment)
		.join(Function)
		.on(Assignment.function == Function.name)
		.join(Position)
		.on(Assignment.position == Position.name)
		.join(Ministry)
		.on(Position.ministry == Ministry.name)
		.select(
			Assignment.name,
			Assignment.person,
			Assignment.status,
			Assignment.requested_on,
			Assignment.reminded_on,
			Function.start_date,
			Ministry.team_reminder_days,
		)
		.where(Function.start_date >= nowdate())
		.orderby(Function.start_date)
	)
	return scoped(query, Assignment, {}).run(as_dict=True)


def send_requests(texts: TeamTexts) -> int:
	"""One email per person, listing every assignment they have not been asked about yet, and a text for each.

	Without an email account, only an assignment whose text left is marked as asked.
	"""
	sent = 0
	is_emailing = can_send_email()
	by_person = defaultdict(list)
	for row in get_upcoming_assignments():
		if row.status == PENDING and not row.requested_on:
			by_person[row.person].append(frappe.get_doc("Ministry Team Assignment", row.name))

	for person, assignments in by_person.items():
		if texts.is_waiting(person):
			continue
		email = is_emailing and get_primary_email("Person", person)
		if email:
			contexts = [assignment.get_email_context() for assignment in assignments]
			context = {"first_name": contexts[0]["first_name"], "assignments": contexts}
			send_team_email(REQUEST_TEMPLATE, email, context, assignments[0])
			sent += 1
		for assignment in assignments:
			texted = texts.send_about(assignment, "request", REQUEST_TEXT)
			if is_emailing or texted:
				assignment.db_set("requested_on", now_datetime(), update_modified=False)
			if texted:
				frappe.db.commit()
			sent += texted
	return sent


def send_reminders(texts: TeamTexts) -> int:
	"""Remind each person serving, the ministry's Remind Days Before ahead of the function.

	A request sent today already says it all, so its reminder waits for the next day. Without an email
	account, only an assignment whose text left is marked as reminded.
	"""
	sent = 0
	today = getdate()
	is_emailing = can_send_email()
	for row in get_upcoming_assignments():
		if not is_due_for_a_reminder(row, today) or texts.is_waiting(row.person):
			continue

		assignment = frappe.get_doc("Ministry Team Assignment", row.name)
		email = is_emailing and get_primary_email("Person", row.person)
		if email:
			send_team_email(REMINDER_TEMPLATE, email, assignment.get_email_context(), assignment)
			sent += 1
		texted = texts.send_about(assignment, "reminder", REMINDER_TEXT)
		if is_emailing or texted:
			assignment.db_set("reminded_on", now_datetime(), update_modified=False)
		if texted:
			frappe.db.commit()
		sent += texted
	return sent


def is_due_for_a_reminder(row: frappe._dict, today) -> bool:
	if row.status == DECLINED or row.reminded_on or not row.team_reminder_days:
		return False
	if row.requested_on and getdate(row.requested_on) >= today:
		return False
	return (getdate(row.start_date) - today).days <= row.team_reminder_days
