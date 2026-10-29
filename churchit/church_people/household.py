# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who is in a household and what part they play in it, from the family's roster.

A household role is Adult (a responsible adult of the household), Other Adult (lives there without
authority over the children, such as a grandparent or a lodger) or Child (a dependent).
"""

import frappe

from churchit.church_people.family_relations import ROLE_OF_TYPE
from churchit.church_people.membership import living_people_filter

ADULT = "Adult"
OTHER_ADULT = "Other Adult"
CHILD = "Child"
DESCENDANT_ROLES = ("child", "step_child", "grandchild")


def role_of(person: str) -> str | None:
	"""*person*'s household role on their family's roster, or None."""
	family = frappe.db.get_value("Person", person, "family")
	if not family:
		return None
	return (
		frappe.db.get_value(
			"Family Members", {"parenttype": "Family", "parent": family, "member": person}, "household_role"
		)
		or None
	)


def get_household_role(
	is_primary_contact: bool, relationship: str | None, age: int | None, adult_age: int
) -> str | None:
	"""The household role a member's relationship to the primary contact and age decide, or None.

	The primary contact and their spouse are Adults. A child, step-child or grandchild under *adult_age* is a
	Child, and anyone else at or over it is an Other Adult.
	"""
	kinship = ROLE_OF_TYPE.get(relationship)
	if is_primary_contact or kinship == "spouse":
		return ADULT
	if age is None:
		return None
	if age >= adult_age:
		return OTHER_ADULT
	return CHILD if kinship in DESCENDANT_ROLES else None


def get_ages(people: list[str]) -> dict[str, int]:
	"""{person: age} for those of *people* whose age is known: born on a known date, and died on one if they died.

	The column stores an unknown age as 0.
	"""
	if not people:
		return {}
	# church-scope: only the people named, by name
	born = frappe.get_all(
		"Person",
		filters={"name": ("in", people), "birth_date": ("is", "set")},
		fields=["name", "age", "is_deceased", "deceased_date"],
	)
	return {person.name: person.age for person in born if not person.is_deceased or person.deceased_date}


def members(family: str, roles: list[str] | None = None) -> list[str]:
	"""The living people on *family*'s roster, primary contact first, then in roster order.

	With *roles*, only the members holding one of those household roles.
	"""
	Member = frappe.qb.DocType("Family Members")
	Person = frappe.qb.DocType("Person")
	# church-scope: one family's own roster, by name
	query = (
		frappe.qb.from_(Member)
		.join(Person)
		.on(Person.name == Member.member)
		.select(Member.member)
		.where((Member.parenttype == "Family") & (Member.parent == family) & living_people_filter(Person))
		.orderby(Member.idx)
	)
	if roles is not None:
		query = query.where(Member.household_role.isin(roles))
	contact = frappe.db.get_value("Family", family, "primary_contact")
	return sorted(query.run(pluck=True), key=lambda member: member != contact)


def can_edit(user: str, person: str) -> bool:
	"""True when *user* may edit *person*: their own Person, or a Child of a family they are an Adult of."""
	own = user and frappe.db.get_value("Person", {"user": user}, "name")
	if not own:
		return False
	return own == person or person in get_editable_children(user)


def get_editable_children(user: str) -> list[str]:
	"""The living Children of the family *user*'s Person is an Adult of; none when they are not an Adult.

	A Child stays one on the roster until someone changes the role, so a Child known to be at or over People
	Settings' adult age is left out. A Child of unknown age stays in.
	"""
	own = user and frappe.db.get_value("Person", {"user": user}, ["name", "family"], as_dict=True)
	if not own or not own.family or role_of(own.name) != ADULT:
		return []
	children = members(own.family, [CHILD])
	ages = get_ages(children)
	adult_age = frappe.db.get_single_value("People Settings", "adult_age")
	return [child for child in children if child not in ages or ages[child] < adult_age]


def salutation(family: str) -> str:
	"""How to address *family* on a letter or label, e.g. "John & Jane Smith", from its living Adults.

	A nickname stands in for the first name. A shared last name is written once, and different ones give
	"John Smith & Jane Doe". A family with no Adult known is addressed by its name.
	"""
	if not family:
		return ""
	adults = members(family, [ADULT])
	if not adults:
		return frappe.db.get_value("Family", family, "family_name") or ""
	# church-scope: one family's own Adults, by name
	names = {
		person.name: person
		for person in frappe.get_all(
			"Person", filters={"name": ("in", adults)}, fields=["name", "first_name", "nickname", "last_name"]
		)
	}
	people = [names[adult] for adult in adults]
	last_names = {person.last_name or "" for person in people}
	if len(last_names) == 1:
		first_names = [person.nickname or person.first_name for person in people]
		return f"{join_names(first_names)} {last_names.pop()}".strip()
	return join_names(
		[f"{person.nickname or person.first_name} {person.last_name or ''}".strip() for person in people]
	)


def join_names(names: list[str]) -> str:
	"""*names* joined as A, as A & B, or as A, B & C."""
	return " & ".join(filter(None, [", ".join(names[:-1]), names[-1]]))
