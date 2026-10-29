# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Pre check-in: a member picks who comes to one of today's Functions and gets a QR code to scan on arrival.

The code holds `get_signed_params` of the Function, the people and an expiry, so the station and the kiosk
check it with the site secret alone and keep no record of it. A second scan checks in nobody new.
"""

import hmac
from datetime import datetime
from urllib.parse import parse_qsl

import frappe
from frappe import _
from frappe.utils import cint, escape_html, format_datetime, format_time, now_datetime
from frappe.utils.print_format_generator import get_qr_code
from frappe.utils.verified_command import get_signed_params

from churchit.church_ministries.check_in_limits import (
	get_bound_problem,
	get_capacity_warning,
	is_check_in_open,
)
from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_ministries.doctype.function_check_in.function_check_in import print_name_tags
from churchit.church_ministries.kiosk import add_household_check_ins, get_open_functions
from churchit.church_scope import is_multi_church, session_church

SIGNATURE = "&_signature="
# The Function, the people (comma separated) and the expiry.
PAYLOAD_KEYS = ("f", "p", "u")
EXPIRY_FORMAT = "%Y%m%d%H%M%S"


def get_functions() -> list[dict]:
	"""Today's Functions of the signed-in member's church whose type allows self check-in, while open."""
	church = session_church()
	if is_multi_church() and not church:
		return []
	return get_open_functions(church)


@frappe.whitelist(methods=["POST"])
def get_pre_check_in_code(function: str, persons: str | list[str]) -> dict:
	"""A QR code that checks *persons* in to *function* when scanned, until the Function ends."""
	persons = frappe.parse_json(persons)
	if not persons or not isinstance(persons, list) or not all(isinstance(person, str) for person in persons):
		frappe.throw(_("Choose who to check in."))
	for person in persons:
		frappe.has_permission("Person", "write", doc=person, throw=True)
	if function not in {row.name for row in get_functions()}:
		frappe.throw(_("Check-in to this function is not open now."), frappe.PermissionError)

	problems = [
		f"{escape_html(frappe.db.get_value('Person', person, 'full_name'))}: {problem}"
		for person in persons
		if (problem := get_bound_problem(function, person))
	]
	if problems:
		frappe.throw("<br>".join(problems), title=_("Outside the age or grade limits"))

	fields = ["start_date", "end_date", "start_time", "end_time", "all_day"]
	ends = get_time_window(frappe.db.get_value("Function", function, fields, as_dict=True))[1]
	values = (function, ",".join(dict.fromkeys(persons)), ends.strftime(EXPIRY_FORMAT))
	payload = get_signed_params(dict(zip(PAYLOAD_KEYS, values, strict=True)))
	valid_until = format_time(ends) if ends.date() == now_datetime().date() else format_datetime(ends)
	return {"qr_code": get_qr_code(payload), "valid_until": valid_until}


def read_payload(payload: str) -> tuple[str, list[str]]:
	"""The Function and the people of a scanned *payload*. Refuses a changed or expired one."""
	params = payload.rpartition(SIGNATURE)[0]
	pairs = parse_qsl(params)
	# Other signed links (unsubscribe, consent) share the secret, so only these keys in this order count.
	if [key for key, _value in pairs] != list(PAYLOAD_KEYS) or not hmac.compare_digest(
		get_signed_params(params).encode(), payload.encode()
	):
		frappe.throw(_("This check-in code is not valid. Ask at the welcome desk."), frappe.PermissionError)

	values = dict(pairs)
	if now_datetime() > datetime.strptime(values["u"], EXPIRY_FORMAT):
		frappe.throw(
			_("This check-in code has expired. Make a new one, or ask at the welcome desk."),
			frappe.PermissionError,
		)
	return values["f"], values["p"].split(",")


def redeem(function: str, persons: list[str]) -> tuple[list[str], list[str]]:
	"""Check *persons* in to *function* while its check-in is open: (every check-in, the new ones)."""
	if not is_check_in_open(function):
		frappe.throw(_("Check-in to this function is not open now."), frappe.PermissionError)
	return add_household_check_ins(dict.fromkeys(persons, function))


@frappe.whitelist(methods=["POST"])
def check_in(payload: str, print_tags: bool = False) -> dict:
	"""Check in the people of a pre check-in code scanned at the station, and print the new check-ins' tags."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	function, persons = read_payload(payload)
	frappe.has_permission("Function", doc=function, throw=True)

	names, new = redeem(function, persons)
	result = {
		"check_ins": names,
		"new": new,
		"function_name": frappe.db.get_value("Function", function, "function_name"),
	}
	if warning := get_capacity_warning(function):
		result["capacity_warning"] = warning
	if new and cint(print_tags):
		# A network printer can take seconds, so the check-in locks must not wait for it.
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		result["print"] = print_name_tags(check_ins=new)
	return result
