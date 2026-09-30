# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Server side of the Check-In Station page."""

import re

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from churchit.church_ministries.doctype.function_check_in.function_check_in import (
	check_in_persons,
	is_shared_function,
	print_name_tags,
)
from churchit.church_scope import (
	church_query_filters,
	default_church,
	is_people_directory_private,
	scoped,
)

RESULT_LIMIT = 12


@frappe.whitelist()
def get_station_context():
	"""Functions around today plus the printing settings the station shows."""
	frappe.has_permission("Function Check-In", "create", throw=True)
	settings = frappe.get_single("Check-In Settings").for_church(default_church())
	today = getdate()
	functions = frappe.get_all(
		"Function",
		filters={
			"start_date": ["between", [add_days(today, -1), add_days(today, 7)]],
			"auto_repeat": 0,
			**church_query_filters({}),
		},
		fields=["name", "function_name", "start_date", "start_time"],
		order_by="start_date asc, start_time asc",
	)
	return {
		"today": str(today),
		"functions": functions,
		"name_tag_printing": settings.name_tag_printing,
		"printer_name": settings.printer_name,
		"security_codes": settings.security_codes,
	}


@frappe.whitelist()
def search_people(query: str | None, function: str | None = None):
	"""People matching *query* by name, family name or phone digits, grouped by family."""
	frappe.has_permission("Person", throw=True)
	query = (query or "").strip()
	if len(query) < 2:
		return []
	scope = get_people_scope(function)
	digits = re.sub(r"\D", "", query)
	if len(digits) >= 4 and not re.search(r"[a-zA-Z]", query):
		matched = find_by_phone(digits, scope)
	else:
		matched = find_by_name(query.split(), scope)
	return group_by_family(matched, scope)


def get_people_scope(function):
	"""Person filters for the station: every church unless people are private, or at a shared function.

	A station has to find whoever walks in, whichever church they belong to. With
	a private directory that still holds at a joint service, so the results carry
	names, ages and photos only, never contact details.
	"""
	if function:
		frappe.has_permission("Function", doc=function, throw=True)
	if not is_people_directory_private() or (function and is_shared_function(function)):
		return {}
	return church_query_filters({})


def find_by_name(words, scope):
	person = frappe.qb.DocType("Person")
	family = frappe.qb.DocType("Family")
	query = (
		frappe.qb.from_(person)
		.left_join(family)
		.on(person.family == family.name)
		.select(person.name)
		.orderby(person.last_name)
		.orderby(person.first_name)
		.limit(RESULT_LIMIT)
	)
	for word in words:
		like = f"%{word}%"
		query = query.where(person.full_name.like(like) | family.family_name.like(like))
	if scope:
		query = scoped(query, person, {})
	return query.run(pluck=True)


def find_by_phone(digits, scope):
	"""Match phone numbers however they are formatted by allowing anything between digits."""
	pattern = "%" + "%".join(digits) + "%"
	phones = frappe.get_all(
		"Phone Number",
		filters={"phone_number": ["like", pattern], "parenttype": ["in", ["Person", "Family"]]},
		fields=["parent", "parenttype"],
		limit=RESULT_LIMIT,
	)
	persons = [row.parent for row in phones if row.parenttype == "Person"]
	families = [row.parent for row in phones if row.parenttype == "Family"]
	if families:
		# church-scope: *scope* is get_people_scope's answer for this station
		persons += frappe.get_all("Person", filters={"family": ["in", families], **scope}, pluck="name")
	return persons


def group_by_family(matched, scope):
	"""Expand matches to whole families so siblings can be checked in together."""
	if not matched:
		return []
	# church-scope: *scope* is get_people_scope's answer for this station
	families = frappe.get_all(
		"Person",
		filters={"name": ["in", matched], "family": ["is", "set"], **scope},
		pluck="family",
		distinct=True,
	)
	or_filters = [["name", "in", matched]]
	if families:
		or_filters.append(["family", "in", families])
	# The church filter is the backstop: every person the station lists passes it,
	# whichever of the searches above found them.
	people = frappe.get_all(
		"Person",
		filters=scope,
		or_filters=or_filters,
		fields=[
			"name",
			"first_name",
			"last_name",
			"full_name",
			"age",
			"photo",
			"family",
			"is_head_of_household",
		],
		order_by="is_head_of_household desc, age desc, first_name asc",
	)
	family_names = dict(
		frappe.get_all(
			"Family", filters={"name": ["in", families]}, fields=["name", "family_name"], as_list=True
		)
	)
	groups = {}
	for row in people:
		row.matched = row.name in matched
		group = groups.setdefault(
			row.family or row.name,
			{"family": row.family, "family_name": family_names.get(row.family), "members": []},
		)
		group["members"].append(row)
	return sorted(groups.values(), key=lambda group: group["members"][0].full_name)


@frappe.whitelist()
def get_check_ins(function: str):
	"""Who is checked in to *function*, newest first, whichever church they belong to."""
	frappe.has_permission("Function Check-In", throw=True)
	frappe.has_permission("Function", doc=function, throw=True)
	# church-scope: keyed to one function the caller may read; its roster spans churches on purpose
	check_in = frappe.qb.DocType("Function Check-In")
	person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(check_in)
		.join(person)
		.on(check_in.person == person.name)
		.select(check_in.name, check_in.person, check_in.security_code, check_in.creation, person.full_name)
		.where(check_in.function == function)
		.orderby(check_in.creation, order=frappe.qb.desc)
	)
	return query.run(as_dict=True)


@frappe.whitelist()
def check_in(function: str, persons: str | list[str], print_tags: bool = False):
	"""Check people in and, when asked, hand their name tags to the printer path."""
	names = check_in_persons(function, persons)
	result = {"check_ins": names}
	if cint(print_tags):
		result["print"] = print_name_tags(check_ins=names)
	return result


@frappe.whitelist()
def undo_check_in(name: str):
	frappe.delete_doc("Function Check-In", name)


@frappe.whitelist()
def add_visitor(
	first_name: str | None, last_name: str | None = None, phone: str | None = None, family: str | None = None
):
	"""Create a Person on the spot so a first-time visitor can be checked in.

	Checking people in is the right that counts: a check-in volunteer holds no
	Person create, which would otherwise ask them to read every Person lookup too.
	"""
	frappe.has_permission("Function Check-In", "create", throw=True)
	if not (first_name or "").strip():
		frappe.throw(_("First name is required."))
	person = frappe.get_doc(
		{
			"doctype": "Person",
			"first_name": first_name.strip(),
			"last_name": (last_name or "").strip(),
			"family": family,
		}
	)
	if phone:
		person.append("phones", {"phone_number": phone.strip(), "is_primary": 1})
	person.insert(ignore_permissions=True)
	return {"name": person.name, "full_name": person.full_name, "family": person.family}
