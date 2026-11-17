# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Keeps each user's Church User Permission in step with their Person, and guards the settings and lookups every church shares."""

import frappe
from frappe import _
from frappe.core.doctype.version.version import get_diff
from frappe.model.document import Document
from frappe.permissions import add_user_permission
from frappe.utils import sbool

from churchit.church_scope import (
	CHURCH_FIELD,
	EXPAND_FILTER_DEFAULT,
	allowed_churches,
	has_church_access,
	is_multi_church,
	is_scoped,
)

UNSCOPED_USERS = ("Administrator", "Guest")

# The vocabulary every church picks from: one branch's change reaches every church. Note Category guards
# itself (NoteCategory.refuse_unless_every_church): a branch may still describe one, but not change who reads it.
GLOBAL_LOOKUPS = frozenset(
	{
		"Address Type",
		"Background Check Type",
		"Care Request Type",
		"Case Type",
		"Communication Purpose",
		"Connection Card Interest",
		"Email Type",
		"Expense Type",
		"Function Attendance Type",
		"Function Type",
		"Group Role",
		"Group Status",
		"Group Type",
		"Inactive Reason",
		"Life Event Type",
		"Marital Status",
		"Member Status",
		"Membership Type",
		"Missionary Status",
		"Missionary Support Frequency",
		"Payment Type",
		"Person Relation Type",
		"Phone Type",
		"Position Type",
		"Prayer Request Status",
		"Prayer Request Type",
		"Sign-Up Item",
		"Skill",
		"Visit Type",
	}
)
BRANCH_MANAGER_PROFILE = "Church Branch Manager"
MANAGER_PROFILE = "Church Manager"


def user_church_permissions(user):
	return frappe.get_all(
		"User Permission",
		filters={"user": user, "allow": "Church"},
		fields=["name", "for_value", "hide_descendants"],
	)


def has_every_church(user: str) -> bool:
	"""True when *user* reaches every church: unrestricted, or holding each church that has no parent.

	Holding the main church reaches its branches even while they are hidden, because the
	user may include them at will.
	"""
	if allowed_churches(user) is None:
		return True
	held = {permission.for_value for permission in user_church_permissions(user)}
	return set(frappe.get_all("Church", filters={"parent_church": ("is", "not set")}, pluck="name")) <= held


def refuse_changing_shared_settings(doc: Document, church_tables: tuple[str, ...] = ()) -> None:
	"""validate on a Single that every church shares: only someone across every church changes it.

	A row of a table in *church_tables* belongs to the church it names, so a user may change the
	rows of their own churches. A row that names no church serves every church. Otherwise one
	branch's manager could untick Keep People and Families Private and read every church's people.
	Saves with ignore_permissions are the app's own.
	"""
	if doc.flags.ignore_permissions or has_every_church(frappe.session.user):
		return
	before = doc.get_doc_before_save() or frappe.get_doc(doc.doctype)
	for row in (doc, *doc.get_all_children()):
		# get_diff compares links by these caller-sent titles, so they could make a change look like none.
		row.delete_key("__link_titles")
	diff = get_diff(before, doc)
	if not diff:
		return
	tables = {change[0] for change in diff.added + diff.removed + diff.row_changed}
	if diff.changed or tables - set(church_tables):
		frappe.throw(
			_(
				"{0} apply to every church. Only someone who works across every church can change them."
			).format(_(doc.doctype)),
			frappe.PermissionError,
		)

	rows = [frappe._dict(row) for _table, row in diff.added + diff.removed]
	for table, index, name, _changes in diff.row_changed:
		rows += [doc.get(table)[index], *(row for row in before.get(table) if row.name == name)]
	allowed = allowed_churches()
	for row in rows:
		if row.church not in allowed:
			refuse_another_churches_row(doc, row)


def refuse_changing_global_lookup(doc: Document, method: str | None = None, *args, **kwargs) -> None:
	"""validate, on_trash and before_rename on every doctype: only someone across every church changes a global lookup.

	Otherwise one branch's manager could rename a Member Status or delete an Expense Type that every
	church uses. Saves with ignore_permissions, installs, migrations and patches are the app's own.
	"""
	if doc.doctype not in GLOBAL_LOOKUPS or doc.flags.ignore_permissions:
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch:
		return
	if has_every_church(frappe.session.user):
		return
	frappe.throw(
		_(
			"{0} is shared by every church. Only someone who works across every church can add, change or delete one."
		).format(_(doc.doctype)),
		frappe.PermissionError,
	)


def refuse_another_churches_row(doc: Document, row) -> None:
	table = _(doc.meta.get_label(row.parentfield))
	if not row.church:
		message = _(
			"Row {0} of {1} serves every church. Only someone who works across every church can change it."
		)
		frappe.throw(message.format(row.idx, table), frappe.PermissionError)
	church = frappe.db.get_value("Church", row.church, "church_name") or row.church
	frappe.throw(
		_("Row {0} of {1} belongs to {2}. Only that church can change it.").format(row.idx, table, church),
		frappe.PermissionError,
	)


def set_user_church(user, church):
	"""Point the user's Church permission at `church`, replacing any other one."""
	existing = user_church_permissions(user)
	if len(existing) == 1 and existing[0].for_value == church:
		return
	for permission in existing:
		frappe.delete_doc("User Permission", permission.name, ignore_permissions=True, force=True)
	add_user_permission("Church", church, user, ignore_permissions=True, is_default=1, hide_descendants=1)


def can_limit_logins(user: str | None = None) -> bool:
	"""True when *user* may point a login at its person's church: a System Manager or someone across every church."""
	user = user or frappe.session.user
	return "System Manager" in frappe.get_roles(user) or has_every_church(user)


@frappe.whitelist(methods=["POST"])
def limit_login_to_church(person: str) -> None:
	"""Point the Church permission of *person*'s login at *person*'s church, branches hidden. Changes data.

	A staff login linked by hand keeps the churches it had (`Person.sync_church_permission`), so a
	login made in the desk for a branch's staff still works in the main church until someone limits it.
	"""
	if not is_multi_church() or not can_limit_logins():
		frappe.throw(
			_("Only someone who works across every church can limit a login to a church."),
			frappe.PermissionError,
		)
	doc = frappe.get_doc("Person", person)
	doc.check_permission("write")
	if not doc.user or not doc.church:
		frappe.throw(_("Set the Church and the Portal User of {0} first.").format(doc.full_name))
	set_user_church(doc.user, doc.church)
	suggest_branch_profile(doc.user, doc.church)


def suggest_branch_profile(user: str, church: str) -> None:
	"""Say that a manager limited to a branch fits the Church Branch Manager profile better.

	The Church Manager profile also holds Website, Workspace, Report and Dashboard Manager, which
	change Frappe settings that act on every church.
	"""
	if not frappe.db.get_value("Church", church, "parent_church"):
		return
	profiles = frappe.get_all("User Role Profile", filters={"parent": user}, pluck="role_profile")
	if MANAGER_PROFILE not in profiles:
		return
	frappe.msgprint(
		_(
			"{0} has the {1} role profile, which can also change the website, workspaces, reports and "
			"dashboards of every church. For the manager of one branch, give the login the {2} role "
			"profile in the User form instead."
		).format(frappe.bold(user), _(MANAGER_PROFILE), _(BRANCH_MANAGER_PROFILE)),
		title=_("Branch Manager Profile"),
		indicator="orange",
	)


def move_church_permissions(church, destination):
	"""Point everyone scoped to *church* at *destination* instead.

	Called when a church is deleted. A permission that outlives its church hides
	every record of every other church from the user holding it, and deleting it
	outright would do the opposite: no Church permission means no restriction, so
	they would see every church. The parent is where a closed branch's people
	belong, and it keeps them scoped either way.
	"""
	holders = frappe.get_all(
		"User Permission", filters={"allow": "Church", "for_value": church}, pluck="user"
	)
	for user in holders:
		set_user_church(user, destination)


def grant_root_permission_to_users(root):
	"""Give every enabled user without a Church permission the root church, branches hidden."""
	bound = set(frappe.get_all("User Permission", filters={"allow": "Church"}, pluck="user"))
	users = frappe.get_all("User", filters={"enabled": 1, "name": ("not in", UNSCOPED_USERS)}, pluck="name")
	for user in users:
		if user not in bound:
			add_user_permission(
				"Church", root, user, ignore_permissions=True, is_default=1, hide_descendants=1
			)


def scope_new_user(doc, method=None):
	"""after_insert on User: give a new login the church it was created in.

	A user with no Church permission is unrestricted, so a login made outside the
	Person invite (the desk User list, a website sign-up) used to see every
	church. The church the request is about is the best guess available: the
	branch whose page took a sign-up, or the church of whoever is adding the user
	in the desk. Linking a Person repoints it, so this is only the starting point.
	"""
	from churchit.church_foundations.doctype.church.church import selected_church_name

	if not is_multi_church() or doc.name in UNSCOPED_USERS or not doc.enabled:
		return
	if user_church_permissions(doc.name):
		return
	church = selected_church_name()
	if church:
		add_user_permission(
			"Church", church, doc.name, ignore_permissions=True, is_default=1, hide_descendants=1
		)


def refuse_sharing_outside_the_church(doc, method=None):
	"""validate on DocShare: a church's record is shared only with users who can see that church.

	Frappe shares a record with an assignee who cannot read it, so without this an
	assignment, or the Share menu, handed one church's record to another church's user.
	"""
	if not is_multi_church() or not is_scoped(frappe.get_meta(doc.share_doctype)):
		return
	church = frappe.db.get_value(doc.share_doctype, doc.share_name, CHURCH_FIELD)
	if doc.everyone and church:
		frappe.throw(
			_("{0} {1} belongs to one church, so it cannot be shared with everyone.").format(
				_(doc.share_doctype), doc.share_name
			),
			frappe.PermissionError,
		)
	if doc.user and not has_church_access(doc.user, church):
		frappe.throw(
			_("{0} cannot see records of {1}, so {2} {3} cannot be shared with or assigned to them.").format(
				doc.user, church, _(doc.share_doctype), doc.share_name
			),
			frappe.PermissionError,
		)


def include_branches_state(user):
	"""True or False for a user whose church has branches to include; None for everyone else."""
	if not is_multi_church() or user in UNSCOPED_USERS:
		return None
	permissions = user_church_permissions(user)
	if len(permissions) != 1 or not has_branches(permissions[0].for_value):
		return None
	return not permissions[0].hide_descendants


def has_branches(church):
	left, right = frappe.db.get_value("Church", church, ["lft", "rgt"])
	return (right or 0) - (left or 0) > 1


@frappe.whitelist(methods=["POST"])
def set_church_filter_expansion(expand: bool) -> bool:
	"""Remember for the caller whether a church picked in a report filter brings its branches along. Changes data."""
	frappe.defaults.set_user_default(EXPAND_FILTER_DEFAULT, "1" if sbool(expand) else "0")
	return bool(sbool(expand))


@frappe.whitelist(methods=["POST"])
def set_include_branches(include: bool) -> bool:
	"""Show or hide the branch churches' records for the caller, on their own Church permission. Changes data.

	Returns whether the branches now show.
	"""
	user = frappe.session.user
	if include_branches_state(user) is None:
		frappe.throw(_("Your church has no branches to include."))
	permission = frappe.get_doc("User Permission", user_church_permissions(user)[0].name)
	permission.hide_descendants = 0 if sbool(include) else 1
	permission.save(ignore_permissions=True)
	return not permission.hide_descendants
