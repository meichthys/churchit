# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Forget the Ministry Team Assignments, Ministry Team Blocks and Possible Duplicates of people anonymized
before these became records about the person: their change history, which can hold the person's name, their
comments and attachments, and the address and text of their messages."""

import frappe

from churchit.church_people.privacy import ANONYMIZED, forget

RECORDS_NOW_ABOUT_THE_PERSON = (
	("Ministry Team Assignment", "person"),
	("Ministry Team Block", "person"),
	("Possible Duplicate", "person"),
	("Possible Duplicate", "other_person"),
)


def execute():
	people = frappe.get_all("Person", filters={"first_name": ANONYMIZED}, pluck="name")
	if not people:
		return
	for doctype, fieldname in RECORDS_NOW_ABOUT_THE_PERSON:
		for name in frappe.get_all(doctype, filters={fieldname: ("in", people)}, pluck="name"):
			forget(doctype, name)
