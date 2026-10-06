# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Church scoping shared by reports, public pages and the wildcard validate hook."""

import frappe
from frappe import _
from frappe.utils import cint
from frappe.utils.nestedset import get_descendants_of

CHURCH_FIELD = "church"
SHARED_FIELD = "is_shared"
SHARED_BY_FIELD = "shared_by_church"
# A shared record holds this in `church`. Frappe's own permission clause reads
# `church is empty or church in (yours)`, so the empty string is what makes a
# record visible to every church without a line of query code.
SHARED = ""
# Per-user default: a church picked in a report filter also brings its branches.
EXPAND_FILTER_DEFAULT = "church_filter_includes_branches"

# The people directory. Every church reads it, the way one congregation spread
# over several campuses expects, unless Church Features keeps it private. Either
# way only a person's own church may change them.
PEOPLE_DOCTYPES = ("Person", "Family")
READ_PERMISSIONS = ("read", "select", "print", "email", "report", "export")

# Doctypes a church may hand to every other church: reusable content, the supplier
# directory, the places and equipment that satellite congregations share, the
# occasions they hold together (a joint service, an organisation-wide board
# meeting), and the two containers money runs through, Fund and Ministry.
#
# Belief is here rather than global: branches normally hold one statement of faith,
# so its box defaults to ticked, but a branch that differs can keep its own.
#
# Fund and Ministry are containers, not money. Every gift and every expense keeps
# the church that gave or spent it, so per-church figures come from those rows at
# read time; what a shared container holds is the joint pot, which is the point of
# sharing one. The consequence is worth saying out loud: sharing a fund publishes
# its balance and its ledger to every church, and sharing a ministry publishes its
# combined spending. Both are the owning church's decision, one record at a time.
#
# Listing a doctype here only offers the checkbox. Nothing is shared until someone
# ticks it on a record, and only the church in `shared_by_church` may untick it.
SHAREABLE_DOCTYPES = (
	"Belief",
	"Church Asset",
	"Fund",
	"Function",
	"Location",
	"Meeting Minutes",
	"Ministry",
	"Room",
	"Sermon",
	"Sermon Handout",
	"Sermon Series",
	"Song",
	"Vendor",
)


def is_multi_church():
	"""True when the Church Features switch is on."""
	return is_feature_enabled("enable_multi_church")


def is_people_directory_private():
	"""True when Church Features keeps each church's people and families to itself."""
	return is_feature_enabled("private_people")


def is_feature_enabled(fieldname):
	"""True when a Church Features checkbox is ticked.

	Off until migrate has synced the field: pre-model-sync patches still save
	records (their own Patch Log among them) on the schema being upgraded.
	"""
	try:
		meta = frappe.get_meta("Church Features")
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return False
	return meta.has_field(fieldname) and bool(cint(frappe.db.get_single_value("Church Features", fieldname)))


def root_church():
	"""Name of the church without a parent, or None before setup creates it."""
	return frappe.db.get_value("Church", {"parent_church": ("is", "not set")}, "name", order_by="lft asc")


def is_scoped(meta):
	"""True when the doctype carries its own `church` Link (child tables and Singles never do)."""
	field = meta.get_field(CHURCH_FIELD)
	return bool(
		field
		and field.fieldtype == "Link"
		and field.options == "Church"
		and not meta.istable
		and not meta.issingle
	)


def scoped_doctypes():
	"""Churchit doctypes that carry a `church` Link. The doctype JSON is the registry."""
	candidates = frappe.get_all(
		"DocField",
		filters={"fieldname": CHURCH_FIELD, "fieldtype": "Link", "options": "Church"},
		pluck="parent",
	)
	return sorted(
		frappe.get_all(
			"DocType",
			filters={
				"name": ("in", candidates),
				"module": ("in", frappe.get_module_list("churchit")),
				"istable": 0,
				"issingle": 0,
			},
			pluck="name",
		)
	)


def allowed_churches(user=None):
	"""Churches the user may see, or None when unrestricted."""
	user = user or frappe.session.user
	if not is_multi_church() or user == "Administrator":
		return None
	permissions = frappe.permissions.get_user_permissions(user).get("Church")
	if not permissions:
		return None
	return sorted({permission.get("doc") for permission in permissions})


def requested_church():
	"""The published church the current page is about, when ``?church=`` names one.

	Only a published church counts: the value arrives in the query string, so a
	visitor could otherwise name any church on the site.
	"""
	form_dict = getattr(frappe.local, "form_dict", None)
	requested = form_dict.get(CHURCH_FIELD) if form_dict else None
	return requested if requested and frappe.db.get_value("Church", requested, "publish") else None


def default_church(user=None):
	"""The church a new record belongs to when it names none of its own.

	The reader's own church comes first: staff work in one church whatever page
	they last opened. A visitor has none, so the branch whose public page took
	the record is what settles where it lands, rather than the main church.
	"""
	return frappe.defaults.get_user_default("Church", user) or requested_church() or root_church()


def church_filter_includes_branches(user=None):
	"""True when the user chose to have a picked church bring its branches along.

	Read from the row itself: the user-defaults cache is per worker and lags a
	change by a request or two, which would make the banner switch look broken.
	"""
	value = frappe.db.get_value(
		"DefaultValue", {"parent": user or frappe.session.user, "defkey": EXPAND_FILTER_DEFAULT}, "defvalue"
	)
	return bool(cint(value))


def church_filter(filters):
	"""Churches a report may show: the requested one, else every allowed one, else None.

	A requested church narrows the way a list filter does, unless the user
	turned on branch expansion, in which case its branches come along too.
	Leaving the filter blank shows every church the user has in scope.
	"""
	requested = (filters or {}).get(CHURCH_FIELD)
	allowed = allowed_churches()
	if not requested:
		return allowed
	if allowed is not None and requested not in allowed:
		frappe.throw(_("You do not have access to church {0}").format(requested), frappe.PermissionError)
	churches = [requested]
	if church_filter_includes_branches():
		churches += get_descendants_of("Church", requested)
	return [church for church in churches if allowed is None or church in allowed]


def scoped(query, table, filters):
	"""Restrict a query builder query to the churches the reader may see.

	Pass the table that owns `church`; for a child table, scope its parent and join.
	Shared records come along, the way they do in a list view.
	"""
	churches = church_filter(filters)
	return query.where(table.church.isin([*churches, SHARED])) if churches is not None else query


def church_query_filters(filters):
	"""The equivalent of scoped() for frappe.get_all and frappe.db.count callers."""
	churches = church_filter(filters)
	return {CHURCH_FIELD: ("in", [*churches, SHARED])} if churches is not None else {}


def church_filters(church, **filters):
	"""Filters for a public page: the selected church and whatever is shared with it."""
	if is_multi_church() and church:
		filters[CHURCH_FIELD] = ("in", [church, SHARED])
	return filters


def selected_church_filters(**filters):
	"""church_filters for the church the current page is about, as a Jinja method.

	Website templates are edited by churches, so resolving the selection here
	keeps a page one call away from being scoped correctly.
	"""
	from churchit.church_foundations.doctype.church.church import selected_church_name

	return church_filters(selected_church_name(), **filters)


def session_person():
	"""The Person linked to the logged-in user, or None."""
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("Person", {"user": frappe.session.user}, "name")


def session_church():
	"""The church of the logged-in user's Person, or None."""
	person = session_person()
	return frappe.db.get_value("Person", person, CHURCH_FIELD) if person else None


def document_church(doc):
	"""The church a document belongs to, following a child row to its parent."""
	if doc.get(CHURCH_FIELD):
		return doc.get(CHURCH_FIELD)
	parenttype = doc.get("parenttype")
	if parenttype and doc.get("parent") and frappe.get_meta(parenttype).has_field(CHURCH_FIELD):
		return frappe.db.get_value(parenttype, doc.get("parent"), CHURCH_FIELD)
	return None


def is_shareable(doc):
	"""True when this doctype lets a church hand the record to every other church."""
	return doc.doctype in SHAREABLE_DOCTYPES and doc.meta.has_field(SHARED_FIELD)


def inherits_a_shared_church(doc):
	"""True when this record takes its church from a record that is shared with every church.

	A booking of a shared room is the case that matters: it has to stay visible
	to every church, or a branch reads an empty diary for a room already taken.
	"""
	field = doc.meta.get_field(CHURCH_FIELD)
	if not field or not field.fetch_from:
		return False
	source_field = field.fetch_from.split(".")[0]
	source = doc.get(source_field)
	if not source:
		return False
	source_doctype = doc.meta.get_field(source_field).options
	return frappe.db.get_value(source_doctype, source, CHURCH_FIELD) == SHARED


def is_being_unshared(doc):
	"""True when this save takes a record that was shared with every church back."""
	before = doc.get_doc_before_save()
	return bool(before and cint(before.get(SHARED_FIELD)) and not cint(doc.get(SHARED_FIELD)))


def belongs_to_another_church(owner_church):
	"""True when a shared record came from a church the caller does not hold.

	Administrator belongs to no church and may do as it likes. Everyone else is
	judged by the churches they hold, and holding none means unrestricted
	*reading*, not ownership of what other churches shared.
	"""
	if not owner_church or frappe.session.user == "Administrator":
		return False
	return owner_church not in (allowed_churches() or [])


def only_the_sharing_church_may(doc, action):
	"""Refuse *action* on a record another church shared with this one.

	A shared record is readable and writable by every church, so without this a
	branch could untick the box on something the main church shared, or delete it
	outright, and pull it out of the whole organisation, itself included. Sharing
	is the owner's decision to reverse; a recipient asks.

	Code saving with ``ignore_permissions`` is asserting it knows better, so
	patches, scheduled jobs and the sample data loader are left alone.
	"""
	owner_church = doc.get(SHARED_BY_FIELD)
	if not belongs_to_another_church(owner_church):
		return

	frappe.throw(
		_("Only {0} can {1} this {2}, because they shared it with your church.").format(
			frappe.db.get_value("Church", owner_church, "church_name") or owner_church,
			action,
			_(doc.doctype),
		),
		frappe.PermissionError,
	)


def refuse_unsharing_by_another_church(doc):
	"""Only the church that shared a record may untick the box."""
	if doc.flags.ignore_permissions or not doc.meta.has_field(SHARED_BY_FIELD) or doc.is_new():
		return
	if not is_being_unshared(doc):
		return
	only_the_sharing_church_may(doc.get_doc_before_save(), _("stop sharing"))


def refuse_deleting_another_churches_record(doc, method=None):
	"""doc_events on_trash hook: a recipient church may not delete what was shared with it.

	Unticking the box is already refused for a recipient, and deleting the record
	is the same loss for every other church through a door of its own.
	"""
	if doc.flags.ignore_permissions or not is_multi_church() or not is_scoped(doc.meta):
		return
	if not is_shareable(doc) or not cint(doc.get(SHARED_FIELD)):
		return
	only_the_sharing_church_may(doc, _("delete"))


def restamp_dependents(doc):
	"""Give the records that took their church from this one its own church back.

	A booking of a shared room is stamped as shared when it is made, so every
	church reads the same diary. Nothing revisited that when the room stopped
	being shared, which left the booking, and whoever made it, on show to every
	church for good.
	"""
	for doctype in scoped_doctypes():
		meta = frappe.get_meta(doctype)
		field = meta.get_field(CHURCH_FIELD)
		if not field or not field.fetch_from:
			continue
		source_field = meta.get_field(field.fetch_from.split(".")[0])
		if not source_field or source_field.options != doc.doctype:
			continue
		frappe.db.set_value(
			doctype,
			{source_field.fieldname: doc.name, CHURCH_FIELD: SHARED},
			CHURCH_FIELD,
			doc.get(CHURCH_FIELD),
			update_modified=False,
		)


def refuse_another_churches_record(doc, doctype, name):
	"""Refuse *doc* when it points at a *doctype* record belonging to a different church.

	Money carries the church that gave or spent it, and the fund it lands in has
	to be one that church may use: its own, or one shared with every church. The
	hole this closes is an indirect one, where a global Expense Type names a fund
	and every church's expenses of that type debit it.

	Churches are compared rather than permissions, because the writes that most
	need the check run with ``ignore_permissions``: an online gift, the scheduled
	missionary expenses, the sample data loader.

	The church a new record is about to take is resolved here rather than read off
	the document: ``ensure_church`` settles it on the same ``validate``, and a
	doc_events handler runs after the controller's own method.
	"""
	if not is_multi_church() or not name:
		return
	owner = frappe.db.get_value(doctype, name, CHURCH_FIELD)
	church = document_church(doc) or default_church()
	if not owner or not church or owner == church:
		return

	frappe.throw(
		_(
			"{0} {1} belongs to another church. Tick Shared with all churches on it, or choose one of {2}."
		).format(
			_(doctype),
			frappe.bold(name),
			frappe.db.get_value("Church", church, "church_name") or church,
		),
		frappe.PermissionError,
	)


def refuse_changing_another_churches_people(doc, ptype=None, user=None):
	"""has_permission hook for Person and Family: only their own church may change them.

	Their `church` Link ignores user permissions so that every church can read
	the directory, which leaves this as the only check on writes. Both the stored
	church and the one being saved count, so nobody can take a person over by
	editing the field. Frappe reads any falsy return, None included, as a refusal.

	A call without *ptype* asks for every right at once, the desk's form load
	among them, and a refusal there would take reading away too. The form locks
	itself instead (`church.lock_another_churchs_people`).
	"""
	if not ptype or ptype in READ_PERMISSIONS or not is_multi_church():
		return True
	allowed = allowed_churches(user)
	if allowed is None:
		return True
	churches = {doc.get(CHURCH_FIELD)}
	if not doc.is_new():
		churches.add(frappe.db.get_value(doc.doctype, doc.name, CHURCH_FIELD))
	return not churches - set(allowed) - {None, SHARED}


def ensure_church(doc, method=None):
	"""doc_events validate hook: settle which church a record belongs to, or refuse to save it.

	A shared record stores the empty string, which is what Frappe reads as
	"every church". The church that shared it is kept in `shared_by_church`, so
	unticking the box returns the record where it came from rather than to
	whoever happened to save it.
	"""
	if not is_multi_church() or not is_scoped(doc.meta):
		return

	if is_shareable(doc):
		refuse_unsharing_by_another_church(doc)
		if cint(doc.get(SHARED_FIELD)):
			# Whoever it belonged to, else whoever shared it first, else whoever is sharing it now.
			doc.set(
				SHARED_BY_FIELD,
				doc.get(CHURCH_FIELD) or doc.get(SHARED_BY_FIELD) or default_church(),
			)
			doc.set(CHURCH_FIELD, SHARED)
			return

	if not doc.get(CHURCH_FIELD) and inherits_a_shared_church(doc):
		doc.set(CHURCH_FIELD, SHARED)
		if doc.meta.has_field(SHARED_BY_FIELD) and not doc.get(SHARED_BY_FIELD):
			doc.set(SHARED_BY_FIELD, default_church())
		return

	unshared = is_shareable(doc) and not doc.is_new() and is_being_unshared(doc)

	if not doc.get(CHURCH_FIELD):
		doc.set(CHURCH_FIELD, doc.get(SHARED_BY_FIELD) or default_church())
	if not doc.get(CHURCH_FIELD):
		frappe.throw(_("Church could not be determined for {0} {1}").format(_(doc.doctype), doc.name))

	if unshared:
		restamp_dependents(doc)


def extend_bootinfo(bootinfo):
	"""Tell the desk whether multi-church is on and whether the user can include branches."""
	from churchit.church_foundations.church_access import include_branches_state

	multi_church = is_multi_church()
	allowed = allowed_churches()
	bootinfo.churchit = {
		"multi_church": multi_church,
		"church": default_church() if multi_church else None,
		# Every church reads the people directory, so Person and Family show whose they are.
		"shared_people": multi_church and not is_people_directory_private(),
		"include_branches": include_branches_state(frappe.session.user),
		# One church to deal with: the church field, its filter and the per-church
		# rows of a settings page would only ever name that one church. Always true
		# with the switch off, which is the case every `!single_church` field reads.
		"single_church": not multi_church or (allowed is not None and len(allowed) == 1),
		# Which churches are the reader's own, so the form can tell a record shared
		# with them from one they shared. None means unrestricted.
		"churches": allowed,
		"expand_church_filters": church_filter_includes_branches(),
	}
