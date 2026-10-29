# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The duplicate queue: the weekly scan that fills it with Possible Duplicates, and its upkeep."""

import frappe

from churchit.church_people.matching import (
	POSSIBLE_DUPLICATE,
	find_matches,
	get_pairs,
	get_people,
	record_possible_duplicates,
)
from churchit.church_scope import is_multi_church


def scan() -> None:
	"""Weekly: pair the living people of each church whom the matcher finds alike.

	People in one family are never paired, and a pair already recorded, whatever its status, is not opened again.
	"""
	churches = frappe.get_all("Church", pluck="name") if is_multi_church() else [None]
	for church in churches:
		scan_church(church)


def scan_church(church: str | None) -> list[str]:
	"""Open a Possible Duplicate for each new pair among the living people of *church*, and return their names."""
	people = get_people(church)
	families = {person.name: person.family for person in people}
	created = []
	for person in people:
		matches = [
			match
			for match in find_matches(person, church=church, exclude=person.name)
			if not (person.family and families.get(match.person) == person.family)
		]
		created += record_possible_duplicates(person.name, matches)
	return created


def drop_pairs(person, method=None) -> None:
	"""On Person on_trash: a deleted person's pairs go with them, so the pairs do not block the delete.

	Nothing is left in Deleted Documents, where a pair would keep both people's names.
	"""
	for pair in get_pairs(person.name):
		frappe.delete_doc(
			POSSIBLE_DUPLICATE, pair.name, ignore_permissions=True, force=True, delete_permanently=True
		)
