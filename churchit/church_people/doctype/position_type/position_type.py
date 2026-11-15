# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce

from churchit.church_scope import is_multi_church


class PositionType(Document):
	pass


@frappe.whitelist(methods=["POST"])
def assign_position_to_person(
	position_type: str,
	person: str,
	start_date: str | None = None,
	end_date: str | None = None,
	notes: str | None = None,
) -> str:
	"""Add *position_type* to the positions of *person*, unless another person of their church holds that single-person role. Changes data."""
	frappe.has_permission("Position Type", "read", doc=position_type, throw=True)
	frappe.has_permission("Person", "write", doc=person, throw=True)

	doc = frappe.get_doc("Person", person)
	doc.append(
		"positions",
		{
			"position": position_type,
			"start_date": start_date or None,
			"end_date": end_date or None,
			"notes": notes or "",
		},
	)
	doc.save()
	return doc.name


def refuse_second_holders(person: Document) -> None:
	"""Person validate: refuse a single-person role that this save gives *person* while another person of
	their church holds it with no end date.

	Only the positions that this save starts are checked, so people who shared a role before the rule
	existed can still be saved.
	"""
	for position_type in get_started_single_person_roles(person):
		if holder := get_holder_in_church(position_type, person.name, person.church):
			holder_name = frappe.db.get_value("Person", holder, "full_name") or holder
			frappe.throw(
				_("{0} is a single-person role currently held by {1}.").format(position_type, holder_name)
			)


def get_started_single_person_roles(person: Document) -> list[str]:
	"""The single-person roles of the open positions that this save of *person* starts: a new row, a row
	whose position changed or whose end date was cleared, and every open row when the person changes church."""
	before = person.get_doc_before_save()
	earlier = {row.name: row for row in before.positions} if before else {}
	has_moved = bool(before) and before.church != person.church
	started = set()
	for row in person.positions:
		old = earlier.get(row.name)
		if not row.end_date and (has_moved or not old or old.position != row.position or old.end_date):
			started.add(row.position)
	if not started:
		return []
	return frappe.get_all(
		"Position Type", filters={"name": ("in", list(started)), "is_single_person_role": 1}, pluck="name"
	)


def get_holder_in_church(position_type: str, person: str, church: str | None) -> str | None:
	"""Another person of *church* than *person* who holds *position_type* with no end date, or None.

	Each branch can have its own holder of a single-person role. A site with one church is one church.
	"""
	# church-scope: limited to *church*, the church of the person being given the role
	position = frappe.qb.DocType("Position")
	people = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(position)
		.join(people)
		.on(people.name == position.parent)
		.select(position.parent)
		.where(position.parenttype == "Person")
		.where(position.position == position_type)
		.where(position.end_date.isnull())
		.where(position.parent != person)
		.limit(1)
	)
	if is_multi_church():
		query = query.where(Coalesce(people.church, "") == (church or ""))
	holders = query.run(pluck=True)
	return holders[0] if holders else None
