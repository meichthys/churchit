# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Doctypes whose records churchit's own AI features send only to a Local or Zero retention model.

Church AI Settings keeps them in Only for Local or Zero Retention Models (private_model_doctypes). The
runner (churchit.ai.runner) gives a prompt with one of their records to the Private Work agent and
refuses it unless that agent's model has one of those labels. Chats and AI apps work with their
user's permissions and are not limited by the list. It is separate from Blocked from Flow Knowledge.
"""

import frappe

from churchit.ai.switch import SETTINGS

# Care, counseling, private notes, prayer, giving, background checks, pickup restrictions, alms,
# member transfers and meeting minutes. Never Person or Church Email.
RECOMMENDED = (
	"Alms Request",
	"Background Check",
	"Care Assignment",
	"Care Request",
	"Collection",
	"Counseling Case",
	"Giving Import",
	"Giving Statement",
	"Meeting Minutes",
	"Member Transfer",
	"Online Donation",
	"Person Note",
	"Pickup Restriction",
	"Pledge",
	"Prayer",
	"Prayer Request",
	"Visitation Log",
)


def get_private_doctypes() -> set[str]:
	"""The doctypes in Church AI Settings' Only for Local or Zero Retention Models."""
	return frappe.get_cached_doc(SETTINGS).private_doctypes


def fill_private_doctypes() -> None:
	"""after_install and a v1_0 patch: start an empty list with the recommended doctypes. A list with
	rows stays as it is, so it is safe to run again."""
	settings = frappe.get_single(SETTINGS)
	if not settings.private_model_doctypes:
		add_recommended_private_doctypes(settings)


def add_recommended_private_doctypes(settings) -> int:
	"""Add each recommended doctype that the list lacks, keep every row, and return how many it added."""
	missing = [doctype for doctype in RECOMMENDED if doctype not in settings.private_doctypes]
	for doctype in missing:
		settings.append("private_model_doctypes", {"document_type": doctype})
	if missing:
		settings.save()
	return len(missing)


@frappe.whitelist(methods=["POST"])
def use_recommended_private_doctypes() -> int:
	"""Add each recommended doctype missing from Only for Local or Zero Retention Models. Changes data.

	The list is on Church AI Settings. For System Managers and Church Managers; it works while AI is
	off. It keeps every row, a row that an admin added included, and returns how many rows it added.
	"""
	frappe.only_for(("System Manager", "Church Manager"), message=True)
	return add_recommended_private_doctypes(frappe.get_single(SETTINGS))
