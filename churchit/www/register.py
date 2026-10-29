# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils import (
	cstr,
	flt,
	fmt_money,
	format_date,
	format_time,
	getdate,
	today,
	validate_email_address,
)
from frappe.utils.verified_command import verify_request

from churchit.church_finances.payments import get_payment_url
from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CONFIRMED,
	get_function_calendar,
	is_in_sign_up_window,
)
from churchit.church_ministries.sign_up_amounts import get_function_rows, is_freely_given
from churchit.church_people.household import members
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import church_filters, session_person
from churchit.ics import calendar_response
from churchit.questions import get_fields

no_cache = 1
# One registration brings at most this many others, so one request cannot add rows without end.
MAX_ATTENDEES = 20
CALENDAR_METHOD = "/api/method/churchit.www.register.get_event_calendar"


def get_context(context):
	"""The public Register page: the selected church's upcoming functions that take guest sign-ups."""
	context.no_cache = 1
	context.title = _("Register")
	context.functions = get_open_functions()
	for function in context.functions:
		function.when = format_date(function.start_date)
		if function.start_time and not function.all_day:
			function.when += ", " + format_time(function.start_time, TIME_FORMAT)
	chosen = frappe.form_dict.get("function")
	context.function = next((function for function in context.functions if function.name == chosen), None)
	context.is_unknown_function = bool(chosen and not context.function)
	# A link-only function opens from its link but is not listed.
	context.functions = [function for function in context.functions if not function.is_link_only]


def get_open_functions(**filters) -> list[frappe._dict]:
	"""The selected church's published functions from today on that take guest sign-ups now."""
	functions = frappe.get_all(
		"Function",
		filters=church_filters(
			selected_church_name(),
			publish=1,
			allow_sign_ups=1,
			allow_guest_sign_ups=1,
			start_date=(">=", today()),
			**filters,
		),
		fields=[
			"name",
			"function_name",
			"start_date",
			"start_time",
			"all_day",
			"description",
			"sign_ups_open_on",
			"sign_ups_close_on",
			"is_link_only",
		],
		order_by="start_date, start_time",
	)
	return [function for function in functions if is_in_sign_up_window(function)]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def sign_up(
	function: str,
	registrant_name: str,
	email: str,
	phone: str | None = None,
	notes: str | None = None,
	discount_code: str | None = None,
	website: str | None = None,
	**form,
) -> dict:
	"""Register for an open function from /register. *form* holds the inputs the page's includes add.

	The status, amounts and person are worked out on the server. A signed-in member signs up as their
	own Person, and a guest's person is linked after the commit.
	"""
	if not get_open_functions(name=function):
		frappe.throw(_("This function is not open for registration."), frappe.PermissionError)
	# Only a bot fills in the hidden website field. It is told the same as a person.
	if website:
		return {"status": CONFIRMED}
	validate_email_address(email, throw=True)

	function_doc = frappe.get_doc("Function", function)
	registrant_name = registrant_name.strip()
	attendees = get_attendee_rows(function_doc, {**form, "registrant_name": registrant_name})
	doc = frappe.get_doc(
		{
			"doctype": "Function Sign-Up",
			"function": function,
			"registrant_name": registrant_name,
			"email": email.strip(),
			"phone": phone,
			"notes": notes,
			"discount_code": discount_code,
			"attendees": attendees,
			"answers": get_answer_rows(function_doc, form, attendees),
		}
		# Keep the attendee row names that the answers name: insert renames every child row otherwise.
	).insert(ignore_permissions=True, set_child_names=False)
	return {"status": doc.status, **get_calendar_link(doc), **get_payment_link(doc)}


def get_attendee_rows(function_doc: Document, form: dict) -> list[dict]:
	"""Attendee rows beyond the registrant's own, which `set_attendees` adds, from the `attendees` input: a JSON
	list of the household members a signed-in member ticked (`person`) and the names anyone typed
	(`attendee_name`), each with its `selection`.

	On a function with selections the registrant's own row comes first, with the `selection` they chose. The
	household is worked out again from the session, and a Person outside it is refused.
	"""
	rows = [get_registrant_row(form)] if function_doc.selections else []
	household = get_household()
	for attendee in read_attendees(form.get("attendees")):
		if row := get_attendee_row(attendee, household):
			rows.append(row)
	return rows


def get_registrant_row(form: dict) -> dict:
	"""The registrant's own attendee row with their selection: a member's Person, or a guest's name."""
	own = session_person() if is_portal_member() else None
	name = None if own else form.get("registrant_name")
	return {"person": own, "attendee_name": name, "selection": form.get("selection") or None}


def get_attendee_row(attendee: dict, household: dict[str, str]) -> dict | None:
	"""The row of a ticked household member (`person`) or of a typed name; None for a blank one."""
	person, name = cstr(attendee.get("person")), cstr(attendee.get("attendee_name")).strip()
	if person and person not in household:
		frappe.throw(_("You can add only the people of your own household."), frappe.PermissionError)
	if not (person or name):
		return None
	selection = cstr(attendee.get("selection")) or None
	if person:
		return {"person": person, "attendee_name": None, "selection": selection}
	return {"person": None, "attendee_name": name, "selection": selection}


def read_attendees(value: str | None) -> list[dict]:
	"""The `attendees` input: a JSON list of at most MAX_ATTENDEES objects."""
	try:
		attendees = frappe.parse_json(value or "[]")
	except ValueError:
		attendees = None
	if not isinstance(attendees, list) or not all(isinstance(row, dict) for row in attendees):
		frappe.throw(_("The attendees could not be read."))
	if len(attendees) > MAX_ATTENDEES:
		frappe.throw(_("One registration can bring at most {0} other people.").format(MAX_ATTENDEES))
	return attendees


def get_household() -> dict[str, str]:
	"""{person: full name} of the other living people of the signed-in member's household; none for a guest."""
	own = session_person() if is_portal_member() else None
	family = own and frappe.db.get_value("Person", own, "family")
	people = [person for person in members(family) if person != own] if family else []
	if not people:
		return {}
	# church-scope: the member's own household, from their family's roster
	full_names = dict(
		frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", "full_name"], as_list=True)
	)
	return {person: full_names[person] for person in people}


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_attendee_choices(function: str) -> dict:
	"""What /register offers for the attendees of an open function: its selections, and to a signed-in member
	the other people of their household. The page fetches it, so its HTML holds no household name.
	"""
	if not get_open_functions(name=function):
		frappe.throw(_("This function is not open for registration."), frappe.PermissionError)
	# church-scope: the selections of the open function checked above
	selections = frappe.get_all(
		"Function Sign-Up Selection",
		filters={"parent": function, "parenttype": "Function"},
		fields=["selection", "price", "description"],
		order_by="idx",
	)
	currency = frappe.get_cached_doc("Giving Settings").currency or "USD"  # the currency `pay` charges
	for row in selections:
		row.price = fmt_money(row.price, currency=currency) if flt(row.price) else ""
	household = [{"person": person, "full_name": name} for person, name in get_household().items()]
	discounts = get_function_rows(
		"Function Sign-Up Discount", function, ["kind", "amount", "percent", "valid_until"]
	)
	freely_given = is_freely_given(discounts, getdate(today()))
	return {"selections": selections, "household": household, "freely_given": freely_given}


def get_answer_rows(function_doc: Document, form: dict, attendees: list[dict]) -> list[dict]:
	"""Question Answer rows from the `answers` input: a JSON object of each attendee's answers by question.

	The key "" is the registrant, whose attendee row the save adds. Another key is an attendee row's person, or
	its name as typed. Each attendee row gets its name here, so that its answers can name it. The save checks
	the answers against the function's Question Set (`set_attendee_answers`).
	"""
	answers = frappe.parse_json(form.get("answers") or "{}")
	if not isinstance(answers, dict) or not all(isinstance(given, dict) for given in answers.values()):
		frappe.throw(_("The answers could not be read."))

	attendee_by_key = {"": ""}
	for row in attendees:
		row["name"] = frappe.generate_hash(length=10)
		attendee_by_key[row.get("person") or row.get("attendee_name")] = row["name"]
	if set(answers) - set(attendee_by_key):
		frappe.throw(_("Some answers are for someone who is not on this registration."))

	return [
		{"attendee": attendee_by_key[key], "question": question, "answer": answer}
		for key, given in answers.items()
		for question, answer in given.items()
	]


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_questions(function: str) -> list[dict]:
	"""The questions /register asks each attendee: the fields of the open function's Question Set."""
	if not get_open_functions(name=function):
		frappe.throw(_("This function is not open for registration."), frappe.PermissionError)
	question_set = frappe.db.get_value("Function", function, "question_set")
	return get_fields(question_set) if question_set else []


def get_calendar_link(sign_up: Document) -> dict:
	"""Keys for the success view's "Add to calendar" link (`calendar_url`), once the sign-up is Confirmed."""
	if sign_up.status != CONFIRMED:
		return {}
	query = {"function": sign_up.function}
	if church := selected_church_name():
		query["church"] = church
	return {"calendar_url": f"{CALENDAR_METHOD}?{urlencode(query)}"}


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_event_calendar(function: str):
	"""The calendar file of a function /register offers, for the "Add to calendar" link of its success view."""
	# Only what /register lists, so that nobody walks the sequential names through past and far-off functions.
	if not get_open_functions(name=function):
		raise frappe.DoesNotExistError(_("This function is not open for registration."))
	return calendar_response(get_function_calendar(function), "event.ics")


def get_payment_link(sign_up: Document) -> dict:
	"""Keys for the success view's "Pay now" link (`pay_url`), with the amount due and any discount."""
	pay_url = sign_up.pay_url
	if not pay_url:
		return {}

	currency = frappe.get_cached_doc("Giving Settings").currency or "USD"
	link = {"pay_url": pay_url, "amount_due": fmt_money(sign_up.amount_to_pay, currency=currency)}
	if flt(sign_up.discount) > 0:
		link["discount"] = fmt_money(sign_up.discount, currency=currency)
	return link


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=30, seconds=60 * 60)
def pay(sign_up: str, **signed_params) -> None:
	"""The signed Pay now link of /register and the payment email: on to the checkout of the amount due."""
	if not verify_request():
		return

	doc = frappe.get_doc("Function Sign-Up", sign_up)
	if not doc.is_payable:
		frappe.respond_as_web_page(
			_("Nothing to pay"),
			_("This registration has no payment due now. Please contact the church office."),
			indicator_color="orange",
		)
		return

	function_name = frappe.db.get_value("Function", doc.function, "function_name")
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = get_payment_url(
		doc,
		doc.amount_to_pay,
		frappe.get_cached_doc("Giving Settings").currency or "USD",
		doc.payment_church,
		function_name,
		_("Registration for {0}").format(function_name),
		payer_name=doc.registrant_name or None,
		payer_email=doc.email or None,
	)
