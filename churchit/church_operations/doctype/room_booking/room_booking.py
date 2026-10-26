# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import get_datetime

from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import (
	church_filters,
	has_church_access,
	inherits_a_shared_church,
	refuse_another_churches_parent,
	refuse_another_churches_record,
	session_church,
	session_person,
)
from churchit.questions import YES, get_fields, get_questions, set_answers

# Roles that approve the bookings of a room with no Approvers list.
APPROVER_ROLES = {"Church Manager", "System Manager"}
# Roles a user on a room's Approvers list needs to approve its bookings.
LISTED_APPROVER_ROLES = {"Church Staff", "Church Manager"}
DECIDED_NOTIFICATION = "Room Booking Decided"
DECIDED_MESSAGE = """<p>Your room booking is {{ doc.status | lower }}.</p>

<ul>
  {% if doc.room %}<li><strong>Room:</strong> {{ frappe.db.get_value("Room", doc.room, "room_name") }}</li>{% endif %}
  <li><strong>Purpose:</strong> {{ doc.purpose }}</li>
  <li><strong>Start:</strong> {{ frappe.utils.format_datetime(doc.start_datetime) }}</li>
  <li><strong>End:</strong> {{ frappe.utils.format_datetime(doc.end_datetime) }}</li>
</ul>
"""


class RoomBooking(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "room", _("{0} belongs to another church, so only that church can book it.")
		)
		self.set_portal_requester()
		self.refuse_a_request_with_no_requester()
		self.refuse_another_churches_requester()
		self.refuse_another_churches_function()
		if self.end_datetime and self.start_datetime:
			# REST sends text, which compares as text.
			self.start_datetime = get_datetime(self.start_datetime)
			self.end_datetime = get_datetime(self.end_datetime)
			if self.end_datetime <= self.start_datetime:
				frappe.throw(_("End time must be after start time."))
		self.refuse_a_booking_of_nothing()
		# No room: the mandatory-field check reports it.
		room = frappe.db.get_value(
			"Room", self.room, ["is_bookable", "requires_approval"], as_dict=True
		) or frappe._dict(is_bookable=1)
		self.refuse_a_room_that_is_not_bookable(room.is_bookable)
		self.refuse_a_room_outside_the_members_church()
		self.refuse_assets_that_cannot_be_booked()
		self.set_initial_status(room.requires_approval)
		self.reset_approval(room.requires_approval)
		self.validate_approver(room.requires_approval)
		self.validate_blocked()
		self.validate_setup()
		self.set_room_answers()
		self.check_conflicts()
		self.check_asset_conflicts()

	def on_update(self):
		self.update_approver_assignments()
		self.deny_requests_a_block_overlaps()

	def on_trash(self):
		if self.status == "Blocked" and not self.flags.ignore_permissions and not self.is_approver():
			frappe.throw(
				_("Only an approver of this room can remove its blocked time."), frappe.PermissionError
			)

	def is_moved(self):
		return any(self.has_value_changed(field) for field in ("room", "start_datetime", "end_datetime"))

	def refuse_a_request_with_no_requester(self):
		"""The desk asks for a requester through mandatory_depends_on, which only the form checks."""
		if self.status != "Blocked" and not self.requester:
			frappe.throw(_("Choose a Requester, or set the status to Blocked."), frappe.MandatoryError)

	def refuse_another_churches_requester(self):
		if self.flags.ignore_permissions or not self.has_value_changed("requester"):
			return
		refuse_another_churches_record(self, "Person", self.requester)

	def refuse_another_churches_function(self):
		"""Refuse a Function of another church: its public event would list this booking's room.

		A booking of a shared room belongs to every church, so it may serve any church's Function.
		"""
		if self.flags.ignore_permissions or not (
			self.has_value_changed("function") or self.has_value_changed("room")
		):
			return
		if self.room and inherits_a_shared_church(self):
			return
		refuse_another_churches_record(self, "Function", self.function)

	def refuse_a_room_that_is_not_bookable(self, is_bookable):
		if not is_bookable and self.is_moved():
			frappe.throw(
				_("{0} is not bookable.").format(frappe.get_cached_value("Room", self.room, "room_name"))
			)

	def is_approver(self) -> bool:
		"""True when the session user approves the bookings of this booking's room."""
		return bool(self.room) and frappe.get_doc("Room", self.room).is_approver(frappe.session.user)

	def onload(self):
		self.set_onload("is_approver", self.is_approver())

	def set_initial_status(self, requires_approval):
		"""Approve a new booking at once on an open room, or when its room's approver makes it.

		A write with ignore_permissions (a recurrence copy) is not an approver's choice, so it stays
		Requested. A booking made as Denied, Cancelled or Blocked is left alone.
		"""
		if not self.is_new() or self.status not in (None, "", "Requested"):
			return
		if not requires_approval or (not self.flags.ignore_permissions and self.is_approver()):
			self.status = "Approved"

	def reset_approval(self, requires_approval):
		"""Send a moved booking back for approval, unless an approver moved it."""
		if not requires_approval or self.status != "Approved" or self.is_new():
			return
		if self.get_doc_before_save().status != "Approved" or not self.is_moved():
			return
		if not self.is_approver():
			self.status = "Requested"

	def validate_approver(self, requires_approval):
		"""Let only an approver of an approval-gated room approve or deny its bookings, or reopen a denied one.

		Church Users hold write access to their own bookings, so without this a
		requester could approve the very booking they submitted. A requester may still cancel.
		"""
		before = self.get_doc_before_save()
		before_status = before.status if before else None
		if not requires_approval or self.status == before_status:
			return
		if self.status == "Approved" and not self.is_approver():
			frappe.throw(_("Only an approver of this room can approve a booking for it."))
		is_reopened = before_status == "Denied" and self.status != "Cancelled"
		if (self.status == "Denied" or is_reopened) and not self.is_approver():
			frappe.throw(
				_("Only an approver of this room can deny a booking for it, or reopen a denied one.")
			)

	def check_conflicts(self):
		"""Refuse a booking that clashes, or mark it Conflict when the requester asks anyway.

		A Blocked time always wins, and only an Approved booking refuses a Blocked one.
		"""
		if not self.room or self.status in ("Denied", "Cancelled"):
			return
		# Under the Room lock, so two saves at once cannot both miss each other.
		frappe.db.get_value("Room", self.room, "name", for_update=True)
		clashes = [clash for clash in self.get_room_clashes() if self.is_clash(clash)]
		if not clashes:
			return
		is_blocked = self.status == "Blocked" or any(clash.status == "Blocked" for clash in clashes)
		if self.request_anyway and not is_blocked:
			self.status = "Conflict"
			return
		frappe.throw(
			_("Room is already booked at that time (conflicts with: {0}).").format(
				describe_clashes([(clash.name, clash.church) for clash in clashes])
			)
		)

	def get_room_clashes(self) -> list[frappe._dict]:
		"""The other bookings that hold this room at an overlapping time, read with a lock."""
		# church-scope: a shared room is booked by several churches, so a clash has to be
		# found across all of them, not only the booking church's own diary
		Booking = frappe.qb.DocType("Room Booking")
		return (
			frappe.qb.from_(Booking)
			.select(Booking.name, Booking.church, Booking.status, Booking.can_share_room)
			.where(
				(Booking.room == self.room)
				& (Booking.name != (self.name or ""))
				& Booking.status.isin(["Requested", "Approved", "Blocked", "Conflict"])
				& (Booking.start_datetime < self.end_datetime)
				& (Booking.end_datetime > self.start_datetime)
			)
			.for_update()
			.run(as_dict=True)
		)

	def is_clash(self, other: frappe._dict) -> bool:
		if self.status == "Blocked":
			return other.status == "Approved"
		if other.status == "Blocked":
			return True
		if other.status == "Conflict":
			return False
		return not (self.can_share_room and other.can_share_room)

	@frappe.whitelist(methods=["POST"])
	def approve(self):
		self.decide("Approved")

	@frappe.whitelist(methods=["POST"])
	def deny(self):
		self.decide("Denied")

	def decide(self, status: str) -> None:
		"""Set a Requested booking to *status*, for an approver of its room."""
		self.load_stored_for_an_approver()
		if self.status != "Requested":
			frappe.throw(_("Only a Requested booking can be approved or denied."))
		self.status = status
		self.save(ignore_permissions=True)

	@frappe.whitelist(methods=["POST"])
	def resolve_conflict(self, action: str):
		"""Keep this booking and deny the requests it clashes with, or share the room with them."""
		self.load_stored_for_an_approver()
		if self.status != "Conflict" or action not in ("keep", "share"):
			frappe.throw(_("Only a Conflict booking can be resolved, by keep or share."))
		frappe.db.get_value("Room", self.room, "name", for_update=True)
		for clash in self.get_room_clashes():
			is_shared = self.can_share_room and clash.can_share_room
			if action == "keep" and clash.status in ("Requested", "Conflict") and not is_shared:
				set_booking_values(clash.name, status="Denied")
			elif action == "share" and clash.status != "Blocked" and not clash.can_share_room:
				set_booking_values(clash.name, can_share_room=1)
		# Without request_anyway, a clash that is still left refuses the approval.
		self.status, self.request_anyway = "Approved", 0
		if action == "share":
			self.can_share_room = 1
		self.save(ignore_permissions=True)

	def load_stored_for_an_approver(self) -> None:
		"""Load the stored booking for an approver of its room, who may hold no write right on it."""
		frappe.only_for(APPROVER_ROLES | LISTED_APPROVER_ROLES)
		self.reload()
		self.check_permission("read")
		if not self.is_approver():
			frappe.throw(_("Only an approver of this room can decide its bookings."), frappe.PermissionError)

	def set_portal_requester(self):
		"""A member, or anyone on the Room Request form, books only for themselves."""
		if not (is_portal_member() or frappe.flags.in_web_form):
			return
		own_person = session_person()
		if not own_person:
			frappe.throw(_("No Person record is linked to your account."))
		# Staff can open any booking of their church on the form; that must not move it to them.
		if not self.is_new() and self.get_doc_before_save().requester != own_person:
			frappe.throw(_("You can change only your own requests here."), frappe.PermissionError)
		self.requester = own_person

	def refuse_a_room_outside_the_members_church(self):
		"""Under the web form's ignore_permissions too, a member asks only for a room get_bookable_rooms offers."""
		if not (is_portal_member() or frappe.flags.in_web_form):
			return
		if self.room and self.has_value_changed("room") and self.room not in get_bookable_rooms():
			frappe.throw(_("You can ask only for a bookable room of your church."), frappe.PermissionError)

	def refuse_a_booking_of_nothing(self):
		if not self.room and not self.assets:
			frappe.throw(_("Choose a room or some equipment to book."), frappe.MandatoryError)

	def refuse_assets_that_cannot_be_booked(self):
		"""Refuse an asset this save adds that is not bookable or belongs to another church.

		A moved booking checks each asset again, as it does its room. A member asks for a room only, so staff book
		the equipment. A booking of a shared room acts for the church that made it, also in a recurrence copy.
		"""
		before = self.get_doc_before_save()
		stored = {row.asset for row in before.assets} if before else set()
		added = {row.asset for row in self.assets} - stored
		if added and (is_portal_member() or frappe.flags.in_web_form):
			frappe.throw(_("Only staff can book equipment."), frappe.PermissionError)
		for asset in {row.asset for row in self.assets} if self.is_moved() else added:
			# The church first: the message below shows the title.
			refuse_another_churches_record(self, "Church Asset", asset, self.church or self.shared_by_church)
			values = frappe.db.get_value("Church Asset", asset, ["title", "is_bookable"], as_dict=True)
			if not values.is_bookable:
				frappe.throw(_("{0} is not bookable.").format(values.title))

	def check_asset_conflicts(self):
		"""Refuse a booking of an asset that another booking holds at an overlapping time.

		Unlike a room, an asset is never shared between bookings and never requested anyway.
		"""
		assets = sorted({row.asset for row in self.assets})
		if not assets or self.status in ("Denied", "Cancelled"):
			return
		# Locks go in the order a save with a room takes them: the Room Booking rows (as check_conflicts does), each
		# asset in one order, then the Room Booking Asset rows. So two saves at once neither deadlock nor both pass.
		self.get_overlapping_bookings()
		for asset in assets:
			frappe.db.get_value("Church Asset", asset, "name", for_update=True)
		# Read again: a save that held an asset's lock may have committed since.
		bookings = dict(self.get_overlapping_bookings())
		if not bookings:
			return
		BookingAsset = frappe.qb.DocType("Room Booking Asset")
		clashes = (
			frappe.qb.from_(BookingAsset)
			.select(BookingAsset.parent)
			.distinct()
			.where(
				(BookingAsset.parenttype == "Room Booking")
				& BookingAsset.parent.isin(list(bookings))
				& BookingAsset.asset.isin(assets)
			)
			.for_update()
			.run(pluck=True)
		)
		if clashes:
			frappe.throw(
				_("Equipment is already booked at that time (conflicts with: {0}).").format(
					describe_clashes([(name, bookings[name]) for name in sorted(clashes)])
				)
			)

	def get_overlapping_bookings(self) -> list[tuple[str, str]]:
		"""(name, church) of the other bookings that hold their equipment at an overlapping time, read with a lock."""
		# church-scope: a shared asset is booked by several churches, so a clash has to be
		# found across all of them, not only the booking church's own diary
		Booking = frappe.qb.DocType("Room Booking")
		return (
			frappe.qb.from_(Booking)
			.select(Booking.name, Booking.church)
			.where(
				(Booking.name != (self.name or ""))
				& Booking.status.isin(["Requested", "Approved", "Conflict"])
				& (Booking.start_datetime < self.end_datetime)
				& (Booking.end_datetime > self.start_datetime)
			)
			.for_update()
			.run()
		)

	def validate_blocked(self):
		"""Let only an approver of the room block a time, or change a blocked time."""
		before = self.get_doc_before_save()
		if self.status != "Blocked" and not (before and before.status == "Blocked"):
			return
		if not self.room:
			frappe.throw(_("Choose the room to block."))
		if not self.is_approver():
			frappe.throw(_("Only an approver of this room can block its time."), frappe.PermissionError)

	def update_approver_assignments(self):
		"""Assign a booking that waits for a decision to its room's approvers, and close that when decided or moved."""
		is_room_changed = self.has_value_changed("room")
		if not (self.has_value_changed("status") or is_room_changed):
			return
		is_waiting = self.status in ("Requested", "Conflict")
		if not is_waiting or is_room_changed:
			assign_to.close_all_assignments(self.doctype, self.name, ignore_permissions=True)
		if not is_waiting or not self.room:
			return
		assigned = frappe.get_all(
			"ToDo",
			filters={"reference_type": self.doctype, "reference_name": self.name, "status": "Open"},
			pluck="allocated_to",
		)
		approvers = [
			user for user in frappe.get_doc("Room", self.room).get_approvers() if user not in assigned
		]
		if approvers:
			assign_to._add(
				{"assign_to": approvers, "doctype": self.doctype, "name": self.name}, ignore_permissions=True
			)

	def deny_requests_a_block_overlaps(self):
		if self.status != "Blocked":
			return
		for clash in self.get_room_clashes():
			if clash.status in ("Requested", "Conflict"):
				set_booking_values(clash.name, status="Denied")

	def validate_setup(self):
		"""Refuse a setup that the booking's room does not offer. A setup taken off the room later stays."""
		if not self.setup or not (self.has_value_changed("setup") or self.has_value_changed("room")):
			return
		if not self.room:
			frappe.throw(_("Choose a room for the setup {0}.").format(frappe.bold(self.setup)))
		if not frappe.db.exists(
			"Room Setup", {"parenttype": "Room", "parent": self.room, "setup_name": self.setup}
		):
			room_name = frappe.get_cached_value("Room", self.room, "room_name")
			frappe.throw(_("{0} is not a setup of {1}.").format(frappe.bold(self.setup), room_name))

	def set_room_answers(self):
		"""Keep the answers to the room's Question Set as Question Answer rows.

		While the room and the answers stay as saved, the rows stay too, so a decision or a later change to the room's
		set does not refuse the booking. After a change of room, answers to another set are dropped. A blocked time
		is no request, so it asks nothing and keeps no answers.
		"""
		if self.status == "Blocked":
			self.set("answers", [])
			return

		answers = {row.question: row.answer for row in self.answers}
		before = self.get_doc_before_save()
		is_unchanged = (
			before
			and before.room == self.room
			and answers == {row.question: row.answer for row in before.answers}
		)
		if is_unchanged:
			return

		question_set = frappe.db.get_value("Room", self.room, "question_set") if self.room else None
		questions = get_questions(question_set) if question_set else []
		if before and not answers.keys() <= {question.fieldname for question in questions}:
			self.set("answers", [])
			answers = {}
		if question_set:
			# A kept tick reads Yes, and set_answers counts only 1 or true as ticked.
			ticks = {question.fieldname for question in questions if question.question_type == "Check"}
			answers = {
				name: "1" if name in ticks and answer == YES else answer for name, answer in answers.items()
			}
			set_answers(self, question_set, answers)
		elif answers:
			frappe.throw(_("The room of this booking asks no questions."))


def describe_clashes(conflicts: list[tuple[str, str]]) -> str:
	"""The clashing bookings, as (name, church) pairs, named only where the user can see their church."""
	clashes = [name for name, church in conflicts if has_church_access(frappe.session.user, church)]
	hidden = len(conflicts) - len(clashes)
	if hidden:
		clashes.append(_("{0} booking(s) of another church").format(hidden))
	return ", ".join(clashes)


def get_bookable_rooms() -> dict[str, str]:
	"""{name: room_name} of the rooms the signed-in member may ask for: their church's bookable ones and shared ones.

	The web form cannot ask a room's questions, so a room with a required question is booked by staff.
	"""
	if not session_person():
		return {}
	asks = set(
		frappe.get_all(
			"Question Set Question", filters={"parenttype": "Question Set", "is_required": 1}, pluck="parent"
		)
	)
	rooms = frappe.get_all(
		"Room",
		filters=church_filters(session_church(), is_bookable=1),
		fields=["name", "room_name", "question_set"],
		order_by="room_name asc",
	)
	return {room.name: room.room_name for room in rooms if room.question_set not in asks}


def set_booking_values(name: str, **values) -> None:
	"""Save a decision on another booking with a real save, so its checks, ToDos and notification run."""
	booking = frappe.get_doc("Room Booking", name)
	booking.update(values)
	booking.save(ignore_permissions=True)


def create_decided_notification() -> None:
	"""Insert the Notification that tells the maker of a booking it was approved or denied, once.

	It is not standard, because production cannot enable a shipped one, and a church may change it.
	"""
	if frappe.db.exists("Notification", DECIDED_NOTIFICATION):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": DECIDED_NOTIFICATION,
			"subject": "Room booking {{ doc.status | lower }}: {{ doc.purpose }}",
			"document_type": "Room Booking",
			"event": "Value Change",
			"value_changed": "status",
			"condition_type": "Python",
			"condition": 'doc.status in ("Approved", "Denied")',
			"channel": "Email",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"recipients": [{"receiver_by_document_field": "owner"}],
			"message_type": "HTML",
			"message": DECIDED_MESSAGE,
		}
	).insert(ignore_permissions=True)


@frappe.whitelist(methods=["GET"])
def get_room_questions(room: str) -> list[dict]:
	"""The fields that ask the questions of *room*'s Question Set, for the booking form."""
	doc = frappe.get_doc("Room", room)
	doc.check_permission("read")
	return get_fields(doc.question_set) if doc.question_set else []
