# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The self check-in kiosk: a household finds itself by its phone number and checks itself in.

A kiosk is a User whose one role is Church Check-In Kiosk, with one Church permission and a fixed IP
(Restrict IP). The role has no DocPerms, so the reads here run past permissions and send only what a
kiosk may show: the church's open self check-in Functions and the names, photos and grades of the
household of one whole phone number.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate, today

from churchit.church_ministries.check_in_limits import get_bound_problem, is_check_in_open
from churchit.church_ministries.doctype.function_check_in.function_check_in import add_check_ins
from churchit.church_ministries.page.check_in.check_in import group_by_family
from churchit.church_scope import (
	allowed_churches,
	church_filters,
	is_multi_church,
	is_people_directory_private,
	root_church,
)
from churchit.contacts import phone_digits
from churchit.www.directory import is_public

KIOSK_ROLE = "Church Check-In Kiosk"
# A whole phone number, so a kiosk cannot walk the directory a few digits at a time.
MIN_PHONE_DIGITS = 7
# Every kiosk behind one church IP shares this, so it allows a busy Sunday morning.
REQUESTS_PER_HOUR = 600


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REQUESTS_PER_HOUR, seconds=60 * 60)
def find_household(phone: str) -> dict:
	"""The open Functions, and the people of *phone*'s households with the Functions each may check in to."""
	frappe.only_for(KIOSK_ROLE)
	return get_households(phone, get_church())


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REQUESTS_PER_HOUR, seconds=60 * 60)
def check_in(phone: str, choices: str | dict) -> dict:
	"""Check each person of *choices* ({person: function}) in, and print the tags of the new check-ins.

	The households are found again from *phone*, so a kiosk checks in only whom it was offered, and where.
	Only new check-ins print, and never with a code an earlier check-in holds: a phone number is no credential.
	"""
	frappe.only_for(KIOSK_ROLE)
	church = get_church()
	choices = frappe.parse_json(choices)
	chosen = (
		{(person, str(function)) for person, function in choices.items()}
		if isinstance(choices, dict)
		else set()
	)
	offered = {
		(member["name"], function)
		for household in get_households(phone, church)["households"]
		for member in household["members"]
		for function in member["functions"]
	}
	if not chosen or not chosen <= offered:
		frappe.throw(
			_("Check-in is not open for these people here. Ask at the welcome desk."), frappe.PermissionError
		)

	return print_new_check_ins(*add_household_check_ins(dict(chosen)), church)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REQUESTS_PER_HOUR, seconds=60 * 60)
def check_in_code(payload: str) -> dict:
	"""Check in the people of a scanned pre check-in code, at an open self check-in Function of this church."""
	from churchit.church_ministries.pre_check_in import read_payload, redeem  # it imports this module

	frappe.only_for(KIOSK_ROLE)
	church = get_church()
	function, persons = read_payload(payload)
	if function not in {row.name for row in get_open_functions(church)}:
		frappe.throw(
			_("Check-in is not open for these people here. Ask at the welcome desk."), frappe.PermissionError
		)
	return print_new_check_ins(*redeem(function, persons), church)


def print_new_check_ins(names: list[str], new: list[str], church: str | None) -> dict:
	"""The kiosk's answer for check-ins *names*: the tags of the *new* ones, through *church*'s printer."""
	if not new:
		return {"count": len(names), "print": None}

	docs = [frappe.get_doc("Function Check-In", name) for name in new]
	has_earlier_code = hide_earlier_codes(docs)
	# A network printer can take seconds, so the check-in locks must not wait for it.
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	settings = frappe.get_single("Check-In Settings").for_church(church)
	return {
		"count": len(names),
		"print": settings.print_name_tags(docs),
		"has_earlier_code": has_earlier_code,
	}


def get_church() -> str | None:
	"""The kiosk's one church. With several or none, a request could name the church it reads."""
	if not is_multi_church():
		return root_church()
	churches = allowed_churches()
	if len(churches or ()) != 1:
		frappe.throw(
			_("This kiosk needs exactly one church. Ask an administrator to set it up."),
			frappe.PermissionError,
		)
	return churches[0]


def hide_earlier_codes(check_ins: list) -> bool:
	"""Clear, in memory only, each code of *check_ins* that an earlier check-in holds. True when one did.

	A household's new check-ins get its code, and the tags must not hand it to whoever typed the phone.
	"""
	codes = {doc.security_code for doc in check_ins if doc.security_code}
	if not codes:
		return False

	# church-scope: codes are unique across the site for the day; get_security_code locked these rows
	earlier = set(
		frappe.db.get_values(
			"Function Check-In",
			{
				"security_code": ("in", list(codes)),
				"name": ("not in", [doc.name for doc in check_ins]),
				"creation": (">=", getdate(check_ins[0].creation)),
			},
			"security_code",
			for_update=True,
			pluck=True,
		)
	)
	for doc in check_ins:
		if doc.security_code in earlier:
			doc.security_code = None
	return bool(earlier)


def add_household_check_ins(choices: dict[str, str]) -> tuple[list[str], list[str]]:
	"""Check in each person of *choices* to their function: (every check-in, the new ones)."""
	persons_by_function = {}
	for person, function in choices.items():
		persons_by_function.setdefault(function, []).append(person)
	functions = sorted(persons_by_function)
	# Every Function row before the code lock add_check_ins takes, in one order, so two kiosks cannot deadlock.
	for function in functions:
		frappe.db.get_value("Function", function, "name", for_update=True)
	# The code lock before the check-in rows, the station's order (add_check_ins), so the two cannot deadlock.
	frappe.db.get_single_value("Check-In Settings", "security_codes", for_update=True)

	# church-scope: the check-ins of the people and Functions this kiosk was offered.
	# Locking, after the Function locks: a plain read answers from the request's older snapshot.
	present = frappe.db.get_values(
		"Function Check-In",
		{"function": ("in", functions), "person": ("in", list(choices))},
		"name",
		for_update=True,
		pluck=True,
	)
	names = [
		name for function in functions for name in add_check_ins(function, persons_by_function[function])
	]
	return names, [name for name in names if name not in present]


def get_households(phone: str, church: str) -> dict:
	"""*phone*'s households, each member with the open Functions of *church* they may check in to.

	Only a whole number matches a Person's or a Family's phone. The people pass the station's rule:
	any church's, unless the directory is private and no open Function is shared. A member who may
	check in to nothing is left out.
	"""
	functions = get_open_functions(church)
	result = {
		"functions": [
			{"name": row.name, "function_name": row.function_name, "start_time": row.start_time}
			for row in functions
		],
		"households": [],
	}
	digits = phone_digits(phone)
	if not functions or len(digits) < MIN_PHONE_DIGITS:
		return result

	private = is_people_directory_private()
	scope = church_filters(church) if private and not any(row.is_shared for row in functions) else {}
	groups = group_by_family(find_by_phone(digits, scope), scope)
	own = get_own_people(groups, church) if private else None

	for group in groups:
		members = [
			{
				"name": member.name,
				"full_name": member.full_name,
				"photo": member.photo if is_public(member.photo) else None,
				"grade": member.grade,
				"functions": get_offered_functions(member.name, functions, own),
			}
			for member in group["members"]
		]
		members = [member for member in members if member["functions"]]
		if members:
			result["households"].append({"family_name": group["family_name"], "members": members})
	return result


def get_own_people(groups: list[dict], church: str) -> set[str]:
	"""The people of *groups* who belong to *church*: with a private directory, only they join its unshared Functions."""
	names = [member.name for group in groups for member in group["members"]]
	if not names:
		return set()
	# church-scope: the people the kiosk found, narrowed to its own church
	return set(
		frappe.get_all("Person", filters={"name": ("in", names), **church_filters(church)}, pluck="name")
	)


def get_offered_functions(person: str, functions: list[dict], own: set[str] | None) -> list[str]:
	"""The *functions* *person* may check in to: within its bounds, and shared or theirs when *own* is given."""
	return [
		row.name
		for row in functions
		if (own is None or row.is_shared or person in own) and not get_bound_problem(row.name, person)
	]


def get_open_functions(church: str) -> list[dict]:
	"""Today's Functions of *church* whose type allows self check-in while their check-in is open."""
	types = frappe.get_all("Function Type", filters={"allow_self_check_in": 1}, pluck="name")
	if not types:
		return []
	functions = frappe.get_all(
		"Function",
		filters=church_filters(church, start_date=today(), type=("in", types), auto_repeat=0),
		fields=["name", "function_name", "start_time", "is_shared"],
		order_by="start_time asc, function_name asc",
	)
	return [row for row in functions if is_check_in_open(row.name)]


def find_by_phone(digits: str, scope: dict) -> list[str]:
	"""The people whose own or whose family's phone is exactly *digits*."""
	# church-scope: one whole phone number; group_by_family applies *scope* to everyone found
	phones = frappe.get_all(
		"Phone Number",
		filters={"digits": digits, "parenttype": ("in", ["Person", "Family"])},
		fields=["parent", "parenttype"],
	)
	persons = [row.parent for row in phones if row.parenttype == "Person"]
	families = [row.parent for row in phones if row.parenttype == "Family"]
	if families:
		# church-scope: *scope* is the station's rule for this kiosk
		persons += frappe.get_all("Person", filters={"family": ("in", families), **scope}, pluck="name")
	return persons
