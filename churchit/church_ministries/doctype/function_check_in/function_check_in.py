# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, today

from churchit.church_ministries.attendance import record, remove
from churchit.church_ministries.check_in_limits import refuse_a_full_room
from churchit.church_people import household
from churchit.church_scope import default_church, refuse_another_churches_parent

CHECKED_IN = "Checked-In"
REGULAR = "Regular"
VOLUNTEER = "Volunteer"
# Set only by add_check_ins (the code), checkout.check_out and check_in.release (who took a person).
CHECKOUT_FIELDS = (
	"collected_at",
	"collected_by",
	"collected_by_name",
	"released_by",
	"override_reason",
	"overridden_by",
	"security_code",
)

# Letters and digits that are hard to confuse on a printed tag.
SECURITY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class FunctionCheckIn(Document):
	def before_insert(self):
		# A form or REST insert passes the room limit here; add_check_ins checked it for its whole group.
		if self.function and not self.flags.ignore_permissions:
			frappe.db.get_value("Function", self.function, "name", for_update=True)
			refuse_a_full_room(self.function, 0 if self.check_in_kind == VOLUNTEER else 1)

	def validate(self):
		refuse_another_churches_parent(
			self,
			"function",
			_("{0} belongs to another church, so only that church can check people in to it."),
		)
		# Prevent duplicate check-ins for the same function and person
		if frappe.db.exists(
			"Function Check-In", {"function": self.function, "person": self.person, "name": ("!=", self.name)}
		):
			frappe.throw(_("This person has already been checked in to this function."))
		# Frappe does not enforce read_only on insert, so a form or REST insert could forge a code or release.
		if self.is_new():
			is_untrusted = not self.flags.ignore_permissions and any(
				self.get(field) for field in CHECKOUT_FIELDS
			)
		else:
			is_untrusted = not self.flags.checkout and any(
				self.has_value_changed(field) for field in CHECKOUT_FIELDS
			)
		if is_untrusted:
			frappe.throw(
				_("The security code and the checkout are set only at the Check-In Station."),
				frappe.PermissionError,
			)

	def before_save(self):
		function_label = (
			frappe.db.get_value("Function", self.function, "function_name") if self.function else ""
		)
		person_label = frappe.db.get_value("Person", self.person, "full_name") if self.person else ""
		parts = [function_label or "", person_label or ""]
		self.title = " - ".join(p for p in parts if p)

		record(self.person, self.function, CHECKED_IN)

	def on_trash(self):
		# A checked-out check-in records who took the person. Only system code deletes it.
		if self.collected_at and not self.flags.ignore_permissions:
			frappe.throw(_("This person has been checked out, so their check-in cannot be undone."))
		if remove(self.person, self.function, CHECKED_IN):
			frappe.msgprint(_("The associated attendance record has been removed."), alert=True)


def is_shared_function(function_name):
	"""True when the function is shared with every church."""
	return bool(cint(frappe.db.get_value("Function", function_name, "is_shared")))


def new_security_code():
	return "".join(secrets.choice(SECURITY_CODE_ALPHABET) for _ in range(4))


@frappe.whitelist(methods=["POST"])
def check_in_persons(function_name: str, persons: str | list[str], kind: str | None = None):
	"""Check *persons* in to a function as *kind* (Regular when not given), after the permission checks."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	# The inserts below ignore permissions, so the function and every person are checked here.
	frappe.has_permission("Function", doc=function_name, throw=True)
	persons = frappe.parse_json(persons)
	# A shared function is a joint service: any church's people may come.
	if not is_shared_function(function_name):
		for person in persons:
			frappe.has_permission("Person", doc=person, throw=True)

	return add_check_ins(function_name, persons, kind or REGULAR)


def add_check_ins(function: str, persons: list[str], kind: str = REGULAR) -> list[str]:
	"""Check *persons* in to *function* and return their check-ins in order. The caller checks permissions.

	A person already checked in keeps their check-in, and their attendance is Checked-In again.
	"""
	# The Function row, then the code lock, then check-in rows: the order of every writer, so none deadlock.
	frappe.db.get_value("Function", function, "name", for_update=True)
	is_coded = frappe.db.get_single_value("Check-In Settings", "security_codes", for_update=True)

	unique = list(dict.fromkeys(persons))
	# A locking read: a plain one answers from the request's older snapshot and misses another station's row.
	names = dict(
		frappe.db.get_values(
			"Function Check-In",
			{"function": function, "person": ("in", unique)},
			["person", "name"],
			for_update=True,
		)
	)
	for person in names:
		record(person, function, CHECKED_IN)

	new = [person for person in unique if person not in names]
	refuse_a_full_room(function, 0 if kind == VOLUNTEER else len(new))
	code = get_security_code(new) if new and kind != VOLUNTEER and is_coded else None
	for person in new:
		check_in = frappe.get_doc(
			{
				"doctype": "Function Check-In",
				"function": function,
				"person": person,
				"check_in_kind": kind,
				"security_code": code,
			}
		).insert(ignore_permissions=True)
		names[person] = check_in.name
	return [names[person] for person in persons]


def get_security_code(persons: list[str]) -> str:
	"""The oldest code a check-in of *persons* or their households got today, else a code no check-in has today.

	Verify Pickup finds a code at any church, so a code is unique on the site for the day. The Check-In
	Settings row lock holds to commit, so a second station waits and then sees this code. The reads after it
	lock too: a plain read answers from the request's older snapshot.
	"""
	frappe.db.get_single_value("Check-In Settings", "security_codes", for_update=True)

	people = set(persons)
	for person in persons:
		if family := frappe.db.get_value("Person", person, "family"):
			people.update(household.members(family))

	# church-scope: codes are unique across the whole site each day, and a household keeps one at any church
	held = frappe.db.get_values(
		"Function Check-In",
		{"creation": (">=", today()), "security_code": ("is", "set")},
		["person", "security_code"],
		order_by="creation asc",
		for_update=True,
	)
	household_code = next((code for person, code in held if person in people), None)
	if household_code:
		return household_code

	used = {code for _person, code in held}
	code = new_security_code()
	while code in used:
		code = new_security_code()
	return code


@frappe.whitelist(methods=["POST"])
def print_name_tags(check_ins: str | list[str] | None = None, persons: str | list[str] | None = None):
	"""Name tags for saved check-ins, or plain tags for people who are not checked in."""
	docs = [frappe.get_doc("Function Check-In", name) for name in frappe.parse_json(check_ins) or []]
	for doc in docs:
		doc.check_permission("read")
	for person in frappe.parse_json(persons) or []:
		frappe.has_permission("Person", doc=person, throw=True)
		docs.append(frappe.get_doc({"doctype": "Function Check-In", "person": person}))
	if not docs:
		frappe.throw(_("Nothing to print."))
	# The operator prints at their own campus, so their church's printer is the one.
	settings = frappe.get_single("Check-In Settings").for_church(default_church())
	return settings.print_name_tags(docs)
