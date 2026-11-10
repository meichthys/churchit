# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

SUGGESTION_DOCTYPE = "Church AI Suggestion"


class ChurchAISuggestion(Document):
	"""AI's suggestion on one new request (churchit.ai.triage). A doctype of its own, so its document
	permissions keep it from every other reader of the request: web forms, REST, the timeline, reports."""

	def validate(self):
		self.church = frappe.db.get_value(self.reference_doctype, self.reference_name, "church")


def set_suggestion(doctype: str, name: str, values: dict) -> str:
	"""Keep *values* as the suggestion on the record and return its name. The reviewer who runs it may
	not write the doctype."""
	filters = {"reference_doctype": doctype, "reference_name": name}
	existing = frappe.db.get_value(SUGGESTION_DOCTYPE, filters)
	suggestion = (
		frappe.get_doc(SUGGESTION_DOCTYPE, existing) if existing else frappe.new_doc(SUGGESTION_DOCTYPE)
	)
	suggestion.update({**filters, **values})
	suggestion.save(ignore_permissions=True)
	return suggestion.name


def delete_suggestion(doctype: str, name: str) -> None:
	"""Delete the suggestion on the record, with its assignments, notices and timeline."""
	filters = {"reference_doctype": doctype, "reference_name": name}
	for suggestion in frappe.get_all(SUGGESTION_DOCTYPE, filters=filters, pluck="name"):
		frappe.delete_doc(SUGGESTION_DOCTYPE, suggestion, ignore_permissions=True, delete_permanently=True)


def delete_with_request(doc: Document, method=None) -> None:
	"""on_trash of Prayer Request and Care Request: the suggestion goes with its request."""
	delete_suggestion(doc.doctype, doc.name)


def follow_request_church(doc: Document, method=None) -> None:
	"""on_update of Prayer Request and Care Request: the suggestion moves with its request to another
	church, so only that church's readers read it."""
	if doc.get_doc_before_save() and doc.has_value_changed("church"):
		filters = {"reference_doctype": doc.doctype, "reference_name": doc.name}
		frappe.db.set_value(SUGGESTION_DOCTYPE, filters, "church", doc.church)
