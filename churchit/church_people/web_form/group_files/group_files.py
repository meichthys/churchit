# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe

from churchit.church_people.group_leaders import get_led_groups
from churchit.church_scope import session_person


def get_context(context):
	"""Offer a leader the groups they lead on a new file, and show the group's name on a saved one."""
	group_field = next(field for field in context.web_form_doc.web_form_fields if field.fieldname == "group")
	if context.get("reference_doc"):
		# The form is view only once saved, so the field shows the name and not the Group's ID.
		group_field.update(fieldname="group_name", fieldtype="Data", options="")
		return

	person = session_person()
	groups = get_led_groups(person) if person else []
	# Only a leader may add a file, so the list offers New only to one.
	context.allow_multiple = bool(groups)
	# church-scope: only groups the member leads, whatever their church
	options = frappe.get_all(
		"Group", filters={"name": ("in", groups or [""])}, fields=["name as value", "group_name as label"]
	)
	group_field.options = json.dumps(options, default=str)
