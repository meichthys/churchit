import frappe
from frappe import _

from churchit.ai.opt_outs import get_member_ai_state
from churchit.church_people.member_access import limit_to_personal_details, open_own_personal_details
from churchit.church_scope import session_person

AI_SECTION = "ai_section"


def get_context(context):
	if frappe.form_dict.is_new:
		open_own_personal_details()
	limit_to_personal_details(context)
	show_ai_state(context)


def show_ai_state(context):
	"""Start the AI Features section with whether the church of the person on the page uses AI now, so a
	member can opt out before AI is on and still know if it is in use."""
	person = (context.reference_doc or {}).get("name") or session_person()
	church = frappe.db.get_value("Person", person, "church") if person else None
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == AI_SECTION:
			field.description = f"{get_member_ai_state(church)} {_(field.description or '')}".strip()
