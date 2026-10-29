# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Giving: the dates of a person's first and last gift, and whether their giving has lapsed.

A gift is a Donation row on a submitted Collection, as a giving statement counts it. A paid Online Donation records
one, dated when it was paid, so the Online Donation itself is not read.
"""

import frappe
from frappe.query_builder.functions import Max, Min
from frappe.utils import add_days, getdate, nowdate

from churchit.church_people.summaries import same_church

FIELDS = ("first_gift_on", "last_gift_on", "is_lapsed_giver")
# A lapsed giver gave within the last year, but not within the last 90 days.
LAPSED_AFTER_DAYS = 90
LAPSED_WITHIN_DAYS = 365


def collection_givers(doc) -> set[str]:
	before = doc.get_doc_before_save()
	rows = [*(doc.get("donations") or []), *(before.get("donations") or [] if before else [])]
	return {row.person for row in rows}


SOURCES = {"Collection": collection_givers}


def compute(people: list[str]) -> dict[str, dict]:
	"""Each person's first and last gift up to today, and whether that last gift makes them a lapsed giver."""
	# church-scope: stored on the person; same_church keeps it to their own church's collections, never shared
	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	Person = frappe.qb.DocType("Person")
	today = getdate(nowdate())
	tomorrow = add_days(today, 1)
	rows = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on((Collection.name == Donation.parent) & (Donation.parenttype == "Collection"))
		.join(Person)
		.on(Person.name == Donation.person)
		.select(Donation.person, Min(Collection.date).as_("first"), Max(Collection.date).as_("last"))
		.where(Donation.person.isin(people) & (Collection.docstatus == 1))
		.where(Collection.date < tomorrow)
		.where(same_church(Collection, Person))
		.groupby(Donation.person)
		.run(as_dict=True)
	)
	lapsed_from, lapsed_to = add_days(today, -LAPSED_WITHIN_DAYS), add_days(today, -LAPSED_AFTER_DAYS - 1)
	return {
		row.person: {
			"first_gift_on": getdate(row.first),
			"last_gift_on": getdate(row.last),
			"is_lapsed_giver": int(lapsed_from <= getdate(row.last) <= lapsed_to),
		}
		for row in rows
	}
