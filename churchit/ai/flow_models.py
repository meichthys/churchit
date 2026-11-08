# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A privacy label on each Flow Model: where a model sends church data and what its provider may do
with it. Flow owns providers and models; churchit only adds the label. A Frappe without Flow gets none.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import now_datetime

from churchit.ai.switch import has_flow

DEFAULT_LABEL = "Unknown"
PRIVACY_LABELS = (DEFAULT_LABEL, "May train", "No training", "Zero retention", "Local")
# A model with one of these labels may keep church data or train on it, or nobody has said.
UNSAFE_LABELS = (DEFAULT_LABEL, "May train")
LABEL_FIELD = "church_privacy_label"
BY_FIELD = "church_privacy_label_by"
ON_FIELD = "church_privacy_label_on"

PRIVACY_LABEL_FIELDS = {
	"Flow Model": [
		{
			"fieldname": LABEL_FIELD,
			"fieldtype": "Select",
			"label": "Privacy Label",
			"options": "\n".join(PRIVACY_LABELS),
			"default": DEFAULT_LABEL,
			"description": "Who sees what this model is sent. Set it from the provider's terms.",
			"insert_after": "extra_params",
			"no_copy": 1,
		},
		{
			"fieldname": BY_FIELD,
			"fieldtype": "Link",
			"options": "User",
			"label": "Label Set By",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": LABEL_FIELD,
		},
		{
			"fieldname": ON_FIELD,
			"fieldtype": "Datetime",
			"label": "Label Set On",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": BY_FIELD,
		},
	]
}


def add_privacy_label_field() -> None:
	"""after_install and after_migrate: add the label to Flow Model. It does nothing without Flow.

	Not a fixture: a Custom Field fixture for a doctype that Frappe 16 lacks breaks migrate. Safe to
	repeat, because Frappe leaves a field that already matches.
	"""
	if has_flow():
		create_custom_fields(PRIVACY_LABEL_FIELDS)


def stamp_privacy_label(doc, method=None) -> None:
	"""Flow Model validate: stamp who changed the label and when.

	A save that keeps the label keeps its stamp, so a save over REST cannot rewrite it. A new model
	starts at Unknown, which nobody set. The field arrives with the first migrate, so skip until then.
	"""
	if not doc.meta.has_field(LABEL_FIELD):
		return

	before = doc.get_doc_before_save()
	previous = before.get(LABEL_FIELD) if before else None

	if (doc.get(LABEL_FIELD) or DEFAULT_LABEL) != (previous or DEFAULT_LABEL):
		doc.update({BY_FIELD: frappe.session.user, ON_FIELD: now_datetime()})
	else:
		doc.update({field: before.get(field) if before else None for field in (BY_FIELD, ON_FIELD)})


def sync_agents_on_model(doc, method=None) -> None:
	"""Stub for A3.9 (doc_events Flow Model on_update): sync churchit's agents once a chat model exists."""
