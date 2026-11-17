# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""One person on one row of a membership table."""

from collections import Counter

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html


def refuse_repeated_people(doc: Document, table: str, fieldname: str) -> None:
	"""Refuse a person who this save puts on a second row of *table*.

	A repeat that an earlier save stored is left alone, so that its record can still be saved.
	"""
	before = doc.get_doc_before_save()
	counts_before = Counter(row.get(fieldname) for row in before.get(table)) if before else Counter()
	counts = Counter(row.get(fieldname) for row in doc.get(table))
	first_rows = {}
	for row in doc.get(table):
		person = row.get(fieldname)
		first_rows.setdefault(person, row.idx)
		if person and first_rows[person] != row.idx and counts[person] > counts_before[person]:
			# get_list, so a person of a private directory the user may not read shows by ID only
			names = frappe.get_list("Person", filters={"name": person}, pluck="full_name")
			name = names[0] if names else person
			frappe.throw(
				_("Row {0}: {1} is already in row {2}.").format(
					row.idx, frappe.bold(escape_html(name)), first_rows[person]
				)
			)
