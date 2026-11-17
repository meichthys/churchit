import frappe
from frappe import _
from frappe.utils import cint
from frappe.website.doctype.web_form.web_form import get_link_options

from churchit.ai.opt_outs import get_member_ai_state
from churchit.church_people.member_access import limit_to_personal_details, open_own_personal_details
from churchit.church_scope import session_person

AI_SECTION = "ai_section"
DIRECTORY_SECTION = "directory_section"
# The Type column of each contact table the member fills in. The types are shared lookup lists.
TYPE_COLUMNS = {"emails": "email_type", "phones": "phone_type"}


def get_context(context):
	"""Open a member's own record at once from the list too, as the menu link has one row to show."""
	if frappe.form_dict.is_new or (frappe.form_dict.is_list and session_person()):
		open_own_personal_details()
	limit_to_personal_details(context)
	show_ai_state(context)
	show_directory_state(context)
	offer_every_type(context)


def offer_every_type(context):
	"""Give the Type columns every type, as Allow Read on All Link Options does for a field of the form itself.

	Frappe offers a signed-in member only the link options they own, and a child table's column cannot carry
	that setting.
	"""
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		column = TYPE_COLUMNS.get(field.fieldname)
		for df in field.get("fields") or []:
			if df["fieldname"] == column:
				link_doctype = frappe.get_meta(field.options).get_field(column).options
				df["options"] = get_link_options(
					context.web_form_doc.name, link_doctype, allow_read_on_all_link_options=True
				)


def show_directory_state(context):
	"""Say in the Directory section that the church shows no Member Directory page while People Settings has it off."""
	if cint(frappe.db.get_single_value("People Settings", "member_directory")):
		return
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == DIRECTORY_SECTION:
			field.description = _(
				"Your church has no Member Directory page now. If it adds one, other members see what you choose here."
			)


def show_ai_state(context):
	"""Start the AI Features section with whether the church of the person on the page uses AI now, so a
	member can opt out before AI is on and still know if it is in use."""
	person = (context.reference_doc or {}).get("name") or session_person()
	church = frappe.db.get_value("Person", person, "church") if person else None
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == AI_SECTION:
			field.description = f"{get_member_ai_state(church)} {_(field.description or '')}".strip()
