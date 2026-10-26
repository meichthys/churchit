from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import (
	add_to_date,
	cint,
	flt,
	fmt_money,
	format_date,
	format_datetime,
	format_time,
	get_datetime,
	get_url,
	now_datetime,
)
from frappe.utils.verified_command import get_signed_params

from churchit.church_finances.doctype.collection.collection import add_single_donation
from churchit.church_finances.doctype.online_donation.online_donation import PAID_STATUSES
from churchit.church_finances.payments import PAYMENT_RECORDERS, is_charge_confirmed, notify_finance
from churchit.church_ministries.attendance import record, remove
from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_ministries.sign_up_amounts import get_amount_due, get_discount
from churchit.church_people.matching import find_or_add_person
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import (
	church_filters,
	refuse_another_churches_parent,
	session_church,
	session_person,
)
from churchit.contacts import get_primary_email
from churchit.ics import make_calendar, make_event
from churchit.utils import resolve_link_titles
from churchit.www.calendar import _format_address

SIGNED_UP = "Signed-Up"
PENDING, CONFIRMED, WAITLISTED, CANCELLED = "Pending", "Confirmed", "Waitlisted", "Cancelled"
# Only code sets these (`flags.set_by_code`); validate puts back what a browser sent.
PROTECTED_FIELDS = ("status", "hold_expires_on", "approved_by", "amount_paid", "payment_status")
WINDOW_FIELDS = ("sign_ups_open_on", "sign_ups_close_on")
# The Person source of the people a sign-up adds.
SIGN_UP_SOURCE = "Sign-Up"
HOLD_HOURS = 24
SIGN_UP_APPROVERS = {"Church Manager", "System Manager", "Church People Editor"}
CONFIRMATION_TEMPLATE = "Sign-Up Confirmation"
UNPAID, PAID, REFUND_DUE, REFUNDED = "Unpaid", "Paid", "Refund Due", "Refunded"
# A sign-up in one of these takes no more payment.
PAYMENT_DONE = (PAID, REFUND_DUE, REFUNDED)
PAYMENT_DUE_TEMPLATE = "Sign-Up Payment Due"
PAY_METHOD = "churchit.www.register.pay"
EVENT_FIELDS = (
	"name",
	"function_name",
	"title",
	"start_date",
	"start_time",
	"end_date",
	"end_time",
	"all_day",
	"address",
	"description",
	"modified",
)


class FunctionSignUp(Document):
	def validate(self):
		self.refuse_closed_function()
		self.set_person()
		self.restore_protected_fields()
		self.set_attendees()
		self.refuse_people_signed_up()
		self.set_item_quantities_needed()
		self.set_amounts()
		self.reserve_seats()

	def refuse_closed_function(self):
		# A change made by code, such as a member cancelling after sign-ups close, is not refused.
		if self.flags.set_by_code:
			return
		if not frappe.db.get_value("Function", self.function, "allow_sign_ups"):
			frappe.throw(_("Sign ups are not enabled for this function."))

		if frappe.session.user == "Guest" or is_portal_member():
			if not is_open_for_sign_up(self.function):
				frappe.throw(_("This function is not open for you to sign up."), frappe.PermissionError)
		else:
			refuse_another_churches_parent(
				self,
				"function",
				_("{0} belongs to another church, so only that church can sign people up for it."),
			)

	def set_person(self):
		if self.flags.set_by_code:
			return  # code changes the status of anyone's sign-up, never whose sign-up it is
		if is_portal_member():
			# Force person from the linked Person record to prevent tampering
			person_name = session_person()
			if not person_name:
				frappe.throw(_("No Person record is linked to your account."))
			self.person = person_name
		elif frappe.session.user == "Guest":
			# A guest never names the person: link_registrant finds or adds them after the commit.
			if self.is_new():
				self.person = None
		elif self.person and not self.flags.ignore_permissions:
			# `person` is a plain Link, which user permissions never measure against its church.
			frappe.has_permission("Person", doc=self.person, throw=True)

		if not self.person and not (self.registrant_name and self.email):
			frappe.throw(_("A sign-up with no Person needs the registrant's name and email."))

	def restore_protected_fields(self):
		"""Put back the stored status, payment and approval fields unless code set them (`flags.set_by_code`)."""
		if self.flags.set_by_code:
			return
		before = self.get_doc_before_save()
		for fieldname in PROTECTED_FIELDS:
			self.set(fieldname, before.get(fieldname) if before else self.meta.get_field(fieldname).default)

	def set_attendees(self):
		"""Keep the registrant's attendee row while Attending is ticked, and check each row's selection."""
		before = self.get_doc_before_save()
		registrant = next((row for row in self.attendees if self.is_registrant_row(row)), None)
		if not registrant and before:
			# Staff changed the person or fixed the typed name: the old registrant row is this one.
			registrant = next((row for row in self.attendees if before.is_registrant_row(row)), None)
		if registrant and not self.attending:
			self.remove(registrant)
		elif self.attending:
			registrant = registrant or self.append("attendees", {})
			registrant.person = self.person
			if not self.person:
				registrant.attendee_name = self.registrant_name

		# church-scope: the selections of the function this sign-up is for
		selections = frappe.get_all(
			"Function Sign-Up Selection",
			filters={"parent": self.function, "parenttype": "Function"},
			pluck="selection",
		)
		saved = {row.name: get_attendee_key(row) for row in before.attendees} if before else {}
		for row in self.attendees:
			# A saved row was checked then. A member cannot read every household Person, and a cancel
			# still works after the function's selections changed.
			if saved.get(row.name) == get_attendee_key(row):
				continue
			self.set_attendee_name(row)
			if (row.selection or selections) and row.selection not in selections:
				frappe.throw(_("Row {0}: choose one of this function's selections.").format(row.idx))

	def is_registrant_row(self, row) -> bool:
		"""The attendee row of the registrant: their Person, or a guest's name before a Person is linked."""
		if self.person and row.person == self.person:
			return True
		return not row.person and bool(self.registrant_name) and row.attendee_name == self.registrant_name

	def set_attendee_name(self, row):
		if row.person:
			# `person` is a plain Link, which user permissions never measure against its church.
			if not self.flags.ignore_permissions:
				frappe.has_permission("Person", doc=row.person, throw=True)
			row.attendee_name = frappe.db.get_value("Person", row.person, "full_name")
		if not row.attendee_name:
			frappe.throw(_("Row {0}: give the attendee's name.").format(row.idx))

	def get_attendee_people(self) -> set[str]:
		return {row.person for row in self.attendees if row.person}

	def refuse_people_signed_up(self, for_update: bool = False):
		# Checked once `person` is settled: the portal form sends none of its own. A guest has no person yet.
		if self.status == CANCELLED:
			return  # it holds no seat, so the person may have signed up again
		people = [row.person for row in self.attendees if row.person]
		if len(people) != len(set(people)):
			frappe.throw(_("Each person can be on a sign-up only once."))

		taken = self.get_people_signed_up({self.person, *people} - {None, ""}, for_update)
		if self.person in taken:
			frappe.throw(_("This person has already signed up for this function."))
		if taken:
			names = ", ".join(row.attendee_name for row in self.attendees if row.person in taken)
			frappe.throw(_("Already signed up for this function: {0}.").format(names))

	def get_people_signed_up(self, people: set[str], for_update: bool = False) -> set[str]:
		"""Those of *people* on another sign-up of this function that is not Cancelled, as its registrant or an attendee.

		*for_update* makes it a locking read, for a check under the Function row lock.
		"""
		if not people:
			return set()

		SignUp = frappe.qb.DocType("Function Sign-Up")
		Attendee = frappe.qb.DocType("Function Sign-Up Attendee")
		# church-scope: the sign-ups of one function, read to refuse a second one and never shown
		others = (
			(SignUp.function == self.function)
			& (SignUp.name != (self.name or ""))
			& (Coalesce(SignUp.status, "") != CANCELLED)
		)
		registrants = frappe.qb.from_(SignUp).select(SignUp.person).where(others & SignUp.person.isin(people))
		attendees = (
			frappe.qb.from_(Attendee)
			.join(SignUp)
			.on(SignUp.name == Attendee.parent)
			.select(Attendee.person)
			.where(others & (Attendee.parenttype == "Function Sign-Up") & Attendee.person.isin(people))
		)
		if for_update:
			registrants, attendees = registrants.for_update(), attendees.for_update()
		return set(registrants.run(pluck=True)) | set(attendees.run(pluck=True))

	def set_item_quantities_needed(self):
		"""Mirror each item's function-level quantity_needed and price onto the sign-up row for display."""
		for row in self.table_iprj:
			if cint(row.my_quantity) < 0:
				frappe.throw(_("Row {0}: the quantity cannot be below 0.").format(row.idx))

			function_row = (
				frappe.db.get_value(
					"Function Sign-Up Item",
					{"parent": self.function, "parenttype": "Function", "item": row.item},
					["quantity_needed", "price"],
					as_dict=True,
				)
				or frappe._dict()
			)
			row.quantity_needed = function_row.quantity_needed or 0
			row.price = function_row.price or 0

	def set_amounts(self):
		"""Work out `discount` and `amount_due` on the server, whatever the browser sent."""
		self.discount = get_discount(self)
		self.amount_due = get_amount_due(self)
		if not self.payment_status and self.amount_to_pay:
			self.payment_status = UNPAID
		elif self.payment_status == UNPAID and not self.amount_to_pay:
			self.payment_status = None

	def reserve_seats(self):
		"""Give a new, promoted or moved sign-up, or one with more attendees, its status: Confirmed, Pending or Waitlisted."""
		if not self.is_claiming_seats():
			return

		limits = get_seat_limits(self.function)
		# Again under the lock: the plain read in validate can miss a sign-up committed meanwhile.
		self.refuse_people_signed_up(for_update=True)
		if not (self.is_new() or self.flags.promote):
			self.check_growth(limits)
		if smaller := self.get_full_capacity(limits, Counter()):
			frappe.throw(_("There are more attendees than seats in {0}.").format(smaller))
		if problem := self.get_item_problem():
			frappe.throw(problem)

		if not self.get_full_capacity(limits, get_seats_taken(self.function, self.name)):
			self.hold_seats(limits.sign_up_requires_approval)
		elif self.is_new() or self.status == WAITLISTED or self.has_value_changed("function"):
			self.status, self.hold_expires_on = WAITLISTED, None
		else:
			frappe.throw(_("There are not enough free seats for the added attendees."))

	def is_claiming_seats(self) -> bool:
		"""New, promoted, moved to another function, or a Confirmed or Pending sign-up that asks for more."""
		if self.is_new() or self.flags.promote:
			return True
		if self.status != CANCELLED and self.has_value_changed("function"):
			return True  # it claims the other function's seats, as a new sign-up does
		if self.status not in (CONFIRMED, PENDING):
			return False
		held = self.get_doc_before_save().get_claims()
		return any(count > held[key] for key, count in self.get_claims().items())

	def get_claims(self) -> Counter:
		"""The seats this sign-up takes, in all and by selection, and the quantity of each item it brings."""
		claims = Counter(("selection", row.selection) for row in self.attendees)
		claims["seats"] = len(self.attendees)
		for row in self.table_iprj:
			claims["item", row.item] += cint(row.my_quantity)
		return claims

	def get_full_capacity(self, limits: frappe._dict, taken: Counter) -> str | None:
		"""The function or selection whose capacity this sign-up's attendees would pass on top of *taken*."""
		claims = self.get_claims()
		if limits.capacity and taken["seats"] + claims["seats"] > limits.capacity:
			return limits.function_name
		for selection, capacity in limits.selections.items():
			if capacity and taken["selection", selection] + claims["selection", selection] > capacity:
				return selection
		return None

	def get_item_problem(self) -> str | None:
		"""Why this sign-up brings more of a limited item than the other sign-ups leave, or None."""
		# church-scope: the items of the function this sign-up is for
		limited = frappe.get_all(
			"Function Sign-Up Item",
			filters={"parent": self.function, "parenttype": "Function", "is_limited": 1},
			fields=["item", "quantity_needed"],
		)
		if not limited:
			return None

		totals = get_item_totals(self.function, self.name, for_update=True)
		claims = self.get_claims()
		for row in limited:
			left = max(cint(row.quantity_needed) - totals[row.item]["quantity_signed_up"], 0)
			if claims["item", row.item] > left:
				return _("Only {0} more of {1} can be signed up for.").format(left, row.item)
		return None

	def check_growth(self, limits: frappe._dict):
		"""On a function that needs approval, a sign-up that grows or moves waits for approval again.
		A paid one cannot grow or move when it would need more pay, a new approval or another function's fund.
		"""
		needs_more = (
			limits.sign_up_requires_approval
			or self.has_value_changed("function")
			or flt(self.amount_due) > flt(self.amount_paid)
		)
		if flt(self.amount_paid) and needs_more:
			frappe.throw(
				_("This sign-up is paid, so it cannot change like this. Make a new sign-up instead.")
			)
		if limits.sign_up_requires_approval:
			self.approved_by = None

	def hold_seats(self, requires_approval: bool):
		"""Confirm the seats, or hold them while the sign-up waits for approval or for payment."""
		# A held sign-up that grows keeps its hold, so an edit cannot extend it.
		hold, self.hold_expires_on = self.hold_expires_on, None
		if requires_approval and not self.approved_by:
			self.status = PENDING
		elif flt(self.amount_due) > flt(self.amount_paid):
			self.status = PENDING
			self.hold_expires_on = hold or add_to_date(now_datetime(), hours=HOLD_HOURS)
		else:
			self.status = CONFIRMED

	def before_save(self):
		self.set_title()
		self.sync_attendance()

	def set_title(self):
		function_label = (
			frappe.db.get_value("Function", self.function, "function_name") if self.function else ""
		)
		person_label = (
			frappe.db.get_value("Person", self.person, "full_name") if self.person else self.registrant_name
		)
		parts = [function_label or "", person_label or ""]
		self.title = " - ".join(p for p in parts if p)

	def sync_attendance(self):
		"""Each attendee Person has a Signed-Up attendance row while the sign-up is Confirmed."""
		attending = self.get_attendee_people() if self.status == CONFIRMED else set()
		for person in attending:
			record(person, self.function, SIGNED_UP)

		# Only a Confirmed sign-up has rows: a Cancelled one's people may be on a later sign-up.
		before = self.get_doc_before_save()
		if before and before.status == CONFIRMED:
			kept = attending if before.function == self.function else set()
			before.remove_attendance(before.get_attendee_people() - kept)

	def after_insert(self):
		if not self.person:
			frappe.enqueue(link_registrant, enqueue_after_commit=True, sign_up=self.name)

	def on_update(self):
		self.send_confirmation()
		self.send_payment_request()

	def send_registrant_email(
		self, template: str, attachments: list | None = None, context: dict | None = None
	) -> None:
		"""Email the registrant an answer to their own request, from the Email Template *template*.

		It goes to the Person's primary email, else, while there is no Person, to the sign-up's email, with no
		consent check: the registrant asked for it, and a new guest Visitor has no consent yet. An email that
		names a Person goes only to that Person, never to an `email` someone typed. With no outgoing email
		account, or when the church deleted the template, nothing is sent. A failure is logged and never undoes
		the sign-up.
		"""
		recipient = get_primary_email("Person", self.person) if self.person else self.email
		if not (recipient and can_send_email() and frappe.db.exists("Email Template", template)):
			return

		context = {**self.get_email_context(), **(context or {})}
		try:
			email = frappe.get_doc("Email Template", template).get_formatted_email(context)
			frappe.sendmail(
				recipients=[recipient],
				subject=email["subject"],
				message=email["message"],
				attachments=attachments,
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
		except Exception:
			frappe.log_error(
				_("Could not email the registrant of {0}").format(self.name),
				reference_doctype=self.doctype,
				reference_name=self.name,
			)

	def get_email_context(self) -> dict:
		"""What a registrant email names: the registrant's first name, the function, its date and time, and who attends."""
		function = frappe.db.get_value(
			"Function", self.function, ["function_name", "start_date", "start_time", "all_day"], as_dict=True
		)
		first_name = self.person and frappe.db.get_value("Person", self.person, "first_name")
		has_time = function.start_time and not function.all_day
		return {
			"doc": self,
			"first_name": first_name or (self.registrant_name or "").split(" ")[0] or _("Friend"),
			"function_name": function.function_name,
			"date": format_date(function.start_date),
			"time": format_time(function.start_time, TIME_FORMAT) if has_time else "",
			"attendees": [row.attendee_name for row in self.attendees],
		}

	def send_confirmation(self):
		"""Email the registrant once, with a calendar file, when the sign-up becomes Confirmed."""
		# A sign-up moved to another function is confirmed again, for the new event.
		if self.status != CONFIRMED or not (
			self.has_value_changed("status") or self.has_value_changed("function")
		):
			return
		calendar = {
			"fname": "event.ics",
			"fcontent": get_function_calendar(self.function),
			"content_type": "text/calendar",
		}
		self.send_registrant_email(CONFIRMATION_TEMPLATE, attachments=[calendar])

	def send_payment_request(self):
		"""Email the registrant the payment link when a new hold starts."""
		if not (self.hold_expires_on and self.has_value_changed("hold_expires_on")):
			return
		currency = frappe.get_cached_doc("Giving Settings").currency or "USD"
		context = {
			"amount": fmt_money(self.amount_to_pay, currency=currency),
			"pay_by": format_datetime(self.hold_expires_on),
			"pay_url": self.pay_url,
		}
		self.send_registrant_email(PAYMENT_DUE_TEMPLATE, context=context)

	@property
	def payment_church(self) -> str | None:
		"""The church that takes this sign-up's payments: its Function's, or the church that shared it."""
		church, shared_by = frappe.db.get_value("Function", self.function, ["church", "shared_by_church"])
		return church or shared_by

	@property
	def amount_to_pay(self) -> float:
		return max(flt(self.amount_due) - flt(self.amount_paid), 0)

	@property
	def is_holding_seats(self) -> bool:
		"""Confirmed, or Pending with no hold or one not yet passed: `holds_seats` for this sign-up."""
		if self.status == CONFIRMED:
			return True
		hold = self.hold_expires_on
		return self.status == PENDING and (not hold or get_datetime(hold) >= now_datetime())

	@property
	def is_payable(self) -> bool:
		"""True while a payment hold waits for money that the payment church can take online."""
		if not (self.hold_expires_on and self.is_holding_seats and self.amount_to_pay):
			return False
		return bool(frappe.get_cached_doc("Giving Settings").gateways_for(self.payment_church))

	@property
	def pay_url(self) -> str:
		"""The signed Pay now link of the /register page and the payment email, while the sign-up is payable."""
		if not self.is_payable:
			return ""
		return get_url(f"/api/method/{PAY_METHOD}?{get_signed_params({'sign_up': self.name})}")

	def on_trash(self):
		# Deleting a paid sign-up would lose the record of what Finance owes back.
		if flt(self.amount_paid) and not set(PAYMENT_RECORDERS) & set(frappe.get_roles()):
			frappe.throw(
				_("This sign-up is paid, so only a Church Manager can delete it. Cancel it instead."),
				frappe.PermissionError,
			)
		if self.status == CONFIRMED:
			self.remove_attendance(self.get_attendee_people())

	def on_change(self):
		# After the save, so the count no longer sees the seats a moved or smaller party gave up.
		before = self.get_doc_before_save()
		if not before or before.status not in (CONFIRMED, PENDING):
			return
		if before.function != self.function:
			promote_waitlist(before.function)
		elif self.status in (CONFIRMED, PENDING):
			claims = self.get_claims()
			if any(claims[key] < count for key, count in before.get_claims().items()):
				promote_waitlist(self.function)

	def after_delete(self):
		# After the delete, so the count no longer sees this sign-up's seats.
		if self.status in (CONFIRMED, PENDING):
			promote_waitlist(self.function)

	def remove_attendance(self, people: set[str]):
		removed = [person for person in people if remove(person, self.function, SIGNED_UP)]
		if removed:
			frappe.msgprint(_("The associated attendance record has been removed."))

	@frappe.whitelist(methods=["POST"])
	def cancel_registration(self):
		"""Cancel this sign-up and give its seats to the waitlist."""
		self.reload()
		self.check_permission("write")
		# The Function before the sign-up, the order every change to its seats takes the locks in.
		frappe.db.get_value("Function", self.function, "name", for_update=True)
		if self.status == CANCELLED:
			return
		self.cancel_sign_up()

	@frappe.whitelist(methods=["POST"])
	def approve(self):
		"""Approve a Pending sign-up of a function whose sign-ups need approval."""
		self.refuse_unless_waiting_for_approval()
		self.approved_by = frappe.session.user
		self.hold_seats(requires_approval=False)
		self.flags.set_by_code = True
		self.save()

	@frappe.whitelist(methods=["POST"])
	def decline(self):
		"""Decline a Pending sign-up and give its seats to the waitlist."""
		self.refuse_unless_waiting_for_approval()
		self.cancel_sign_up()

	def cancel_sign_up(self):
		"""Cancel, under the caller's Function lock, and give the seats to the waitlist. A paid one is Refund Due."""
		was_paid = self.payment_status == PAID
		self.status = CANCELLED
		if was_paid:
			self.payment_status = REFUND_DUE
		self.flags.set_by_code = True
		self.save()
		promote_waitlist(self.function)
		if was_paid:
			reason = _("Sign-up {0} was cancelled after it was paid. Refund the payment.").format(self.name)
			notify_finance(
				[frappe._dict(doctype=self.doctype, name=self.name, church=self.payment_church)], reason
			)

	def refuse_unless_waiting_for_approval(self):
		"""Load the stored sign-up under its Function's lock, for an approver, while it waits for approval."""
		self.reload()  # the saved record, not the copy the browser sent
		self.check_permission("write")
		# A registrant holds write on their own sign-up, so the role decides, as for Room Booking.
		if not SIGN_UP_APPROVERS & set(frappe.get_roles()):
			frappe.throw(
				_("Only a Church Manager or Church People Editor can approve a sign-up."),
				frappe.PermissionError,
			)

		# The Function before the sign-up, the order every change to its seats takes the locks in.
		frappe.db.get_value("Function", self.function, "name", for_update=True)
		if self.status != PENDING or self.approved_by or self.hold_expires_on:
			frappe.throw(_("This sign-up is not waiting for approval."))

	@frappe.whitelist(methods=["POST"])
	def record_offline_payment(self):
		"""Church Finance: the registrant paid in person, so the cash goes in the weekly Collection."""
		self.refuse_unless_payment_recorder()
		if self.status == WAITLISTED or self.payment_status in PAYMENT_DONE or not self.amount_to_pay:
			frappe.throw(_("This sign-up has no amount due."))
		self.record_payment(self.amount_to_pay, get_seat_limits(self.function))

	@frappe.whitelist(methods=["POST"])
	def record_refund(self):
		"""Church Finance: the payment was refunded at the processor."""
		self.refuse_unless_payment_recorder()
		if self.payment_status not in (PAID, REFUND_DUE):
			frappe.throw(_("Only a paid sign-up can be refunded."))
		self.payment_status = REFUNDED
		self.flags.set_by_code = True
		self.save()

	def refuse_unless_payment_recorder(self):
		"""Load the stored sign-up under its Function's lock, for Church Finance or a Church Manager."""
		# A registrant holds write on their own sign-up, so the role decides.
		frappe.only_for(PAYMENT_RECORDERS)
		self.reload()
		self.check_permission("write")
		# The Function before the sign-up, the order every change to its seats takes the locks in.
		frappe.db.get_value("Function", self.function, "name", for_update=True)

	def on_payment_authorized(self, status: str | None = None):
		"""The payments app callback (X6.4): record a confirmed charge once and confirm the sign-up."""
		if status not in PAID_STATUSES:
			return
		limits = get_seat_limits(self.function)  # the Function lock, before the sign-up row
		frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
		self.reload()
		amount, church = self.amount_to_pay, self.payment_church
		currency = frappe.get_cached_doc("Giving Settings").currency or "USD"
		# A gateway calls back once for each charge, so a callback on a paid sign-up is a second charge.
		if self.payment_status in PAYMENT_DONE:
			reason = _("Sign-up {0} was charged again after it was paid. Refund the extra charge.").format(
				self.name
			)
		elif not (amount and is_charge_confirmed(self, amount, currency)):
			reason = _(
				"Sign-up {0} was charged online, but not the {1} it owes. Check the payment before you record it."
			).format(self.name, fmt_money(amount, currency=currency))
		else:
			fund = frappe.db.get_value("Function", self.function, "sign_up_fund")
			add_single_donation(church, fund, amount, _("Registration fee of sign-up {0}").format(self.name))
			self.record_payment(amount, limits)
			return

		notify_finance([frappe._dict(doctype=self.doctype, name=self.name, church=church)], reason)

	def record_payment(self, amount: float, limits: frappe._dict):
		"""Add *amount* to what is paid and confirm. A sign-up whose seats went meanwhile is Refund Due."""
		self.amount_paid = flt(self.amount_paid) + amount
		if self.is_holding_seats or self.has_free_seats(limits):
			self.payment_status = PAID
			self.hold_seats(limits.sign_up_requires_approval)
		else:
			self.payment_status = REFUND_DUE
		self.flags.set_by_code = True
		self.save(ignore_permissions=True)

	def has_free_seats(self, limits: frappe._dict) -> bool:
		"""True when the seats, limited items and people of this sign-up are free, under the Function lock."""
		people = {self.person, *self.get_attendee_people()} - {None, ""}
		return not (
			self.get_full_capacity(limits, get_seats_taken(self.function, self.name))
			or self.get_item_problem()
			or self.get_people_signed_up(people, for_update=True)
		)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_function_items(
	doctype: str, txt: str, searchfield: str, start: int, page_len: int, filters: dict | None
):
	"""Search query: only Sign-Up Items configured on the given Function."""
	function = (filters or {}).get("function")
	if not function:
		return []
	frappe.has_permission("Function", doc=function, throw=True)
	Item = frappe.qb.DocType("Function Sign-Up Item")
	return (
		frappe.qb.from_(Item)
		.select(Item.item)
		.where((Item.parent == function) & (Item.parenttype == "Function") & Item.item.like(f"%{txt or ''}%"))
		.orderby(Item.idx)
		.limit(page_len or 20)
		.offset(start or 0)
		.run()
	)


@frappe.whitelist()
def get_item_status(function: str, item: str, exclude_sign_up: str | None = None):
	"""Return live quantity_needed (from the Function) and quantity_signed_up
	(summed across all Function Sign-Ups for the same function/item).

	Args:
		function: Function document name.
		item: Sign-Up Item name.
		exclude_sign_up: Optional Function Sign-Up name to exclude from totals
			(used when editing an existing sign-up to show others' contributions).
	"""
	frappe.has_permission("Function", doc=function, throw=True)
	qty_needed = frappe.db.get_value(
		"Function Sign-Up Item",
		{"parent": function, "parenttype": "Function", "item": item},
		"quantity_needed",
	)

	Item = frappe.qb.DocType("Function Sign-Up Item")
	# church-scope: keyed to one function, which the caller has been checked against
	SignUp = frappe.qb.DocType("Function Sign-Up")

	query = (
		frappe.qb.from_(Item)
		.join(SignUp)
		.on(SignUp.name == Item.parent)
		.select(Coalesce(Sum(Item.my_quantity), 0).as_("total"))
		.where(
			(SignUp.function == function)
			& (Item.parenttype == "Function Sign-Up")
			& (Item.item == item)
			& holds_seats(SignUp)
		)
	)
	if exclude_sign_up:
		query = query.where(SignUp.name != exclude_sign_up)

	result = query.run(as_dict=True)
	qty_signed_up = (result[0].total if result else 0) or 0

	return {
		"quantity_needed": qty_needed or 0,
		"quantity_signed_up": int(qty_signed_up),
	}


@frappe.whitelist()
def get_function_item_totals(function: str, exclude_sign_up: str | None = None):
	"""Return live quantity_signed_up totals for every item configured on a Function.

	Returns a dict mapping item -> {quantity_needed, quantity_signed_up}.
	"""
	frappe.has_permission("Function", doc=function, throw=True)
	return get_item_totals(function, exclude_sign_up)


def is_open_for_sign_up(function):
	"""True when the session may sign up now, inside the function's sign-up window.

	A portal member signs up for their church's or a shared function, and a guest for a published one
	with guest sign-ups.
	"""
	if frappe.session.user == "Guest":
		filters = {"name": function, "allow_sign_ups": 1, "publish": 1, "allow_guest_sign_ups": 1}
	else:
		filters = church_filters(session_church(), name=function, allow_sign_ups=1)
	window = frappe.db.get_value("Function", filters, WINDOW_FIELDS, as_dict=True)
	return bool(window) and is_in_sign_up_window(window)


def is_in_sign_up_window(function: dict) -> bool:
	"""True when now is between the function's Sign-Ups Open On and Close On. A blank date sets no limit."""
	now = now_datetime()
	opens, closes = function.get("sign_ups_open_on"), function.get("sign_ups_close_on")
	return (not opens or get_datetime(opens) <= now) and (not closes or now < get_datetime(closes))


def get_function_calendar(function: str) -> str:
	"""A calendar file of *function* alone, under the same UID as its event in the public calendar."""
	row = frappe.db.get_value("Function", function, EVENT_FIELDS, as_dict=True)
	summary = row.function_name or row.title or row.name
	location = _format_address(row.address, {})
	event = make_event(row.name, row, summary, row.modified, description=row.description, location=location)
	return make_calendar(summary, [event])


def link_registrant(sign_up: str) -> None:
	"""Background job after a sign-up with no Person commits: link the one person who strongly matches
	what the registrant typed, else add them as a Visitor.

	It runs as whoever signed up, a guest on /register, so its writes skip permissions. A person already on
	another sign-up of the function is not linked again; a comment names that sign-up for staff.
	"""
	function = frappe.db.get_value("Function Sign-Up", sign_up, "function")
	frappe.db.get_value("Function", function, "name", for_update=True)  # before the sign-up row
	doc = frappe.get_doc("Function Sign-Up", sign_up, for_update=True)
	if doc.person:
		return

	first_name, _space, last_name = doc.registrant_name.strip().rpartition(" ")
	if not first_name:
		first_name, last_name = last_name, None
	candidate = {
		"first_name": first_name,
		"last_name": last_name,
		"emails": [doc.email],
		"phones": [doc.phone] if doc.phone else [],
	}
	# A shared function has no church, so a guest is matched and added at the church that shared it.
	person, _added = find_or_add_person(candidate, doc.payment_church, SIGN_UP_SOURCE)

	# A locking read sees the link another job committed while this one waited for the Function lock.
	other = frappe.db.get_value(
		"Function Sign-Up",
		{"function": doc.function, "person": person, "name": ("!=", doc.name), "status": ("!=", CANCELLED)},
		for_update=True,
	)
	if not other and person in doc.get_people_signed_up({person}):
		other = _("another sign-up")
	if other:
		doc.add_comment(
			"Comment",
			_("Not linked to {0}, who is already signed up for this function on {1}.").format(person, other),
		)
		return

	doc.person = person
	doc.flags.ignore_permissions = doc.flags.set_by_code = True
	doc.save()


def get_item_totals(function, exclude_sign_up=None, for_update=False):
	"""Totals for get_function_item_totals. Callers check first that the reader may see *function*.

	*for_update* makes the count a locking read, for a count under the Function row lock (`get_seats_taken`).
	"""
	function_items = frappe.db.get_all(
		"Function Sign-Up Item",
		filters={"parent": function, "parenttype": "Function"},
		fields=["item", "quantity_needed"],
	)

	Item = frappe.qb.DocType("Function Sign-Up Item")
	# church-scope: keyed to one function, which the caller has been checked against
	SignUp = frappe.qb.DocType("Function Sign-Up")

	query = (
		frappe.qb.from_(Item)
		.join(SignUp)
		.on(SignUp.name == Item.parent)
		.select(Item.item, Coalesce(Sum(Item.my_quantity), 0).as_("total"))
		.where((SignUp.function == function) & (Item.parenttype == "Function Sign-Up") & holds_seats(SignUp))
	)
	if exclude_sign_up:
		query = query.where(SignUp.name != exclude_sign_up)
	if for_update:
		query = query.for_update()

	totals = {row.item: int(row.total or 0) for row in query.groupby(Item.item).run(as_dict=True)}

	return {
		row.item: {
			"quantity_needed": row.quantity_needed or 0,
			"quantity_signed_up": totals.get(row.item, 0),
		}
		for row in function_items
	}


def get_list_context(context):
	context.filters = {"owner": frappe.session.user}
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		from frappe.www.list import get_list as default_get_list

		rows = default_get_list(doctype, txt, filters, limit_start, limit_page_length, **kwargs)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context


def get_attendee_key(row) -> tuple:
	"""What `set_attendees` checks on an attendee row."""
	return row.person, row.attendee_name, row.selection


def holds_seats(SignUp):
	"""The query condition for sign-ups that hold their seats and items: Confirmed, or Pending with no expired hold."""
	live_hold = SignUp.hold_expires_on.isnull() | (SignUp.hold_expires_on >= now_datetime())
	return (SignUp.status == CONFIRMED) | ((SignUp.status == PENDING) & live_hold)


def get_seat_limits(function: str) -> frappe._dict:
	"""*function*'s capacity, approval rule and capacity by selection, read under its row lock.

	Every change to its seats takes this lock first, so each locking count after it sees the seats the others took.
	"""
	limits = frappe.db.get_value(
		"Function",
		function,
		["function_name", "capacity", "sign_up_requires_approval"],
		as_dict=True,
		for_update=True,
	)
	# church-scope: the selections of one function, whose row is locked above
	rows = frappe.get_all(
		"Function Sign-Up Selection",
		filters={"parent": function, "parenttype": "Function"},
		fields=["selection", "capacity"],
	)
	limits.selections = {row.selection: cint(row.capacity) for row in rows}
	return limits


def get_seats_taken(function: str, exclude_sign_up: str | None) -> Counter:
	"""The seats the other sign-ups of *function* hold, in all and by selection.

	A locking read: under REPEATABLE READ a plain count answers from the snapshot this request took
	before it waited for the Function lock, and misses the seats another request committed meanwhile.
	"""
	SignUp = frappe.qb.DocType("Function Sign-Up")
	Attendee = frappe.qb.DocType("Function Sign-Up Attendee")
	# church-scope: the seats of one function, counted and never shown
	selections = (
		frappe.qb.from_(Attendee)
		.join(SignUp)
		.on(SignUp.name == Attendee.parent)
		.select(Attendee.selection)
		.where(
			(SignUp.function == function)
			& (Attendee.parenttype == "Function Sign-Up")
			& (SignUp.name != (exclude_sign_up or ""))
			& holds_seats(SignUp)
		)
		.for_update()
		.run(pluck=True)
	)
	taken = Counter(("selection", selection) for selection in selections)
	taken["seats"] = len(selections)
	return taken


def promote_waitlist(function: str) -> None:
	"""Give free seats of *function* to the oldest waiting parties that fit, under the Function row lock."""
	limits = get_seat_limits(function)
	# church-scope: the waitlist of one function, which code moves on and nobody reads
	waiting = frappe.db.get_values(
		"Function Sign-Up",
		{"function": function, "status": WAITLISTED},
		"name",
		order_by="creation asc",
		for_update=True,
		pluck=True,
	)
	for name in waiting:
		sign_up = frappe.get_doc("Function Sign-Up", name)
		if sign_up.get_full_capacity(limits, get_seats_taken(function, name)) or sign_up.get_item_problem():
			continue
		sign_up.flags.set_by_code = sign_up.flags.promote = True
		sign_up.save(ignore_permissions=True)


def release_expired_holds() -> None:
	"""Cron: cancel Pending sign-ups whose hold expired, then promote each function's waitlist."""
	# church-scope: a job over every church; each hold is released on its own function
	expired = frappe.get_all(
		"Function Sign-Up",
		# "is set" too: a "<" filter alone also matches a sign-up with no hold, which waits for approval.
		filters=[
			["status", "=", PENDING],
			["hold_expires_on", "is", "set"],
			["hold_expires_on", "<", now_datetime()],
		],
		fields=["name", "function"],
	)
	for function in sorted({row.function for row in expired}):
		try:
			get_seat_limits(function)  # the Function lock, before the sign-up rows
			for name in (row.name for row in expired if row.function == function):
				sign_up = frappe.get_doc("Function Sign-Up", name, for_update=True)
				hold = sign_up.hold_expires_on
				if sign_up.status == PENDING and hold and get_datetime(hold) < now_datetime():
					sign_up.status = CANCELLED
					sign_up.flags.set_by_code = True
					sign_up.save(ignore_permissions=True)
			promote_waitlist(function)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				_("Could not release the expired holds of {0}").format(function),
				reference_doctype="Function",
				reference_name=function,
			)
