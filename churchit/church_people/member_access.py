# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What a portal member, a Website User who signs in to the portal, may reach.

Staff are System Users and never pass through here. A member's own requests,
sign-ups and bookings are theirs through `if_owner` DocPerms; this module covers
the records other people own.
"""

from datetime import date

import frappe
from frappe import _
from frappe.model import table_fields
from frappe.rate_limiter import rate_limit
from frappe.utils import getdate

from churchit.church_people.derived import years_since
from churchit.church_people.family_relations import get_gendered_type
from churchit.church_people.household import ADULT, CHILD, can_edit, get_editable_children, role_of
from churchit.church_people.matching import SHARES_NOTHING, find_matches, record_possible_duplicates
from churchit.church_people.membership import VISITOR
from churchit.church_scope import church_filters, is_scoped, session_church, session_person

PERSONAL_DETAILS = "personal-details"
# What a member may name as the recipient of a prayer or alms request.
RECIPIENT_DOCTYPES = ("Person", "Family", "Group", "Ministry", "Missionary")


def is_portal_member(user=None):
	"""True for a signed-in Website User."""
	user = user or frappe.session.user
	return user != "Guest" and frappe.get_cached_value("User", user, "user_type") == "Website User"


def person_query_conditions(user=None, doctype=None):
	"""permission_query_conditions for Person: a member lists their own record and the Children they may edit."""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return ""
	own = f"`tabPerson`.`user` = {frappe.db.escape(user)}"
	children = ", ".join(frappe.db.escape(child) for child in get_editable_children(user))
	return f"({own} or `tabPerson`.`name` in ({children}))" if children else own


def refuse_other_people_to_members(doc, ptype=None, user=None):
	"""has_permission hook for Person: a member reaches their own Person and the Children they may edit.

	They read and write those Children (`household.can_edit`) and nothing more. Frappe reads any
	falsy return as a refusal, so everyone else gets True.
	"""
	user = user or frappe.session.user
	if not is_portal_member(user) or doc.get("user") == user:
		return True
	return ptype in ("read", "write") and can_edit(user, doc.name)


def refuse_member_edits_beyond_personal_details(person):
	"""A member edits a Person through the Personal Details form, so only its fields may change.

	The form sets nothing else, so anything more came straight through the API:
	a membership status, a family or a spouse set by the member. Nor may a member add
	a person: Frappe's web form saves a new record without checking their rights.
	"""
	# A Person a member's own sign-in adds (accounts.link_portal_user), or a child an Adult adds
	# (add_household_child), is not the member's edit.
	if not is_portal_member() or person.flags.from_portal_login or person.flags.from_household_page:
		return
	if person.is_new():
		frappe.throw(_("Ask the church office to add a person."), frappe.PermissionError)
	refuse_changes_beyond(person, personal_details_fields())


def refuse_member_edits_beyond_photo(family):
	"""A member changes only their household's photo, on the My Household page.

	`refuse_other_families_to_members` lets an Adult write their own Family, so anything more came straight
	through the API. `Family.validate` calls this before it changes anything itself. A save that ignores
	permissions is the app's own, such as a Person joining the roster.
	"""
	if is_portal_member() and not family.flags.ignore_permissions:
		refuse_changes_beyond(family, {"photo"})


def refuse_changes_beyond(doc, allowed: set[str]) -> None:
	"""Refuse a save of *doc* that changes a field outside *allowed*, naming the fields it changed."""
	before = doc.get_doc_before_save()
	changed = [
		df.label or df.fieldname
		for df in doc.meta.fields
		if df.fieldname not in allowed and get_comparable(doc, df) != get_comparable(before, df)
	]
	if changed:
		frappe.throw(
			_("Ask the church office to change {0}.").format(", ".join(_(label) for label in changed)),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def add_household_child(first_name: str, last_name: str, birthday: str, gender: str) -> str:
	"""/household: an Adult of a household adds a child under People Settings' adult age to it.

	The child is a Visitor of the household's church who shares nothing in the directory. The people
	they may be are left to staff as possible duplicates. Returns the new Person.
	"""
	from churchit.church_people.accounts import PORTAL  # accounts imports this module

	adult = session_person()
	if not adult or role_of(adult) != ADULT:
		frappe.throw(_("Only an adult of a household adds a child to it."), frappe.PermissionError)
	if not (first_name or "").strip() or not birthday:
		frappe.throw(_("Enter the child's first name and birthday."))
	# Store the date that was checked: the database reads some forms, such as 05-01-10, as another date.
	born = getdate(birthday)
	refuse_an_adult_birthday(born)

	family = frappe.db.get_value("Person", adult, "family")
	# Lock the household first, so two children added at once both keep their roster rows.
	church = frappe.db.get_value("Family", family, "church", for_update=True)
	child = frappe.get_doc(
		{
			"doctype": "Person",
			"first_name": first_name.strip(),
			"last_name": (last_name or "").strip(),
			"gender": gender,
			"birthday": born,
			"church": church,
			"family": family,
			"membership": VISITOR,
			"source": PORTAL,
			**SHARES_NOTHING,
		}
	)
	child.flags.from_household_page = True
	child.insert(ignore_permissions=True)
	mark_as_child(family, child)

	candidate = {"first_name": child.first_name, "last_name": child.last_name, "birth_date": child.birth_date}
	record_possible_duplicates(child.name, find_matches(candidate, church=church, exclude=child.name))
	return child.name


def refuse_an_adult_birthday(birthday: date) -> None:
	"""Refuse a birthday in the future, or one at or over People Settings' adult age: the office adds adults."""
	if birthday > getdate():
		frappe.throw(_("A birthday cannot be in the future."))
	adult_age = frappe.db.get_single_value("People Settings", "adult_age")
	if years_since(birthday) >= adult_age:
		frappe.throw(
			_("Add only a child under {0}. To add someone older, contact the church office.").format(
				adult_age
			)
		)


def mark_as_child(family_name: str, child) -> None:
	"""Make *child*'s roster row, which `Person.on_update` added, a Child and a Son or Daughter by gender."""
	family = frappe.get_doc("Family", family_name)
	row = next(member for member in family.members if member.member == child.name)
	row.household_role = CHILD
	row.relationship_to_primary_contact = get_gendered_type("child", child.gender)
	family.save(ignore_permissions=True)


def personal_details_fields():
	return {field.fieldname for field in frappe.get_cached_doc("Web Form", PERSONAL_DETAILS).web_form_fields}


def open_own_personal_details():
	"""Send a visitor who asks for a new Personal Details form to their own record, or to the list without one."""
	person = session_person()
	frappe.local.flags.redirect_location = (
		f"/{PERSONAL_DETAILS}/{person}/edit" if person else f"/{PERSONAL_DETAILS}/list"
	)
	raise frappe.Redirect


def limit_to_personal_details(context):
	"""Send the Personal Details page only the form's own fields.

	Frappe hands a signed-in visitor the whole record, which would put the
	medical notes and the office's summary fields in the page source.
	"""
	if not context.reference_doc:
		return
	allowed = {"name", "doctype", *personal_details_fields()}
	context.reference_doc = {key: value for key, value in context.reference_doc.items() if key in allowed}


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


def refuse_other_families_to_members(doc, ptype=None, user=None) -> bool:
	"""has_permission hook for Family: a member reads only their own household, and only its Adults write it.

	What an Adult may change is the photo alone (`refuse_member_edits_beyond_photo`).
	"""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return True
	own = frappe.db.get_value("Person", {"user": user}, ["name", "family"], as_dict=True)
	if not own or not own.family or own.family != doc.name:
		return False
	if ptype == "write":
		return role_of(own.name) == ADULT
	return ptype == "read"


def family_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions for Family: a member lists only their own household."""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return ""
	family = frappe.db.get_value("Person", {"user": user}, "family")
	return f"`tabFamily`.`name` = {frappe.db.escape(family)}" if family else "1 = 0"


def has_group_file_permission(doc, ptype=None, user=None) -> bool:
	"""A portal member reaches only the files of the groups they belong to.

	Adding one also needs a leader (`GroupFile.validate`).
	"""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return True
	person = frappe.db.get_value("Person", {"user": user}, "name")
	return bool(person) and bool(
		frappe.db.exists(
			"Group Member", {"parenttype": "Group", "parent": doc.get("group"), "person": person}
		)
	)


def group_file_query_conditions(user=None, doctype=None) -> str:
	"""For a portal member, only the Group Files of their groups."""
	user = user or frappe.session.user
	if not is_portal_member(user):
		return ""
	person = frappe.db.get_value("Person", {"user": user}, "name")
	if not person:
		return "1 = 0"
	return (
		"`tabGroup File`.`group` in (select `parent` from `tabGroup Member` "
		f"where `parenttype` = 'Group' and `person` = {frappe.db.escape(person)})"
	)


def make_group_files_private(doc, method=None) -> None:
	"""A file attached to a Group File is private.

	File's own before_insert has already written a public file to disk by now, so a public one is
	refused rather than flagged private.
	"""
	if doc.attached_to_doctype == "Group File" and not doc.is_private:
		frappe.throw(_("Files of a group are private. Upload the file again with Private ticked."))
