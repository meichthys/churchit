# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What a portal member, a Website User who signs in to the portal, may reach.

Staff are System Users and never pass through here. A member's own requests,
sign-ups and bookings are theirs through `if_owner` DocPerms; this module covers
the records other people own.
"""

import frappe
from frappe import _
from frappe.model import table_fields

from churchit.church_scope import church_filters, is_scoped, session_church, session_person

PERSONAL_DETAILS = "personal-details"
# What a member may name as the recipient of a prayer or alms request.
RECIPIENT_DOCTYPES = ("Person", "Family", "Group", "Ministry", "Missionary")


def is_portal_member(user=None):
	"""True for a signed-in Website User."""
	user = user or frappe.session.user
	return user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "Website User"


def person_query_conditions(user=None, doctype=None):
	"""permission_query_conditions for Person: a member lists only their own record."""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return ""
	return f"`tabPerson`.`user` = {frappe.db.escape(user)}"


def refuse_other_people_to_members(doc, ptype=None, user=None):
	"""has_permission hook for Person: a member reaches only the Person linked to their login.

	Frappe reads any falsy return as a refusal, so everyone else gets True.
	"""
	user = user or frappe.session.user
	return not is_portal_member(user) or doc.get("user") == user


def refuse_member_edits_beyond_personal_details(person):
	"""A member edits their own Person through the Personal Details form, so only its fields may change.

	The form sets nothing else, so anything more came straight through the API:
	a membership status, a family or a head of household set by the member.
	"""
	if not is_portal_member() or person.is_new():
		return
	before = person.get_doc_before_save()
	allowed = {
		field.fieldname for field in frappe.get_cached_doc("Web Form", PERSONAL_DETAILS).web_form_fields
	}
	changed = [
		df.label or df.fieldname
		for df in person.meta.fields
		if df.fieldname not in allowed and get_comparable(person, df) != get_comparable(before, df)
	]
	if changed:
		frappe.throw(
			_("Ask the church office to change {0}.").format(", ".join(_(label) for label in changed)),
			frappe.PermissionError,
		)


def get_comparable(doc, df):
	"""A field's value in a form two loads of the same record compare equal on."""
	if df.fieldtype in table_fields:
		return [
			row.as_dict(no_default_fields=True, no_child_table_fields=True) for row in doc.get(df.fieldname)
		]
	return doc.get(df.fieldname)


def pin_to_members_own_person(doc, fieldname):
	"""A member's portal request always names them, whatever the form sent."""
	if is_portal_member():
		doc.set(fieldname, session_person())


def get_recipient_filters(doctype):
	"""Filters for the records a member may name as a recipient: their church's and shared ones."""
	if doctype not in RECIPIENT_DOCTYPES:
		frappe.throw(
			_("{0} cannot be the recipient of a request.").format(_(doctype)), frappe.PermissionError
		)
	filters = church_filters(session_church()) if is_scoped(frappe.get_meta(doctype)) else {}
	if doctype == "Group":
		filters["public"] = 1
	return filters


def validate_members_recipient(doc):
	"""Refuse a recipient the member could not have picked in the portal's search.

	The request stores the recipient's title, so without this a member could post
	any record's name and read its title back off their own request.
	"""
	if not is_portal_member() or not doc.recipient:
		return
	filters = get_recipient_filters(doc.recipient_type)
	if not frappe.db.exists(doc.recipient_type, {"name": doc.recipient, **filters}):
		frappe.throw(_("Choose a recipient from your church."), frappe.PermissionError)
