import frappe

from churchit.church_people.member_access import limit_to_personal_details, open_own_personal_details


def get_context(context):
	if frappe.form_dict.is_new:
		open_own_personal_details()
	limit_to_personal_details(context)
