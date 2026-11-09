# AGENTS.md

Notes for anyone (person or agent) adding functionality to Churchit. `README.md` covers installing,
contributing and how the app ships its data, and each module's docstring explains how that area
works. This file covers the things that are not visible in a diff and will break quietly if you do
not know them.

Read this before adding a doctype, a report, a chart, a notification, or a page. The general rules
come first, from "The one invariant" to "House style". Notes on single areas of the app follow.

## The one invariant

A site can run in **multi-church** mode: one main church with branch churches under it, switched on
in `Church Features`. Records belong to a church, and a user sees only their own church's records
unless they opt into the branches beneath it.

People and families are the exception. Every church reads the whole directory, the way one
congregation over several campuses expects. Only a person's own church may change them.
`Keep People and Families Private to Each Church` in `Church Features` scopes them like every
other record, except their addresses, which the staff of every church read (see "Roles"). Records
about a person, such as care requests, counseling and giving, keep their own church either way.

The failure mode is silent. Nothing errors when you get this wrong; a branch simply sees rows that
belong to another church. The hygiene tests in `churchit/tests/` (`test_*_hygiene.py`) check the
rules below where they can. CI does not run the tests, so run them before you commit.

Access rides on native Frappe **User Permissions** on `Church`. A user's `Person.church` drives the
permission; `hide_descendants` is the "include branch churches" switch. A user with no Church
permission sees every church. `permission_query_conditions` is never used for church scoping.
Person (a member lists their own record and the household Children they may edit, see "Member
portal"), Family (a member's own household), Person Note (Note Category roles), Follow-up Card (the
Church Follow-up role) and Prayer Request (Visibility) use it for other rules.

The directory is the one place where User Permissions do not limit a record by its church. The
`church` Link on `Person` and `Family` ships with `ignore_user_permissions: 1`, so User Permissions
do not filter them. A User Permission cannot tell a read from a write, so the `has_permission` hook
`church_scope.refuse_changing_another_churches_people` refuses every other action outside the
user's churches. A Frappe `has_permission` hook refuses on any falsy return, `None` included. When
the directory is private, `multi_church.apply_people_privacy` adds a Property Setter that turns
the flag off.

A read of `Person` or `Family` that a user sees must follow the setting. `frappe.get_list` does this
by itself. A raw read asks `church_scope.is_people_directory_private()`, as the Check-In Station
does. A count is the opposite case: Frappe's own count totals every church. A Number Card or
Dashboard Chart over `Person` or `Family` must be Custom and count only the reader's churches. A
card calls `churchit.dashboard.count_people` or `count_families`, or `count_people_in_list` for a
saved Person list. A chart source scopes its query with `scoped` or `church_query_filters`, as the
Life Events and People Added sources do.

## Reading data: the rule that matters most

| API                      | Applies the reader's church?    |
| ------------------------ | ------------------------------- |
| `frappe.get_list`        | **yes**, Frappe does it for you, shared records included |
| `frappe.get_all`         | **no**                          |
| `frappe.db.count`        | **no**                          |
| `frappe.qb` / raw SQL    | **no**                          |
| A child table            | only through `get_list` with `parent_doctype` |

`frappe.get_all` looking permission-aware is the single most common mistake in this codebase; it is
`get_list` with permissions turned off. Prefer `get_list` for anything a user will see. When you
need the others, scope them yourself with `churchit/church_scope.py`:

```python
from churchit.church_scope import church_filters, church_query_filters, scoped

scoped(query, Person, filters)              # query builder, for the churches the reader may see
frappe.get_all("Person", filters=church_query_filters(filters))   # same, as a filters dict
frappe.get_all("Fund", filters=church_filters(church, allow_giving=1))  # one known church
```

The first two answer "what may this reader see", so they belong in reports and desk code. The third
answers "what belongs to this church", so it belongs on public pages and anywhere the church comes
from the record rather than the reader. All three admit shared records, so use them rather than
writing `church == x` by hand, which would silently drop everything shared.

A child table carries no church of its own. `frappe.get_list` reads one only with `parent_doctype`:
it joins the parent and applies the parent's permissions, church included. Every other API applies
nothing, so scope the parent and join to it, the way the Life Events chart source joins
`Life Event` to `Person`.

`churchit/tests/test_church_scope_hygiene.py` fails on a `frappe.get_all`, `frappe.db.count` or
`frappe.qb.DocType` call that names a scoped doctype as a literal, unless the function holding it
calls a `church_scope` helper. It skips reports, patches, setup and tests. It does not see a doctype
held in a variable, `frappe.db.get_value`, `frappe.db.exists`, `frappe.get_doc`, `frappe.qb.from_`
or raw SQL, so scope those yourself. If a particular read genuinely cannot cross churches, say so
where it happens:

```python
# church-scope: a shared room has one diary for every church, so a clash is found across all of them
conflicts = frappe.qb.from_(Booking).where(Booking.room == self.room)
```

The reason is required and lives in the function holding the read, so review sees it and the next
read in the same file still has to justify itself.

## Whitelisted endpoints: the desk is not a rule

A link field's dropdown filters by church and its pre-save check refuses a name typed in by hand, so
the desk looks safe. But a whitelisted function that takes a name is called directly by anyone with
a login, and `PRSN-.####` names are a counter anyone can walk.

- A **document method** (`self`) is not safe on its own. `run_doc_method` checks only **read**, and
  called with `docs` it checks the copy the browser sent, whose `church`, `owner` and `user` the
  caller fills in. Before a method writes, sends, or reads anything beyond the document, it checks
  the stored record: `self.reload()` (or `load_from_db()`) and then `self.check_permission(...)`, as
  `ChurchEmail.load_saved` does, or `frappe.get_doc(self.doctype, self.name).check_permission(...)`.
  A method the form calls without saving first, such as on refresh, loads the stored record into a
  separate document (`Budget.get_progress`), because Frappe sends `self` back to the form and a
  reloaded `self` would overwrite unsaved edits. `tests/test_doc_method_hygiene.py` fails on a write
  before such a check.
- A whitelisted function or document method that changes data takes `methods=["POST"]`. Frappe
  never checks the CSRF token on a GET, and the session cookie still travels with a GET that another
  site starts. `tests/test_http_method_hygiene.py` fails on one that takes GET; one that must take
  GET (a signed email link, a guest read API) goes in its `GET_BY_DESIGN` with the reason.
- A function that only reads takes `methods=["GET"]`, and every caller sends GET
  (`frappe.xcall(method, args, "GET")`, `frappe.call({type: "GET"})`). Under MCP a GET method runs
  with read permission and a rollback. A read that a script under `public/js` calls takes
  `["GET", "POST"]` for one release, because browsers keep that script for 12 hours. The same test
  fails on a function that takes every verb or GET and POST without a listed reason.
- The first docstring line of a whitelisted function ends with "Reads only.", "Changes data." or
  "Sends messages.", every parameter has a type hint, and a read has a return annotation. MCP
  discovery shows only that first line. `tests/test_agent_docs_hygiene.py` enforces it.
- A **has_permission hook sees the edited document.** A save checks write on the document after the
  caller's changes, and REST `PUT` returns the saved document. When a hook decides access from a
  field the caller can change (a category, a visibility), `validate` checks the stored document from
  `get_doc_before_save()` too. (`owner` and `creation` are set-once in Frappe.) User Permissions are
  no different: Frappe measures the `church` the caller sent, so
  `church_scope.refuse_changing_another_churches_record` refuses a save (from `ensure_church`), a
  cancel or an update after submit when the user cannot see the church stored on the record.
- A **module-level function taking a name** is not checked at all. `frappe.get_doc`,
  `frappe.db.get_value` and `frappe.qb` check nothing. Add the check yourself, against the record
  the caller named:

```python
frappe.has_permission("Function", doc=function, throw=True)   # before reading anything about it
frappe.get_doc("Group", group).check_permission("read")        # when you need the document anyway
```

Do not reason from "this is keyed to one function, and a function belongs to one church". That says
the *data* cannot cross churches; it says nothing about whether this caller may see that function.
"Templates are shared on purpose" is the same trap: it justifies reading a template, not reading any
function whose name the caller supplies. So `apply_template` takes a source the reader cannot read
only when a Function Type names it as its template.

Watch for three things that switch the checks off:

- **A plain Link to a scoped doctype.** Frappe applies user permissions to `Church`, not to `Person`,
  so a `person` field is never measured against whose member it is. Check the linked record's church
  yourself, as `MemberTransfer.validate_both_churches_are_mine` does.
- **`ignore_user_permissions: 1`** on a Link exempts that field from the only check Frappe would make.
  It is right on `shared_by_church`, on tree parents and on the directory's `church` fields, and
  suspicious anywhere else.
- **`ignore_permissions=True`** on a write reached from a whitelisted call. It skips the check that
  refuses the same edit made on the form.

## Adding a doctype

Give a doctype, report or other shipped record a name that no other Frappe app is likely to use.
Frappe keeps one record of each name, so an ERPNext `Budget` would take over a Churchit `Budget`. Put
"Church" before a common word, as in `Church Asset`, `Church Budget`, `Church Location` and
`Church Task`. `church_setup/app_clashes.py` refuses to install an app that ships a record of the same
name, and `test_app_clashes` checks ERPNext and Frappe Learning when they are on the bench.

Every doctype that stores records must either carry a church or be declared global; the hygiene test
fails until one is true. Child tables and Singles are exempt automatically.

Scoped doctype: add this field near the top of the form, after the title field.

```json
{ "fieldname": "church", "fieldtype": "Link", "options": "Church", "label": "Church",
  "hidden": 1, "in_standard_filter": 0 }
```

Leave it `hidden`, and keep it out of any hidden tab, section or column. `Church Features` creates
site-local Property Setters that reveal it when multi-church is on, so single-church sites never see
it. These setters are deliberately not fixtures, so never export them. A setter reveals the field,
not the tab, section or column around it (`test_desk_ui_hygiene` checks this).
`church_scope.ensure_church` (a wildcard `validate` hook) fills the field on save and refuses the
save if it cannot.

Give it this `depends_on` as well, and the shareable form of it when the doctype can be shared:

```json
"depends_on": "eval:!(frappe.boot.churchit && frappe.boot.churchit.single_church)"
```

A user who can see one church never needs to pick it. Decide that in `depends_on`, which the form
layout resolves while it renders, and never by calling `frm.toggle_display` on `refresh`: that paints
the field first and then hides it, which reads as a flicker on every form load.

When the record hangs off another scoped record, derive it instead of defaulting it, so it cannot
drift: add `"fetch_from": "<link_field>.church"` and `"read_only": 1`. A sign-up takes its
function's church; a care request takes its person's.

Global doctype: add it to `GLOBAL_DOCTYPES` in the hygiene test with its reason. The existing
entries are lookup and type tables, shared reference data such as Bible Translation, records that
belong to a person rather than a church, the Church tree itself, and the virtual import targets. A
virtual doctype is not exempt, so a new import source goes in the import group.

### Records a church can share

Between the two lies a third bucket: a doctype in `SHAREABLE_DOCTYPES` (`churchit/church_scope.py`)
is scoped as usual, but each record may be handed to every church with a **Shared with all churches**
checkbox. Today that is the reusable content (question sets among it), the supplier directory, the
places and equipment that congregations share, the occasions they hold together (Function, Meeting
Minutes), and the two containers money runs through (Fund, Ministry).

**A container may be shared; money never is.** Every Collection, Expense, Online Donation and Fund
Transfer keeps the church that gave, spent or moved it, so per-church figures come from those rows at
read time. A money record never takes the empty church of a shared container
(`FundTransfer.set_church_when_the_source_is_shared`), and moves money only out of a fund of the
user's church or a shared one (`refuse_another_churches_parent` on `from_fund`). What a shared container holds is the joint
pot, and a stored total on it has to be the joint truth rather than one reader's share:
`Fund.balance` is the joint balance, `Ministry.total_expenses` the combined spending,
`Function.attendance_total` the one head count of one joint service. Say the consequence out loud
when you add a doctype here, because it is the owning church's decision to publish that figure:
sharing a fund publishes its balance and its ledger to every church.

**A record may not use another church's money.** A church-owned record that names a Fund or another
church-owned record, directly or through a global record such as Expense Type, calls
`church_scope.refuse_another_churches_record(doc, doctype, name)` in its own `validate`, as Expense,
Collection, Online Donation, Fund Transfer and Ministry Team Assignment do. The guard compares
churches rather than permissions, because the writes that most need it run with
`ignore_permissions`. The fix for the church that trips over it is to share the fund.

Call the guard from the controller's `validate`, as every caller does. `ensure_church` is a wildcard
`doc_events` hook, which Frappe runs after the controller and after the doctype's own hooks, so
`church` may still be empty in either place. The guard resolves the church itself, and any other
`validate` check that needs the church must do the same.

Listing a doctype only offers the checkbox, and `is_shared` defaults to 0, so nothing is shared
until someone ticks it. Belief is the exception: its box defaults to ticked, so a new Belief is
shared unless someone unticks it. Give a newly listed doctype a default of 0. Model sync gives every
existing row the column's default, and a ticked row is shared on its next save. Leave `is_shared`
out of `in_list_view` and `in_standard_filter`, because a single-church list would show an empty
column (`test_desk_ui_hygiene` checks this). On a multi-church site, Church Features reveals the
field and its filter, but not a list column.

A shared record stores the **empty string** in `church`, which Frappe's permission clause reads as
"every church", so the read side costs nothing. That holds while System Settings' Apply Strict User
Permissions is off, which is Frappe's default. Churchit does not check it: with it on, lists and
forms hide shared records from every user who holds a Church permission, but the `church_scope`
helpers still admit them. Three rules follow, and breaking any of them is how this gets confusing:

- **An empty church is the empty string, not NULL.** Frappe's permission clause reads both as
  shared, but `church == SHARED` only matches the empty string, so a NULL does not pass sharing on
  to records that derive their church. `multi_church.normalise_shared_church` settles this on the
  transition.
- **An empty church always means shared, never "not filled in yet".** `church` carries a
  `depends_on` so it vanishes when the box is ticked, and the desk prefills it on new documents
  (`church.prefill_church`). Keep both if you add a shareable doctype.
- **A shareable doctype keeps the church that shared it in `shared_by_church`**, revealed alongside
  the checkbox so a record shared by the main church does not look like one the branch shared
  itself. The form notes it and locks the checkbox, from `frappe.boot.churchit.churches`
  (`church.note_shared_by_another_church`). Unticking the box returns the record to that church
  rather than to whoever saved it. Without the field, the guard below skips the doctype.

**Only the church in `shared_by_church` may take a shared record away from the rest.** Unticking the
box and deleting the record are the same loss through different doors, so both go through
`only_the_sharing_church_may`. A shared record is writable by every church, so without the guard
any branch could pull a resource out of the whole organization. Administrator is nobody's church and
bypasses it. A user holding no Church permission does not, because holding none means unrestricted
*reading*, not ownership of what other churches shared. The guard steps aside for
`ignore_permissions` saves, so patches and jobs are unaffected. There is no per-recipient opt-out: a
branch that wants something gone asks the owner.

Sharing is not hierarchical: a branch may share upward and sideways, not only the main church
downward.

A record that derives its church with `fetch_from` inherits sharing. A booking of a shared room is
itself shared, so every church sees that the room is taken, with `shared_by_church` recording who
booked it. `church_scope.inherits_a_shared_church` keeps `ensure_church` from stamping its own
default over an inherited blank. When the source stops being shared, `restamp_dependents` stamps
those records back to its church.

A Room is named `ROOM-.####`, so code that shows a room to a person reads `room_name`.
`Room.refuse_a_second_room_with_this_name` keeps `room_name` unique among the rooms one church
lists: its own and the shared ones. A shared room's name is compared with every room. A clash read
of a room or of equipment crosses churches on purpose (see "Room bookings").

Two shapes that are neither, and how they are handled today:

- **Family** follows its primary contact's church (`Family.follow_primary_contacts_church`),
  because a household can span branches. The directory therefore lists a family under every branch
  that has one of its members, rather than filtering on the family's own church. Frappe checks the
  family before it takes that church, so `Family.refuse_another_churches_primary_contact` refuses a
  primary contact whose church the user cannot see, except on `ignore_permissions` saves.
- **Function Type** templates are shared configuration, so `template_function` carries
  `ignore_user_permissions`, and `apply_template` takes such a template even when the reader cannot
  read it (see "Whitelisted endpoints").

Budgets are the one aggregate anchored to a record's church rather than the reader's scope. A budget
counts its own church, and counts the churches beneath it only when **Include Branch Churches** is
ticked, which is how a main church budgets for the whole organisation without forcing that on every
budget it owns. That is also why Budget is not shareable: a shared budget would have no church to
anchor to and would show organisation-wide spending to everyone. On a multi-church site a budget's
name holds its church's abbreviation (`BUDGET MC 2026-01-01 to 2026-12-31`), so two churches can
budget the same dates. Frappe names a record before `ensure_church` runs on `validate`, so
`ChurchBudget.autoname` fills the church first in the same way. A budget made on a single-church
site keeps `BUDGET 2026-01-01 to 2026-12-31`, even when a user's default church fills its hidden
church field. A budget made before this naming keeps its old name, and a church can change its
abbreviation, so never read the church or the dates out of a budget name: use its fields.

## Adding a report, chart or number card

Reports run raw and bypass permissions entirely; `query_report.run` only checks the role-level
report permission.

- Server, and this is the one that matters: pass `filters` through to the query and wrap it in
  `scoped(query, Table, filters)`. Scope the table that owns `church`; for a child table, scope its
  parent. Forget this and the report shows every church's rows to everyone.
- Client: spread the shared filter into the report's own: `filters: [...church.report_filters(), ...]`.
  This is the picker, not the guard. A report without it is still scoped, because the server falls
  back to the reader's own churches; the reader simply cannot narrow to one branch.

`tests/test_reports_hygiene.py` checks both, by text in each report module, with separate messages so
you can tell a leak from a missing picker. It does not see a `frappe.get_doc` or a read in a helper
module. A report that takes a record name in its filters checks that record itself
(`frappe.has_permission(<doctype>, doc=name, throw=True)`), as Budget vs Actual does.

Charts and number cards of type **Document Type** go through `get_list` and apply the reader's
churches, except over `Person` and `Family`, which total every church while the directory is shared
(see "The one invariant"). A Heatmap chart reads with `get_all` and is never scoped. **Custom**
sources and methods are not scoped either: scope them by hand, as `churchit/dashboard.py` and the
Life Events chart source do.

A **Custom** chart or card method is whitelisted, so any signed-in user can call it, portal
members included. Start it with `frappe.has_permission(<doctype>, "report", throw=True)`: staff
roles hold the report right, and without a document Frappe does not count Church User's `if_owner`
one. On Prayer Request, Church Prayer Team passes this check too, so a card there also applies
Visibility (`church_prayers/prayer_access.py`). Give a Custom chart a `document_type` as well.
Frappe shows a chart with neither roles nor a doctype to System Managers only.

A report, card or page that lists people to celebrate, contact or check in must leave out the
people who have died. `membership.living_people_filter(Person)` is the one rule: use it in
`frappe.qb`, or as an item of a `get_list` filters list. For a couple, apply it to the spouse too,
through a left join on `Person` as `spouse`.

Attendance counts only the types in `church_ministries/attendance.COUNTED_TYPES`, and only on a
Function whose start date is today or earlier. Take both from there, and a total from
`attendance.get_total`; `test_reports_hygiene` fails on a second copy of the types.

`Function.attendance_total` is written only through `attendance.get_attendance_total`
(`Function.before_save`, the daily `refresh_started_totals`, `set_headcount`): the larger of the
Function's `headcount` and the counted rows, and 0 until the Function starts.

Write a person's attendance row only through `attendance.record(person, function, status)` and
`attendance.remove(person, function, status)`. They load the Function with `for_update` and save it
whole, so two check-ins at once lose no row and a stale desk save fails. `record` never lowers a type
(`STATUS_RANK`). A `Function.validate` check acts only when `has_value_changed` on its own field, or an
attendance save trips it.

Weekly Metrics rows are written only by `church_summary/metrics.py`, by the daily
`record_recent_weeks` and the Church Manager backfill. Attendance, first-time visitors and giving are
counted again from dated records on each run; active members, people in groups and people serving
are the state on the day, so only the current week gets them. A shared Function counts once, for the
church in `shared_by_church`. Giving stays at permlevel 2, and the Giving by Week chart has the
roles Church Finance and Church Manager.

Recurring Functions are made in `church_ministries/recurrence.py`. Deleting an occurrence adds its
date to the template's Skip Dates (`Function.on_trash`), so the daily job does not make it again.

A group meeting is a Function with `group` set, and the group's schedule is the `auto_repeat`
Function with that group. `group` is the only link from a Function to a Group: `Function.validate`
refuses a new Group association row, a group of another church and a shared Function with a group. A
schedule takes no attendance rows, because `apply_template` copies them to each occurrence. A
leader's attendance goes through `attendance.record` (`group_meetings.record_group_attendance`),
which also sets `did_not_meet` and `attendance_recorded_on`. `Group.meets` is display only:
`group_meetings.get_meets` writes it from the schedule on load and on save, so do not add schedule
fields to Group. Group attendance figures leave out `did_not_meet` meetings and schedules, and count
only `COUNTED_TYPES` on past meetings.

Birthdays and ages come from the Person fields, never from Life Event rows. `birth_month` and
`birth_day` are set from the Birth event even when its year is unknown (0 when there is no
birthday). `birth_date` needs a known year. `age` needs one too and, for someone who died, a known
death date. The age column stores 0 for an unknown age, so test `derived.has_known_age(Person)`, not
the age. For a window of days use `celebrations.get_birthday_rows`; for this week use
`query.month_day_this_week(Person.birth_month, Person.birth_day)`, since a week across the new year
needs (month, day) pairs rather than a range.

## Roles

Church User is the **portal member** role, with no desk access. Staff hold desk roles, bundled
into Role Profiles in `fixtures/role_profile.json`:

| Role | Owns |
| --- | --- |
| Church Staff | Reads people, events, groups, ministries and the lookup types. Changes only records it created, except Church Task: it edits any task but adds none. The Church Staff, Church Office, Church Care Team and Church Treasurer profiles hold it. |
| Church People Editor | Person, Family, Group, Member Transfer, Function Sign-Up (and approves sign-ups), Form Response and Inactive Reason. Adds and edits Person Notes and Follow-up Cards, edits and deletes Connection Cards, and records Communication Consent. Marks a Possible Duplicate Not a Duplicate, but cannot merge, because a merge deletes a Person. |
| Church Pastoral Care | Care, counseling, visitation, background checks, prayer, alms. Adds and edits Person Notes and Follow-up Cards, records Communication Consent, and reads the care figures on Person (permlevel 3). |
| Church Finance | Collections, online donations, the payments and refunds of sign-ups and form responses, expenses, funds and transfers, budgets, statements, vendors, and their types. Edits Alms Requests and reads the giving figures on Person (permlevel 2). |
| Church Check-In | The Check-In Station. Reads people, families and functions. |
| Church Follow-up | The Follow-up Cards assigned to it (`followup.has_card_permission`). Reads connection cards and follow-up workflows. |
| Church Manager | Everything, including settings |

Church Prayer Team has no desk access and is in no profile. Give it on its own to a member or staff
user who prays for the requests: it reads Prayer Team and Whole Church requests.

Church AI User has no desk access, no DocPerms and is in no profile, so it gives a member nothing.
It gates one thing: who may sign in an AI app and use Frappe's MCP server (see "AI"). A System
Manager gives it on the User record, in addition to the person's other roles, to someone they trust
to send what they can read to an AI company. Church Manager and System Manager need no extra role.
Removing it closes MCP to the person at once, but an app already connected keeps its token for the
REST API: also delete the person's tokens in OAuth Bearer Token.

Church Check-In Kiosk has no desk access, no DocPerms and is in no profile. Give it alone to the
User of a self check-in kiosk, with exactly one Church User Permission (the kiosk refuses otherwise)
and Restrict IP. `church_ministries/kiosk.py` reads past permissions for it and sends only the
names, photos and grades of one whole phone number's household, and the Functions it may check in
to. `accounts.link_portal_user` adds no Person for a kiosk login.

A new doctype gives its rights to Church Manager and to the role that owns its area, and read to
Church Staff if staff look it up. Church Check-In and Church Follow-up do not hold Church Staff, so
give them read on what their forms link to. `tests/test_role_hygiene.py` fails when a profile can
fill in a form but cannot pick what one of its Link fields points at. Reports and workspaces carry
the same roles.

A portal member reaches their own records through `if_owner` DocPerms, and their own Person
through `church_people/member_access.py`. That module also limits their Person edits to the
Personal Details form's fields, and a prayer or alms recipient to their own church. A member form
must not link to Person (see the web form bullet in "Frappe behaviours worth knowing");
`tests/test_portal_members.py` checks this.

Rights on a Frappe doctype, such as Church Manager on Data Import or Role Profile, live in that
doctype's `church_customizations/custom/<doctype>.json` under `custom_perms`. A Custom DocPerm
replaces the doctype's standard permissions, and migrate replaces every Custom DocPerm of that
doctype with the file's rows, so the file lists System Manager's rows too. Church Manager's Data
Import rights are `if_owner`: a Data Import has no church, and its file holds every row.

Address is the exception, because ERPNext adds its own Address rule (read for Accounts Manager) and
a file's rows would delete it. `custom/address.json` holds no rows. Instead
`after_install.let_church_roles_read_addresses` and a v1_0 patch add read for Church Manager,
Church Staff and Church People Editor with `frappe.permissions.add_permission`, as ERPNext does,
which keeps every other rule and any rule the site already has for the role. These roles read
every address, so the Map of Addresses and the addresses of people show. Frappe's own rule lets
other roles read only the addresses they added. An address has no church and is titled with the
household or person name, so the staff of every church read it, also when Keep People and
Families Private to Each Church is ticked (`church_customizations/test_address_customization.py`).

## Notifications

`Notification` is overridden by `churchit/church_communications/scoped_notification.py`. Recipients
resolved from a **role** are dropped when their church permission excludes the document's church,
covering email, the desk bell and SMS, for records your users create too.

Recipients resolved from a document field are inherently fine. If you add a notification on a
doctype with no church field there is nothing to filter by, so every role recipient receives it.
Consent filters recipients too, on churchit's and Frappe's doctypes
(`scoped_notification.is_under_church_consent`), so another app's Notifications, such as an ERPNext
invoice, still reach church members (see "Church Emails, consent and bounces").

A shipped Notification with a `condition` sets `"condition_type": "Python"` in its JSON. Migrate
syncs it without field defaults, and Frappe ignores a condition whose type is empty
(`tests/test_notification_templates.py` checks this).

Production cannot enable a shipped Notification. A Notification that must work there, or that a
church may change, is inserted once as a record that is not standard, from `after_install` and a
v1_0 patch, as `room_booking.create_decided_notification` does for Room Booking Decided. To tell
staff that a record waits for them, assign it with `frappe.desk.form.assign_to`: the assignment
sends its own email, so add no second Notification.

New Prayer Request for the Prayer Team, Approved Prayer Request for the Prayer Team, New Private
Prayer Request (`prayer_request.create_new_prayer_request_notifications`), New Alms Request
(`alms_request.create_new_alms_request_notification`) and Church Task Due
(`church_task.create_due_notification`) are inserted the same way. A patch that adds a new one to
existing sites inserts only that one (`create_new_prayer_request_notifications(names=...)`), so a
Notification a church deleted stays deleted. The Church Prayer Team recipient
row has the condition `doc.approved_for_list`. Approved Prayer Request for the Prayer Team (Value
Change on `approved_for_list`, not Private) tells the team when staff approve a request later.
Frappe does not run Value Change on insert, so a request approved at creation sends one email. A
Private request goes to Church Pastoral Care and Church Manager only, and its email leaves out the
request, the title and the requester. Escape free text with `| e` in a Notification body: Frappe's
Jinja does not escape, and guests write prayer requests.

## Public website and portal

`get_church()` resolves which church a page is about: an explicit `?church=` (published churches
only), else the signed-in member's church, else the root. An unknown value falls back to the root
rather than raising, because the navbar and footer resolve it on every page including error pages.

A church's own identity comes before the site-wide Singles: `Church.about` and `mission_statement`
drive the About Us page, and `church_contact_details()` prefers `Church.phone`/`email` over
`Contact Us Settings`, which holds one number for the whole site. A printed letterhead takes the
church of the document being printed, through `get_letterhead_church(doc)`.

Scope page data with `selected_church_filters(...)`, a Jinja method, so a Web Page template, the
shipped ones and a church's own, is one call away from being scoped. Python that already knows the
church keeps passing it: `church_filters(selected_church_name(), ...)`.

Shipped Web Pages are records, so a site keeps whatever it was installed with; the hygiene test
cannot see into the database. Changing one of these templates means a patch that rewrites the
queries in place, the way `patches/v1_0/scope_website_pages_to_church.py` does, rather than
replacing a page a church has edited.

A published Web Page is resolved ahead of a `www/` page on the same route (`DocumentPage` runs
before `TemplatePage`), so moving a page into `www/` means unpublishing the record it replaces.

`site_church.js` carries `?church=` onto the page's links, and Frappe's `can_cache` skips any
request with a query string, so a selected branch is never served from the shared page cache. A
cookie would be invisible to that cache; do not swap the parameter for one.

Frappe caches rendered pages by path alone, shared between guests and users, so
`church_website.context.before_request` disables the cache for signed-in visitors in multi-church
mode and while a members-only Web Page exists, because the menu then differs per visitor. It skips
`/api/` requests, which read no page cache. Do not remove that without replacing it.

Some portal surfaces read past document permissions by design and apply the member's church by
hand: the community prayer request list (`get_community_filters`), the Join a public group picker
(`group_api.joinable_public_groups`), `/directory`, the Function Sign-Up form's function options and
the recipient search (`search_church_recipient`). A new one must do the same.

The group leader surfaces read past permissions too, but gate on leadership, not on the church: a
portal leader holds no DocPerm on Group or Function. `/group-leader`,
`group_meetings.get_group_meetings`, `record_group_attendance` and `group_api.message_group` call
`group_leaders.require_leader(group)`, and `decide_join_request` calls it unless the user may write
the Group. `group_meetings.get_roster` is the one answer to who a leader sees and messages: the
group's living members. `/find-a-group` lists the selected church's open groups and shows only the
city and a pin rounded to 2 decimals from each group's schedule Function. It never reads `meets` or
the street. A member's own requests come from `joinable_public_groups`, so the public page reads no
Group Join Request.

`/register` is the guest sign-up page (`no_cache = 1`). It lists the selected church's published
Functions from today on with Allow Guest Sign-Ups that are inside their sign-up window
(`register.get_open_functions`, `frappe.get_all` with `church_filters`), and every `/register`
endpoint asks it first. `register.sign_up` is a rate-limited guest POST with a honeypot; it takes no
person, status, price or amount from the browser. Other units extend the page only through
`get_attendee_rows`, `get_answer_rows`, `get_calendar_link`, `get_payment_link` and the includes in
`templates/includes/register/`, which add named inputs (a JSON value goes in a hidden input). The
household and the selections come from the guest GET `get_attendee_choices` after the page loads,
so the page HTML holds no name; `get_attendee_rows` rebuilds the household from the session and
refuses any other Person. The questions come from `get_questions`, and the page sends the answers as
one JSON object by attendee (`""` is the registrant, another key is an attendee's person or typed
name). The insert passes `set_child_names=False`, because Frappe renames every child row on insert
and the answers name their attendee rows.

A guest endpoint behind a public page declares no `church` parameter. `churchit.with_church`
(`site_church.js`) sends the page's `?church=` with the call, and the endpoint reads it through
`selected_church_name()`, which accepts only a published church. A signed link is the exception:
`newsletter.unsubscribe` takes `church`, and Frappe's `verify_request` checks the signature.

Calendar feeds are built in `churchit/ics.py`: `make_event`, `make_calendar` (folds every line) and
`calendar_response` (ETag and 304). Stamp each event with the `modified` of the records it shows,
never the time of the request, or the ETag changes on every GET. Do not add a second feed mechanism.

`/calendar` offers Subscribe (`webcal://`) and Download .ics links to
`churchit.ics.get_public_calendar?church=<selected church>` (`calendar.get_context`). The team
feed and the sign-up calendar file also pass the meeting link to `make_event`.

`/calendar`, its feed, the home page and the `/register` list leave out a Function with Link Only
(`is_link_only=0` beside `church_filters`). The guest GET `churchit.www.calendar.get_event` opens
one Function by name for a `?event=` link, a link-only one too, but only a published Function whose
church is published or blank. Function names are a counter, so Link Only hides nothing from a person
who guesses. `get_events` takes `include_branches`, which adds the published churches below the
selected one (`get_published_branches` reads the tree by `lft` and `rgt`: `get_descendants_of` with
`ignore_permissions` counts as a write in the HTTP method hygiene test, and without it a guest
cannot read the tree).

An event lists the rooms of its Approved bookings (`calendar.get_rooms`). In multi-church mode it
leaves out a booking whose church is set and is not the Function's church. A Function's
`meeting_url` must be https and hold no space or line break (`Function.validate_meeting_url`),
because a URL field accepts `javascript:` and feeds write the link as it is. The page shows it only
when it starts with `https://`, and `make_event` writes it as the event `URL` only when it holds no
line break.

Every field a page shows carries a badge on its desk form, worked out by scanning the pages
themselves (`church_website/published_fields.py`). Nothing is declared by hand: a new www page,
published Web Page, Web Form or guest endpoint is picked up, and so are the helpers, jinja methods
and included templates it calls. The scan finds a read by the doctype it names as a string, so pass
doctypes to `frappe.get_all` and similar calls as literals. A Function's schedule row shows the
title of whatever record it links to, so `schedule_item_entries` badges the title field of each
doctype that a schedule row names, as members-only. It also counts an import path such as
`churchit.church_people.membership` as a read of the field `membership`, so a badge can name a
field the page does not show.

Each source is public, members-only or for link holders (`PUBLIC`, `MEMBERS`, `LINK_HOLDERS`). A
web form with `login_required`, or a page that sends every guest to the login screen, is
members-only. A web form with only `key_required` is for whoever holds the emailed link. So a
portal-only field is not announced as public.

Two things defeat the scan: reading records with `frappe.qb` or `frappe.db.sql`, and giving a
doctype a web view, which renders from a template no source reads. A test fails on a web view, and
on `frappe.qb` or `frappe.db.sql` in a source's own code, but not in a helper it calls. Extend
`code_sources()` before adding either.

The scan counts any `record.fieldname` attribute in a page's code, so a page that reads a field
whose name is also a private field of a published doctype reads it with `.get()` (the sermon
presentation reads slide notes this way).

The sermon presentation shows a Song row with no fields picked as the Song's own slides, then a
last slide with its copyright and CCLI numbers. A viewer without Song read sees only a
`public_domain` song (`get_public_slide`), and no title of any other song. A guest never gets a
`/private/` background image. The license number is the sermon's church's, or the viewer's church
(`default_church()`) when the sermon stores no church and for `?song=`, which needs Song read.

The scan does not follow a method of a Single or its `self.` reads. A page that shows a field
through such a method imports the class as the type of its document
(`settings: GivingSettings = frappe.get_cached_doc("Giving Settings")`), and the method reads the
field as an attribute of a row (`wording.other_ways_to_give`), as `/give` does.

`/sermon/<name>` (`www/sermon.py`, through `website_route_rules`) shows one published Sermon to
anyone with the link, and 404 when the sermon's church is set and not published. It does not narrow
to the selected church, so a shared link opens from any branch page, and it has no staff preview.
Jinja has no autoescape there: escape every plain value with `| e`, and pass Text Editor HTML
through `sanitize_html(..., always_sanitize=True)`. The page shows no Sermon Presentation row,
because a presentation's notes are staff notes. A sermon with a Handout shows the handout in place
of its notes, so the bracketed answers stay off the page. Listener notes stay in the browser's
`localStorage`; add no field or method that sends them to the server.
`church_study/media.py:get_embed_url` is the one list of players a page may put in an iframe; any
other link, or one that is not https, gets a plain link. A sermon is renamed to its title, so
`Sermon.after_rename` adds a Website Route Redirect row in Website Settings from the old
`/sermon/<name>` to the new one, only while a Guest can open the sermon (`get_published_sermon`), so
a draft's new title never shows in a Location header. Under the same rule it retargets older rows
to the new name; a sermon a Guest cannot open leaves them on its last public name. It removes a row
whose source is the new name, so every old link takes one hop and none loops. It writes only the
redirect rows and clears the website cache; it does not save Website Settings. A
page whose route follows a record name uses the same Route Redirect rows; do not add a second
redirect store.

`/podcast.xml` (`www/podcast.py`) is the selected church's sermon podcast. It builds the XML with
`xml.etree.ElementTree`; never join record text into XML by hand. It lists a published Sermon when
its `audio_recording` File is public, else the newest Sermon Presentation row with a public
recording. `Sermon.on_update` makes every recording public while the sermon is published and
private otherwise, and writes the sermon's own `audio_recording` again after a move, because Frappe
writes a moved grid row file's URL into the parent field of the same name. The `/sermons` head links
the feed (`context._add_podcast_link`), and `podcast.get_feed_url` adds `?church=` in multi-church
mode.

`/live` plays the selected church's `live_stream_url`, or its nearest parent's (`inherited_value`),
in an iframe when `get_embed_url` knows the link, and redirects (302) to any other link; no link
gives 404. It sets `frappe.local.no_cache` first, so Frappe never stores that 404. The calendar
sends `live_url` (`calendar.get_live_url`) for a Function with Streamed from 15 minutes before it
starts until it ends, only when its church has a stream link. Do not add a second streamed flag on
Function. `utils.validate_https_url` is the one check for a link that guests open
(`Function.meeting_url`, `Sermon.media_url`, `Church.live_stream_url`).

`/bulletins` is members-only and lists the reader's own churches (`church_query_filters({})`), never
the `?church=` selection. `Bulletin.has_website_permission` also requires `has_church_access`, so the
PDF and the digital bulletin at `/bulletins?name=<bulletin>` refuse another church's bulletin. The
digital bulletin includes the print template, so a new bulletin section shows on the portal too.
`/announcements` is public and shows only `announcements` from the selected church's 5 newest
published bulletins with `share_announcements`. Bulletin has `make_attachments_public`, so its uploads
and pasted images are public files that members see on the digital bulletin without file access;
`Bulletin.validate_shared_announcements` refuses a link to a private file in shared announcements.

A Web Page with Members Only is served only to a signed-in active member (`is_directory_member`, the
`/directory` rule) or a user who can edit Web Pages, dynamic routes included. A guest goes to the
login page and anyone else gets 403. The check is the `MembersOnlyPage` renderer in
`church_website/pages.py`, which runs before Frappe's page cache. It matches an exact route in the
database, because Frappe finds a Web Page by route case and accent insensitively; never compare a
Web Page route in Python. `MembersOnlyWebPage` keeps such a page out of global search, and
`pages.get_list_data` (an override of `frappe.www.list.get_list_data`) keeps it out of the portal
list API for a non-member. `pages.get_hidden_pages` is the one list of pages whose links a visitor
must not see: switched-off pages, and members-only pages the visitor cannot open. The menu, footer,
sidebar and `/sitemap.xml` filter on it at render time. A link matches by lower case route, as a
site path or a full URL to this site, and a dynamic route matches from its fixed start
(`members/<name>` hides `/members` and every link under it). An accent variant is not matched; the
gate is still the renderer. Ticking or clearing Members Only clears the whole website cache
(`MembersOnlyWebPage.on_update`), because every cached page holds the menu. `/portal?doctype=Web
Page` lists nothing, because `www/portal.html` shadows Frappe's portal page and has no `portal.py`;
do not add one. The template still draws Frappe's list for another app's list route (ERPNext's
`/orders`), which runs Frappe's own `portal.py`. Its `no_cache` front matter keeps the landing out of
the page cache, which those routes read under the `portal` key; do not remove it. A new way to read
Web Pages without permission checks must apply the same rule.

A new shipped public page (a www page, a shipped Web Page or a web form) gets a `SHIPPED_PAGES`
entry in `church_website/pages.py`, with its label and its owning `enable_*` field (None when no
module owns it). Every migrate adds its switch to Church Features (`sync_page_switches`). Do not add
home, portal, manifest.json, sw.js, offline, app-start (the `AppStartPage` renderer, where the
installed app opens), preferences or a Frappe route. A switched-off page
answers 404 from the `SwitchedOffPage` renderer, its web form refuses Frappe's web form APIs
(`SwitchedOffWebForm`), and its navbar, footer, portal and sitemap links go at render time
(`get_hidden_pages`). `SwitchedOffPage` reads the request path, not `frappe.local.path`, which only
Frappe's own resolver sets (Frappe Builder's does not). Never change the cached Website Settings
rows: build new lists. A template that links to another shipped page asks `get_switched_off_pages()`
first, as `sermons.html` and `home.html` do.

## Settings a church can differ on

Three Singles hold site-wide configuration. Each takes per-church overrides through one resolution
point, so no caller threads a church around:

| Single | Override | Resolved by |
| ------ | -------- | ----------- |
| Giving Settings | a `church` column on each `Giving Gateway` row | `gateways_for(church)` |
| Giving Settings | `Church Giving Wording` rows | `get_thank_you_message`, `get_statement_acknowledgment`, `get_other_ways_to_give` |
| Check-In Settings | `Church Check In Printer` rows | `for_church(church)` |
| Bulletin Settings | `Church Bulletin Sections` rows | `for_church(church)` |

Two rules the shapes differ on, and both are forced rather than chosen:

- **A blank field means "inherit" only where blank is not also a value.** A gateway row
  with no church serves every church, and a printer row's empty host falls back. A
  `Check` cannot do this, because unticked and unset are the same value, so a Bulletin
  Sections row replaces the whole set and its fields carry the Single's own defaults.
  `Bulletin Settings.roles` is the one thing a row cannot override, since Frappe has no
  child table inside a child table. That list is only which job titles to print;
  `sections.position_holders` reads the people from the bulletin's own church, so a
  branch already prints its own pastor.
- **`for_church` never changes the Single.** `frappe.get_cached_doc` hands out one shared
  instance, so a church's row is applied to a copy. With no row for the church, it returns
  the Single itself, so treat the result as read-only.

The gateway override matters most: without it, a gift given on a branch's page goes through the
merchant account the main church set up.

Only the gateways in `giving_settings.SUPPORTED_GATEWAY_SETTINGS` (Stripe and PayPal) call back
`on_payment_authorized` with an Online Donation, so Giving Settings refuses any other and
`gateways_for` skips one stored before. `GivingSettings.get_gateway(church, payment_gateway)` gives
the row a payment uses: the one asked for when the church is offered it, else the church's default.

The payments app is optional (not in `required_apps`), and `payments.is_payments_on()` is its switch.
Without it `gateways_for` offers no row, so /give shows its unavailable notice, a sign-up is not
payable and `get_payment_url` refuses in `get_gateway` before it imports the app. Giving Settings
refuses Enable Online Giving without the app, and its form says why. Never import `payments` at
module level. A test that needs the app gets its gateway from `test_giving_settings.make_gateway`,
which skips the test without the app, and a doctype test module whose doctype links Payment Gateway
sets `IGNORE_TEST_RECORD_DEPENDENCIES = ["Payment Gateway"]`. The Docker image ships the app, and
installs it only when `.env` lists it in `EXTRA_APPS`.

## Giving and the fund ledger

Write Fund ledger rows only with `fund.add_transaction` and `fund.remove_transactions`. They lock
the Fund row, insert or delete only their own Financial Transaction rows by name, and set `balance`
and `goal_progress` with `frappe.db.set_value`, so a gift adds no Version and a stale desk form fails
as modified. Never append to `Fund.transactions` and save the Fund from code. A document that
touches two funds calls `add_transaction` in fund name order, so two writers cannot deadlock. Do
not take a locking read on Financial Transaction rows: its gap locks block writers on other Funds.
`Fund.before_save` keeps the same sum, so a desk save corrects a drifted balance.

A payable record gets its checkout URL from `church_finances/payments.get_payment_url`, which takes
only a gateway that `get_gateway` offers to the record's church. Its `on_payment_authorized(status)`
locks its row, records once when `payments.is_charge_confirmed` (the newest Completed Integration
Request has the amount and currency), and else calls `payments.notify_finance`, which alerts the
Church Finance users of the record's church. Churchit calls no vendor API and has no dispatch map.
An Online Donation compares `charged_amount`: the gift plus `fee_amount`, the fee the giver chose
to cover, which `start_donation` works out on the server from the gateway row
(`payments.get_fee_to_cover`). The covered fee is part of the gift everywhere: the Donation row,
`expected_total`, the receipt and the statement. Giving Settings refuses a fee percent of 100 or
more and a negative fee.

An Online Donation gets its `collection` only in `record_donation` (`refuse_a_changed_collection`).
When Finance sets or clears `person` on a recorded gift, `on_update` copies it to the Collection's
Donation row with the person's primary email, comments on the Collection and refreshes both
people's summaries after commit. Cancelling a Collection is the refund: `Collection.on_cancel` sets
each of its Paid Online Donations to Refunded before it removes the ledger rows, and
`record_charge` skips a Paid or Refunded gift, so a late callback records nothing. A partial
refund is a negative Donation row in a new Collection.

Function Sign-Up and Form Response are payable records too. Their payments go to `payment_church`:
the Function's or Question Set's church, or `shared_by_church` when it is shared. Its fund must be
that church's or a shared one (`church_scope.refuse_another_churches_fund`; do not use
`refuse_another_churches_record`, which reads a shared record's empty church as the editor's). A
registration fee or form payment is one Donation row with no person through
`collection.add_single_donation`, which `OnlineDonation.record_donation` uses too, so it is on no
Giving Statement. A sign-up's Pay now link is the signed GET `register.pay`; a form's is the POST
`form_response.pay`. A charge on a record already paid records nothing and alerts Finance. A sign-up
payment that arrives after its hold ended confirms only while seats are free, else it is Refund Due.
A paid sign-up that is cancelled or declined is Refund Due and alerts Finance, and only a
`PAYMENT_RECORDERS` user deletes a paid sign-up. A guest of a shared Function or Question Set is
matched and added as a Person at its `payment_church`.
Refunds are made at the processor; then Finance cancels the Collection or adds a negative row and
calls `record_refund`. `alert_unrecorded_gifts` also reports sign-ups and form responses that a
gateway charged and that are still unpaid.

Giving statements are tax receipts. `get_donations` and `get_givers` count only funds with
`is_tax_deductible`; a shared Fund has one flag for every church. A Payment Type with `is_non_cash`
marks donated property: `Collection.validate` refuses such a row with an amount or with no
`description`, so the ledger, the totals and every report stay cash only, and the statement prints
the description in place of an amount. Never add an estimated value. `emailed_on` is the only record
that a statement went: a rebuild that changes any line clears it, and a send that the queue drops (a
global unsubscribe) does not set it. `send_statement_emails` runs on the long queue, locks each
statement, sends to the person's primary email at that time and commits after each one.

Pledge Campaign owns its fund, dates and goal and is never shared; a Pledge takes its church from
its campaign. Pledge Progress counts only the Donation rows of the campaign church's submitted
Collections to the campaign fund, to the end of the last day. Never derive it from `Fund.balance`
or `Fund.goal_progress`, which an Expense changes. On the `pledge` web form every login pledges
only for its own Person (`Pledge.take_members_own_pledge`).

GL Account Mapping maps a Fund, Payment Type, Expense Type or Church to an account, once for each
church and record. The GL Journal takes each line's mapping from the source document's church,
refuses a document whose debits and credits differ, lists every missing mapping in one message,
and names a source document by its doctype and name only. Do not add a title or a person to the
memo: an Expense title can hold a person's name.

A Collection's title is its day and its Function's name, such as 2026-10-20 Sunday Worship
(`collection.get_title`, set in `before_save`). The day comes first so that a narrow list column
does not cut it. A stored title that holds a day writes it as ISO, here and in the Prayer and
Weekly Metrics titles, so it reads the same after a church changes its date format. An Online
Donation's title is `donor_name`: Remove Personal Data rewrites it and removes the Version rows of
the gift. A Fund Transfer is titled with the names of its funds,
'General to Building' (`fund_transfer.get_title`), and an Alms Request with its recipient's name
(`alms_request.get_recipient_name`), a stored copy that Remove Personal Data writes Anonymized over
like any copy of a full name. The Expense that Create Expense makes is titled with the request's
ID, such as 'Alms Request ALMS-0002' (`alms_request.get_expense_title`), because no Expense links to
the recipient, so Remove Personal Data could not find a name there.

## Integrations

A connector to another system uses Frappe's doctypes, hooks and APIs as they are designed, and stays
small. Do not build one that depends on another app's internals, calls an unstable vendor API
directly, or handles its own protocol or payment payloads: it breaks when the other side changes.

- **Use Frappe's settings doctype first:** SMS Settings, Payment Gateway, Email Account, OAuth
  Client, Geolocation Settings or Webhook. Sending a record to another system is a Webhook, not code.
- **A service with no Frappe home keeps its settings on a Single in the module that owns its data**:
  fields on that module's settings Single (People Settings holds the address lookup), or one
  `<Name> Settings` Single when the module has none. Keep secrets in Password fields.
- **Give each connector one switch, `is_<name>_on()`**, like `geocoding.is_address_lookup_on()`, and
  ask it before each call. Add no connector registry and no Church Features check.
- **An inbound endpoint refuses while the switch is off**, compares its secret with
  `hmac.compare_digest`, and sets a `rate_limit`. Follow "Whitelisted endpoints" for everything else.
- **An outbound call runs on the long queue, from the server**, never from the browser, and is safe
  to run again.

Web Push is a planned exception (Fit 3, High upkeep): it follows the Web Push protocol and the
browsers' push services, so keep it small. `church_communications/push.py` owns it. `subscribe` and
`unsubscribe` (POST, signed-in users) keep one Push Subscription per browser endpoint, and accept
only an endpoint of a push service in `PUSH_SERVICES`, because the server posts to it; a new
browser push service needs a line there. `subscribe` has a rate limit, and a user keeps at most
`MAX_BROWSERS` subscriptions (a new browser replaces the one used longest ago). A deleted or disabled
User loses its subscriptions (`delete_user_subscriptions`, User on_update and on_trash).
`send_push(user, title, body, url)` queues one `deliver` job per subscription on the short queue
after the commit, with a ttl of one day; `deliver` deletes a subscription on HTTP 404 or 410 and
logs any other refusal or a timeout once, with a short message only: the locals of a traceback hold
the endpoint, its keys and the signed header. pywebpush (2.5 or later, for
`WebPushException.status_code`) does the VAPID signing and the encryption, so write no crypto code.
The private key stays on the server: read it only with `get_password` in the job, and give a page
only `get_public_key()`. A user reads and deletes only
their own subscriptions (`has_subscription_permission`, `subscription_query_conditions`); System
Manager reads all. A notification's url is a path or a URL of this site, and the service worker
opens only a same-origin url. Ask `push.is_push_on()` before you offer or send push. A browser that
changes its push service, iOS rules (Home Screen apps only, iOS 16.4 or later) and pywebpush or
py_vapid upgrades can break it.

Staff chat is Raven, which a System Manager installs beside Churchit (Manual: Communications, Staff
Chat). Churchit's only Raven code is the Staff Chat link to `/raven` in the Communications sidebar:
`church_communications.staff_chat.extend_bootinfo` drops it when the Apps screen does not offer Raven
to the user (not installed, or Raven's own permission check refuses). Do not add a Raven hook or
Document Notification to a Churchit doctype. Raven does not follow church scoping, so the manual
gives Raven access by hand.

## The switch

`Church Features.enable_multi_church` is off by default and a single-church site must notice nothing.
Each off-to-on change stamps the root church on every scoped record that has no church and is not
shared. It gives each enabled user without a Church permission, except Administrator and Guest, a
root permission with branches hidden. The switch turns off only while no branch exists, so keep both
steps safe to repeat. Migrate never runs them, so a permission an administrator deleted stays
deleted.

A user with no Church permission sees every church, so a login made **after** the switch is scoped
too, by `church_access.scope_new_user` on User `after_insert`. It takes the church the request is
about: the branch whose page took a sign-up, or the church of whoever adds the user in the desk.
Linking a Person repoints a portal login's permission afterwards, so this is only the starting
point. A staff login that a user links by hand keeps its churches (`Person.sync_church_permission`);
a later change of the person's church and the app's own links (`ignore_permissions`) still move them.

## AI

An AI app that connects over Frappe's MCP server runs as its user, with that user's permissions. It opens no permission hole; it only lets the user act faster. So churchit does not guard doctypes, fields or Frappe methods against AI apps. It controls whether AI is on, who may connect an app, and it warns where people decide.

- **The switch:** AI is off until a Church Manager or System Manager turns on `Church AI Settings.enabled`. Call `switch.is_ai_on()` before you offer or run an AI feature, and `switch.require_ai(feature)` in an endpoint. While AI is off, `enable_mcp` is cleared (after install, after every migrate and when AI is turned off) and `refuse_mcp_while_ai_off` refuses to set it. Churchit never sets `enable_mcp` to 1. Read the switch with a default of off, because a hook can run before migrate adds the field. On a multi-church site only a Church Manager with no Church restriction (or a System Manager) turns AI on.
- **Who may connect an app:** Frappe lets a user sign in an OAuth app only when the user holds one of the app's Allowed Roles, and gives an app with none "Desk User", which every desk user holds. Dynamic client registration, which every MCP client uses, saves an app with none. `switch.limit_new_app_to_ai_roles` (doc_events OAuth Client before_insert) gives such an app `switch.AI_ROLES`: Church Manager, System Manager and Church AI User. An app made with roles keeps them, and churchit does not change existing apps: the exposure panel lists each app that every desk user may still sign in. Frappe's MCP server itself takes every desk user, by session, API key or any app's token, so `switch.refuse_mcp_to_other_users` (`auth_hooks`) refuses `/api/v2/mcp` to a signed-in user without one of `AI_ROLES`, at every request. A token outlives a removed role (Frappe checks Allowed Roles only at sign-in, not at refresh) and still reaches the REST API. Only a System Manager creates API keys (Frappe's `generate_keys`), and a key gives its owner's access.
- **Warnings:** the Church AI Settings form, its acknowledgment, the exposure panel (`exposure.get_exposure`), the notice of a new connection, Manual: Foundations "AI and your church's data", the How We Use AI page, the README and `skills/churchit/` say what an AI app can see and do, that a hosted model sends what it reads to its company, and that text guests and members write can hold instructions for the AI. Change them together. On Church AI Settings, each warning is a collapsible Section Break titled "Warning: ..." with a one-line description and one HTML field `<name>_html` that `church_ai_settings.js` (`get_warnings`) fills. A new one goes in `ROUTINE_COLLAPSED`, and `test_church_ai_settings.TestWarningSections` checks its title, description and script. A section only for Flow gets `depends_on` on `frappe.boot.churchit.ai.flow` and goes in `FLOW_SECTIONS` of that test. A Flow sentence in another section goes in `only_with_flow`. Only the yellow summary in `intro_html` stays open.
- **Churchit's own AI features draft, a person saves:** a churchit AI feature returns a draft, a label says that AI wrote it, and a person saves it in the desk. This is a rule for churchit's code, not a guard around Frappe.
- **Reading:** read through `frappe.get_list` or `get_doc` plus `check_permission`, as the user. In AI code do not use `frappe.get_all`, `frappe.db.count`, `frappe.db.sql` or `frappe.qb`. Drop a masked key. Never send it as null or 0.
- **Untrusted text:** text that guests and members write is data. Never put it in an instruction, and never let it choose a method or a recipient.
- **Drafts:** `ai/drafts.py`. `propose(doctype, values, name=None)` (POST, rate limit 30 an hour per user) and `make_draft(..., source=None)` (for churchit's own features and Flow tools, with the label source) call `require_ai`, check the desk user and create (or write on the named record), keep only the fields the caller could set in the form, in form order, and list every other key in `dropped`: unknown keys, display, `read_only`, hidden and virtual fields, a permlevel without write, non-scalar values, Table fields of a missing child doctype and `SENDING_FIELDS`. `SENDING_FIELDS` holds the fields whose save sends (Church Email `status` and `send_after`, Ministry Team Assignment `status`, Follow-up Workflow `is_active`), found by reading each controller: add one with each new sending field. A save that sends with no field to drop, such as a new Function Sign-Up (its confirmation), is told in the manual. A submitted record takes only `allow_on_submit` fields, a cancelled one is refused, and a Single is an edit of its one record. A table row adds a row, or changes the row whose `name` it holds, and a draft never removes one. The draft lives in `frappe.cache` for 3600 s under `churchit:ai_draft:<user>:<token>`, outside Frappe's `user:` prefix because a sign-in clears that prefix; `persistent_cache_keys` in `hooks.py` keeps it through a full `clear_cache` (a migrate, a Church Features save). Nothing reaches the database. `get_draft(token)` (GET) gives it to its user only, with `stale` when `modified` changed since. `label_saved(doctype, name, token)` (POST) adds the Info Comment "Drafted with AI help (<source>)." once after the first save, and forgets the token; a forged or another user's token adds nothing, and a doctype with no timeline (`hide_toolbar`) gets none. The desk drops the query string on `/new`, so `public/js/ai_drafts.js` takes `ai_draft` when the script loads and on `frappe.router` change, then removes it from the URL. Never rename `get_draft` or `label_saved`: `app_include_js` is cached for 12 hours.
- **Agent guide:** `ai/guide.py` `get_agent_guide(topic=None)` (GET) gives `skills/churchit/SKILL.md`, or `reference/<stem>.md` for the stem of an existing file, read with `frappe.get_app_source_path`. MCP's `search_methods("church rules")` finds it first by its first docstring line: keep that line, and keep other whitelisted methods from sorting before it with both words (`test_guide` checks it). System Settings Agent Instructions belong to the site admin: `add_guide_pointer()` (POST, System Manager) is the only writer. It appends `POINTER` once, when the text does not name `get_agent_guide`, through `get_single("System Settings").save()`. No install, migrate or patch writes the field (`test_guide.TestNoUpdateWritesAgentInstructions`). The AI Access panel line `exposure.get_guide_pointer_line` shows the button to a System Manager while AI is on and the sentence is missing.
- **Office reads:** `church_people/ai.py`, `church_ministries/ai.py` and `church_summary/ai.py` hold the reads for AI apps and the Church Office agent. Each is GET, calls `require_ai` first, refuses a Website User (`frappe.only_for(SYSTEM_USER_ROLE, message=True)`), narrows a list or count of people to the reader's churches (`in_readers_churches`, `dashboard.count_people`), runs a report through `frappe.desk.query_report.run` (`get_report_rows`, so the report roles, the `report` permission on its doctype, the Link filter checks and User Permissions apply as in the desk) and gives a page of 50 with the total (`get_page`). A read gives what the reader could read in the desk and refuses nothing by doctype or age: a record goes through `apply_fieldlevel_read_permissions` and drops masked keys, rows through `get_list`. `validate_person_filters` is the one check of a smart-list filter (Person and its child tables, 10 filters, 20 columns, Frappe's own `get_filter`); `get_filter_items` drops the fifth element that lists saved by an older Frappe keep on each filter. The People report view keeps a standard filter (Membership Status) from the user's last visit beside the link's filters, so `explanation` tells the person to remove it. A read that sends the details of a record writes one Access Log row with method "AI: <feature>" and the record as reference (`make_access_log`; the briefings use "AI: Person briefing" and "AI: Group briefing"). Use that convention for every later AI feature. `church_people/ai.py` is about 640 lines: the briefings stay there because `test_ai_hygiene` scans only `churchit/ai/*.py` and `churchit/<module>/ai.py`.
- **Church Office:** `churchit.ai.flow.agents()` (`flow_agents`) declares churchit/Church Office, churchit/Writer and churchit/Private Work, none while no enabled chat Flow Model exists. Church Office reads and drafts. Its tools are the `@tool` wrappers in `flow.py` (`OFFICE_TOOLS`) over the AI reads and `drafts.make_draft` (with the chat's Flow Model as the source), plus Flow's `find_doctypes`, `describe`, `read_records`, `run_report` and `read_screen`. It never gets a write, web, memory or `execute` tool, and none of its tools asks for approval, because none changes data. The `propose` tool calls `make_draft`, so the limit of 30 drafts an hour on `propose` does not apply in Flow. A wrapper only calls the module function, which checks `require_ai`, the desk user and the permissions, and takes its description from that function's docstring: a docstring change reaches Flow at the next agent sync. A new AI read that the agent should use gets a wrapper in `OFFICE_TOOLS` with the same parameters. Writer and Private Work have no tools. Flow writes the agents after each migrate. Churchit also syncs them when an enabled chat Flow Model is saved (`flow_models.sync_agents_on_model`), in a job when AI is turned on (`flow_models.queue_agent_sync`) and when the manual sync makes its knowledge base. Flow keeps an agent's Model and the Roles that a System Manager sets. The desk boot asks `flow_models.is_flow_ready()`, which reads the Flow Model and Flow Agent tables by the names in `flow_models` (`OFFICE`, `WRITER`, `PRIVATE_WORK`) and loads no Flow code, so a Flow API move cannot stop the desk from booting (`test_switch.test_boot_loads_no_flow_code`). Flow lets the owner share a chat with a person (`share_session`) or open it to every Flow User (`set_general_access`), and each of them then reads the tool results, briefings included, that the owner's permissions gave: the Foundations manual, the People manual and the AI Access panel tell people not to share a chat that holds a briefing.
- **Manual knowledge:** `manual_knowledge.queue_sync` (`after_migrate`, and Church AI Settings `on_update` when AI turns on) queues `churchit.ai.flow.sync_manual_knowledge` only with AI on, Flow and an enabled embedding model in Flow Knowledge Settings. The job (long queue, deduplicated) runs as Administrator and keeps the "Churchit Manual" Flow Knowledge Base equal to the manuals, one Text source per section, matched by title: an unchanged section adds nothing, and a changed or gone one loses its source. A section runs from one h2 heading to the next, so a new h2 in a manual needs a title that is unique across the manuals (`test_manual_knowledge`). `to_text` keeps `<` and `>` escaped, because Frappe's XSS filter strips tag-like text from the source content and the sync compares the saved text. Setting the embedding model while AI is on queues nothing: the manuals arrive at the next migrate. `churchit/manuals.py` is the one reader of the manual workspace blocks, for this job and for `docs/build_docs.py`, and uses only the standard library.
- **Where each AI method lives:** `ai/guide.py` (`get_agent_guide`, `add_guide_pointer`, `has_guide_pointer`); `ai/drafts.py` (`propose`, `make_draft`, `get_draft`, `label_saved`); `church_people/ai.py` (`get_smart_list_url`, `validate_person_filters`, `get_smart_list_people`, `first_time_guests_without_follow_up`, `people_not_seen`, `birthdays_and_anniversaries`, `groups_needing_attention`, `get_person_briefing`, `get_group_briefing`); `church_ministries/ai.py` (`get_open_needs`); `church_summary/ai.py` (`get_week_overview`); `ai/flow.py` (`agents`, `sync_agents`, `sync_manual_knowledge`, the tools); `ai/manual_knowledge.py` (`queue_sync`, `get_manual_sections`); `ai/flow_models.py` (`sync_agents_on_model`, `queue_agent_sync`, `is_flow_ready`). The recipes in `skills/churchit` name these methods; a new AI read gets a row in the skill's method table, a tool in `flow.py` and a line in `Manual: People` or `Manual: Foundations`.
- **Flow:** `churchit.ai.flow` is the only module that imports `frappe.flow`. It imports `frappe.flow.lib.tool` (`tool`, `ToolContext`) when it loads, because Flow calls each tool back by its module path; every other import of `frappe.flow` stays inside a function. No other churchit module imports `churchit.ai.flow` at load, so churchit still loads on Frappe 16.54.
- **Flow hooks:** `churchit/ai/flow_switch.py` and `churchit/ai/flow_models.py` hold the hooks on Flow's doctypes. They use only standard hooks (`has_permission`, `permission_query_conditions`, `doc_events`, `after_install`, `after_migrate`) and work on documents, so they never import `frappe.flow`. A Frappe without Flow never fires the hooks on Flow's doctypes, and `add_privacy_label_field` does nothing there. Do not patch Flow, wrap its functions or intercept its requests. A document hook refuses with `ValidationError`, because Flow's sync of an app's row skips only that error and goes on. The Flow Trigger hook runs on `before_validate`, so it refuses before Flow's own check that Run As may use the agent, which churchit's agent hook fails while AI is off. A new session refuses with `PermissionError`. A `has_permission` hook gives its reason with `frappe.permissions.push_perm_check_log`, and Frappe shows it only when a person's own check with `throw` fails. `ai/test_flow_switch.py` reaches Flow by dotted path (`frappe.call`, `mock.patch`), never by import.
- **Flow rules:** While AI is off, Flow refuses a new chat (Flow Session `before_insert`), a new turn of an old chat (Flow Agent and Flow Session `has_permission`, and no list shows an agent), an enabled Flow Trigger, and a new Flow Knowledge Source or a change of what one reads (a rename and turning Auto Sync off still save). A new chat, a trigger and a source show "AI is turned off on this site." A new turn shows Frappe's own permission message: Flow gives write on a chat only to its owner (`if_owner`), so Frappe's second check, on the doctype, replaces the sentence. An install, a migrate or a patch skips these refusals (`flow_switch.is_updating`), because Flow writes the agents, tools and triggers of apps then. The trigger hook also skips Flow's own sync of an app's trigger (system-generated, saved with `ignore_permissions`), which runs when the first Flow Model arrives. While AI is off, Flow's own Run As check still skips an app's trigger with a named Run As there, because churchit's agent hook fails it, and the next update adds it. Administrator passes every `has_permission` hook, so only the `before_insert` refusal stops its new chats, and it can still continue an old chat. While AI is on, a person's new chat starts in Ask, not in Flow's default Auto. An enabled Flow Trigger on text that guests or members write (`flow_switch.GUEST_DOCTYPES`), or one that runs as Administrator, gets a warning and is saved (`flow_switch.get_trigger_warnings`). The exposure panel lists each such enabled trigger, because an update and Flow's own sync save an app's trigger without the warning. Flow's chat button shows to every Flow User whatever the switch says, because Frappe adds it after a doctype-level check that hooks never see. Churchit has no setting for Frappe's Flow Assistant: with AI on it works with the user's permissions, like an MCP app, and a System Manager can clear Enabled on its agent in the Flow Agent list (an update keeps that). The Flow User role lets a person use Flow in the desk. Churchit adds no role for it.
- **Flow knowledge:** a DocType Flow Knowledge Source copies every matching record with `frappe.get_all`, gives the text to everyone who uses an agent with the knowledge base, with no permission check, and sends it to the embedding model. Roles on an agent do not limit it as a sub-agent: a sub-agent works for everyone who can use the agent that has it. So `flow_switch.check_knowledge_source` refuses a new source, or a change of what one reads, on a doctype in Church AI Settings' Blocked from Flow Knowledge (`blocked_knowledge_doctypes`) at all times, in an update too. An app whose patch adds one fails its update; when it adds one while Flow syncs its agents, Flow skips those agents and logs why. A source on a churchit doctype, or a recommended Frappe or Flow doctype, that is not blocked (`flow_switch.is_church_doctype`) saves with an orange warning, and the exposure panel shows each source on church records or on a blocked doctype as Blocked or Not blocked. The list starts with `flow_switch.get_recommended_knowledge_doctypes`, a rule and not a list: each churchit doctype, child tables included, that is or links to Person, Family, User or Contact (`PERSON_LINKS`) or links to such a doctype (one level), the child tables of these and `SENSITIVE_DOCTYPES`, without Singles and `PUBLIC_AND_SETUP_DOCTYPES`, plus Frappe's `PEOPLE_DOCTYPES` and, with Flow, `FLOW_DATA_DOCTYPES` (Flow's chats, memories and knowledge chunks keep what each person read with their own permissions), with their child tables (`get_frappe_people_doctypes`), because Flow reads a child table on its own. A churchit doctype about people that links to no person goes in `SENSITIVE_DOCTYPES`; a public or setup doctype that links to a person goes in `PUBLIC_AND_SETUP_DOCTYPES`. `fill_blocked_knowledge_doctypes` fills an empty list (after_install and a v1_0 patch) and leaves a list with rows as it is. The Use the Recommended List button calls `use_recommended_knowledge_doctypes` (POST, System Manager or Church Manager, also while AI is off), which adds each missing doctype and keeps every row. So a new doctype reaches the list of an existing site only from that button or from a versioned patch that adds it. On a multi-church site only a Church Manager with no Church restriction (or a System Manager) removes a row, as for turning AI on. `forget_missing_blocked_doctypes` (`after_migrate` and `after_app_uninstall`) deletes the row of a doctype that is gone: a migrate and an uninstall delete doctypes without checking links, and a row for a missing doctype makes every save of Church AI Settings fail, turning AI off too.
- **Privacy label:** `church_privacy_label` on Flow Model is a Custom Field. `flow_models.add_privacy_label_field` creates it with `create_custom_fields` in `after_install` and `after_migrate`, only when `switch.has_flow()`. Never make it a fixture, because a fixture for a doctype that Frappe 16 lacks breaks migrate. `church_privacy_label_by` and `church_privacy_label_on` are stamped in Flow Model `validate` when the label changes. The label is the admin's statement, and nothing checks it. The exposure panel warns about `flow_models.UNSAFE_LABELS` (Unknown and May train). Churchit has no data tiers engine. A churchit AI feature that sends church data to a model names the exact fields it sends, reads the label of the model and wraps text that guests write.
- **Flow server (Docker):** `deploy/docker-compose.yml` has the `flow` profile (`flow-configurator` and `flow-server`) and an in-memory `flow-server` volume in every container that runs the image, because Flow's daemon listens on a unix socket there. The `flow-server` command removes the stale `daemon.pid` first, because the image has no `ps` and Flow's restart check runs it. `tests/test_deploy_compose.py` guards the profile, the volume and the dependencies, and on a Flow bench it fails when Flow moves its pid file or the socket's folder (`frappe.flow.daemon.lifecycle`). `deploy/README.md` explains how to turn it on. No published image has Flow, because the image workflow builds only `version-16`. Frappe Cloud is not confirmed.
- **Docs:** the skill for AI apps is `skills/churchit/`. Add a method, a doctype or a report that an agent should use to the skill in the same change. `tests/test_skill_hygiene.py` fails on a method that is missing or not whitelisted.
- **Connected apps:** `switch.tell_system_managers_of_new_ai_app` (doc_events OAuth Bearer Token after_insert) leaves each System Manager a bell notice and an email for the first active token of a person and app, so a sign-in after a revoke counts again. An OAuth Bearer Token's name is its access token, so never put a token's name in a notice, a log, a link or a report: name its OAuth Client.
- **Boot:** `frappe.boot.churchit.ai` is `{"on": bool, "flow": bool, "flow_ready": bool}` (`switch.extend_bootinfo`). `flow` is `switch.has_flow()`: without it, Church AI Settings hides its Flow sections and drops its Flow sentences. `flow_ready` is true when Flow is present, a chat model is enabled and every churchit agent is synced (`flow_models.is_flow_ready`, which loads no Flow code).
- **Next release:** a read that a script under `public/js` calls takes GET and POST for one release, because browsers keep the old script for 12 hours. MCP runs a method that takes POST as a write and commits, so at the next release make each of them `methods=["GET"]` (the GET and POST reads in `tests/test_http_method_hygiene.py` that are not in `CORE_SCRIPT_POSTS` or `LONG_LIST_POSTS`).
- **Test:** `tests/test_ai_hygiene.py` checks the AI endpoints, `tests/test_agent_docs_hygiene.py` checks the docstrings and hints of every whitelisted function, and `tests/test_skill_hygiene.py` checks the skill. `ai/test_switch.py` signs in an app through Frappe's own `validate_client_id`. `ai/test_flow_switch.py` proves the Flow refusals and that the recommended list holds each doctype that the roadmap keeps from AI, and `ai/test_flow_models.py` proves the privacy label and its panel lines, and that the manual names every doctype in `flow_switch.GUEST_DOCTYPES`, `PEOPLE_DOCTYPES` and `FLOW_DATA_DOCTYPES`. Both run on a Flow bench and skip what needs Flow on Frappe 16. `ai/test_guide.py`, `ai/test_drafts.py` and the `test_ai.py` of `church_people`, `church_ministries` and `church_summary` run as church-scoped users and run on Frappe 16 and on a Flow bench. `ai/test_flow_agents.py` and `ai/test_manual_knowledge.py` need Flow and skip without it; the sync tests patch Flow's ingest, so no embedding model is called. Tests never call a chat model.

### Flow API watch

Flow is version 0.1.x on Frappe's development branch (Frappe 17). Its API can change in any update. `churchit/ai/flow.py` is the only module that imports `frappe.flow`. Only Flow's hooks (`flow_agents`, `flow_tools`, `flow_triggers`) and code that has checked `switch.has_flow()` load it; `ai/test_flow.py` enforces this. After each update of the Flow bench, run `churchit.ai.test_flow` there and on a Frappe 16 site, then the full suite on the Flow site, before you change code that calls Flow. `ai/test_flow_models.py` also pins the Flow Model field that the label follows (`extra_params`), so a Flow update that renames it fails there first. `flow.py` uses `frappe.flow.lib.tool` (`tool`, `ToolContext`), `frappe.flow.lib.agent` (`Agent`, `sync_agents`), `frappe.flow.knowledge.Knowledge` and the read tools of `frappe.flow.tools.builtins`, and the agent and knowledge code runs at each agent sync and manual sync: after a Flow update also run `ai/test_flow_agents.py` and `ai/test_manual_knowledge.py` there. Move the Flow bench to a new Frappe commit on purpose and name the commit in the change.

## Client side

`frappe.boot.churchit` carries `multi_church`, `church`, `shared_people`, `include_branches`,
`single_church`, `churches` (the reader's own churches, `None` when unrestricted) and
`expand_church_filters` (`church_scope.extend_bootinfo`). Use it rather than querying from JS.
Anything keyed on it must behave when multi-church is off.

`churchit/public/js/church_utils.js` wraps `frappe.views.BaseList.prototype.get_filters_for_args` so
the "expand filters to branches" option reaches list views. It is guarded and falls back to exact
matching if a Frappe upgrade moves that method; if list filters stop expanding after an upgrade,
look there first. The same file wraps `frappe.form.formatters.Link` for report link titles, and it
replaces `MapView.setup_view` (see the next section).

## Frappe behaviours worth knowing

- **Administrator is never restricted.** User permissions do not apply to it, so it always sees every
  church. Test scoping as a Church Manager, never as Administrator.
- **Booleans over `frappe.xcall` arrive as strings.** Use `frappe.utils.sbool`, not `cint`.
- **A Check of 0 cannot be told from not set.** A server copy of a type's defaults would undo a
  user's untick, so Group Type defaults are copied only by `group.js` when `group_type` changes, and
  the server copies nothing. Do not use `fetch_from` or `fetch_if_empty` for such defaults.
- **The payments app replaces Frappe's web form save.** Its copy of `accept` takes the doctype from
  the browser and ignores Web Form Request keys (frappe/payments#276), so hooks.py points `accept`
  back at Frappe's own; the last installed app wins. A test that calls Frappe's `accept` directly
  tests the real path only while that override holds.
- **Frappe 16.50's Map view is broken.** `ListView` sets `this.load_lib` to a Promise, which hides
  `MapView.load_lib()` (frappe/frappe#44810). `church_utils.js` replaces `MapView.setup_view`; remove
  that once Frappe fixes it.
- **Kanban v2 keeps only the new column from a card move**, and ignores its own realtime update for
  that card. A doctype whose save changes other card fields reloads the board in its
  `<doctype>_kanban.js` `onAfterCardMove`, as `follow_up_card_kanban.js` does.
- **Frappe's calendar draws a Date field as an all-day entry.** The Function calendar
  (`function_calendar.js`) reads `function.get_calendar_events`, which puts each function's start
  and end time into Start Date and End Date. A drag or resize goes through `move_on_calendar`, which
  keeps All Day as it is. Frappe sends all_day for any entry that lasts exactly 24 hours, so a timed
  entry dropped on the all-day row arrives as a 24 hour all-day entry: `move_on_calendar` then moves
  only its day and keeps its times. Frappe also converts every timed entry from the system time zone
  to the user's time zone. Both methods keep the real fieldnames in `field_map`, so selecting a time
  range still starts a new Function on that date.
- **A standard Kanban Board ships in `<module>/doctype/<doctype>/kanban_board/<name>.json`**, the
  only path Frappe 16.54 syncs. It needs `is_standard` Yes, a `module`, `use_kanban_v2` and
  `private` 0, or Frappe refuses it. A site that already has a non-standard board of the same name
  keeps its own. A card sits in the column that has its status as name, so a status with no column
  leaves its cards off the board (Care Requests keeps Closed as an Archived column on purpose). A
  card move saves only the status through `frappe.client.set_value`, so the controller runs. On a
  developer-mode site, saving the board record rewrites its file. `tests/test_boards_and_tours.py`
  checks the two shipped boards, Care Requests and Church Tasks, which the 'Care Board' and 'Tasks
  Board' shortcuts open.
- **A web form puts the records of its Link fields into the page**, hidden fields included: every
  record on a guest form or with Allow Read On All Link Options, else the records the user owns. So
  a guest form's hidden `church` field is Data, not Link, and a member form does not link to Person
  (`tests/test_portal_members.py` checks both).
- **Frappe 16.50 joins a linked table once for all `link.field` fetches**, so a list view with two
  Links to one doctype shows the first link's title in both columns. Show Data name fields instead,
  as Possible Duplicate does.
- **Never name a field `assigned_to`.** Frappe's `assign_to` writes the assignee's User ID into any
  field with that name and clears it when the assignment goes. Care Request's Person link is
  `caregiver` for that reason.
- **Frappe checks create before `fetch_from` fills `church`.** It also checks write on the record as
  the caller sent it, so it sees neither whose record the link names nor whose record this was. A
  doctype that takes its church from a link calls
  `church_scope.refuse_another_churches_parent(self, "<link>", _("{0} belongs to another church, ..."))`
  in `validate`. When the link changes and the save is not `ignore_permissions`, it refuses unless
  the user may see both the linked record's church and the stored church, and fills `{0}` with the
  refused record's title. Ministry Team Assignment calls it only on insert, because its links are
  set once. `tests/test_church_scope_hygiene.py` fails when a doctype whose `church` has `fetch_from`
  does not call it on that link and is not in `PARENT_GUARD_EXCEPTIONS` with a reason: Communication
  Consent checks every save, because its person is set once; Giving Statement checks its own church,
  because a statement for another church's giver stays in the issuer's church; Possible Duplicate
  checks a change of either person of its pair. Family sets its church in code, so it checks its
  primary contact itself and each new member, and Person checks a changed `family`, so a household
  spans churches only when a user who sees both churches links it.
- **Model sync gives every existing row a new column's default before any post_model_sync patch.**
  When that default widens access, move the data in a pre_model_sync patch that syncs the doctype
  itself (`set_prayer_request_visibility`).
- **Assigning a record shares it.** Frappe's `assign_to` shares a record with an assignee who cannot
  read it, and the Share menu shares on purpose. `church_access.refuse_sharing_outside_the_church`
  (DocShare `validate`) refuses both when the user cannot see the record's church, and refuses
  sharing a church's record with everyone. Assign only users who can see the record's church
  (`church_scope.has_church_access`); an assignment from code to anyone else fails loudly.
- **Frappe's connection counts ignore permissions.** It counts with `get_all`, for every doctype
  asked for, so `churchit.connections.get_open_count` replaces it and counts with `get_list`.
  A connection to a confidential doctype is safe to add for that reason only.
- **User defaults are cached per worker** and lag a write by a request; read the `DefaultValue` row
  directly when a choice must take effect immediately.
- **Hand-edited Workspace, Report and similar JSON is skipped by migrate** unless its `modified`
  timestamp is newer than the row in the database. Bump it to the current time or your edit silently
  does nothing. Never write a future time: a site that imports it then skips every real edit made
  before that time. If a local database row already holds a future stamp, reset that row instead
  (`tests/test_json_hygiene.py` refuses future stamps).
- **An email can carry a print format that is rendered when it is sent.** Pass
  `{"print_format_attachment": 1, "doctype", "name", "print_format"}` in `attachments` to
  `frappe.sendmail`, as `GivingStatement.send_by_email` does, so no PDF is made while a row lock is
  held.
- **Frappe imports module folders only for the doctypes in its own `IMPORTABLE_DOCTYPES` list**
  (`frappe/model/sync.py`), which covers Notification but not Letter Head or Email Template. Records
  shipped as JSON beside their module for anything outside that list never reach a site, however
  correct the file; `patches/after_install.create_unsynced_records` seeds those.
- **`get_church()` returns a cached document shared process-wide.** Never mutate and save it; load a
  fresh copy with `frappe.get_doc("Church", get_church().name)`. A save on the cached copy leaves it
  holding a timestamp a rolled-back row no longer has, and the next save fails as stale. After a
  `frappe.db.set_value` on the Church use `frappe.clear_document_cache`, not `clear_cache(doctype=…)`,
  which only clears the meta.
- **A dialog on a portal page shows each field's name.** Every control carries a `.tooltip-content`
  span with its fieldname, and the website CSS hides it only inside a web form body. A
  `frappe.ui.Dialog` sits outside it, so a portal page that opens one adds the
  `.modal .tooltip-content` rule, as `portal_groups.js` and the Community Prayer Requests web form
  do.
- **Email open tracking is added at send time.** Email Queue `message` holds only
  `<!--email_open_check-->`; `SendMailContext.build_message` puts in the image when the Email Account
  has Track Email Status and the queue has a `communication`. A test builds the message the same way
  (`church_communications/test_open_tracking.py`).
- **The desk draws field help as HTML.** A placeholder in angle brackets, such as `<name>`, is an
  unknown tag and vanishes. Write it in capitals, such as CHANNEL_ID, and put an example in the
  field's `placeholder`. A description uses only the inline tags in `HELP_TEXT_TAGS`
  (`tests/test_desk_ui_hygiene.py`).
- **A doctype JSON's `fields` list does not follow the form.** `field_order` does, and 31 doctypes
  list their fields in another order. A check or script that reads the layout from JSON sorts by
  `field_order` (`get_fields_in_form_order` in `tests/test_desk_ui_hygiene.py`).
- **A shortcut cannot open the Map view in place.** Workspace Shortcut `doc_view` has no Map option,
  and `frappe.utils.generate_route` sends any other value to the doctype's default view. A Sidebar
  URL item, and a URL shortcut too, opens in a new tab. The People workspace therefore opens the
  Address map with a URL shortcut to `/desk/people/address/view/map`. The `people` part keeps the
  People sidebar in the new tab only because that sidebar lists Address (Data, Addresses). Without
  the listing, the desk switches to Frappe's Contacts sidebar. Do not set `default_view` Map on
  Address, because ERPNext shares the doctype.
- **The search bar checks each hit with `frappe.has_permission`, not with
  `permission_query_conditions`.** A doctype whose access rule lives only in query conditions needs
  a matching `has_permission` hook before it is searched; Person and Family have both. A save only
  queues its search row, and Frappe writes the queue every 15 minutes. `frappe.db.set_value` skips
  the index, so after one on a searched field call `privacy.refresh_search_row`, as anonymizing
  does. The index `__global_search` is a MyISAM table: a rollback does not undo it. So if Remove
  Personal Data fails and rolls back, the person keeps their data but has no search row, and Frappe's
  own save has queued the anonymized one, until the person's next save. It does not wait for the
  commit, because a write after the commit breaks a following `sql_ddl`. A test deletes the rows it
  made (`test_global_search.forget_search_rows`). MariaDB indexes only whole
  words of 4 letters or more (`ft_min_word_len`).
- **A changed `_list.js` of an existing doctype shows only after `clear-cache` or a migrate.**
  Frappe keeps the list script in the doctype meta.
- **A tree with exactly one top-level record draws it as the root by its ID, not its title**
  (`treeview.js get_root`). So `church_location_tree.js` sets `get_tree_root` off and roots the tree
  at 'All Locations' (`root_value` "", the top level of the default `get_children`).
- **A Single shows no `placeholder` on a Data, Link, Dynamic Link, Password, Select or Read Only
  field.** In Frappe 16.54 `ControlData.set_input_attributes` returns early on a Single before it
  sets the placeholder. On a settings doctype, put a short example in the help instead.

On Frappe 17 (the Flow bench) also:

- Error, Access, Activity Log and Route History live in a log database. `frappe.db` cannot read or
  delete them, a rollback does not undo them, and `get_all` returns 20 rows unless you pass a limit.
  In tests, use `tests.helpers.pop_logs`.
- An Expression autoname reads YY, MM, DD, WW, JJJ or YYYY before `-.####` as a date. Do not start a
  series prefix with one of them (`MeetingMinutes.autoname` keeps `MM-`).
- A File that an Attach field still names cannot be deleted. Pass `force=True` only when you replace
  the field in the same step.
- `frappe.client.get` leaves out empty fields. Read a result with `.get()`.
- Every GET whitelisted method also allows QUERY. Compare allowed methods without QUERY.
- A fake request needs `after_response` (`frappe._dict(method=..., headers={},
  after_response=CallbackManager())`): the log database queues its closing there.
- Letter Head is a synced standard record with mandatory `letter_head_for` and `standard`.

## Testing

Run the whole suite before committing anything broad: `bench --site <site> run-tests --app churchit`.
CI does not run it.

- The suite is **destructive on a site you care about**. `TestSampleDataRoundTrip` deletes the
  sample data and creates it again, and the site keeps the result. Restore with
  `churchit.setup.sample_data.create_sample_data()`, which is idempotent, or run single modules while
  developing.
- **`delete_sample_data` removes every sample record.** A new sample doctype needs a delete step (all
  rows, or a filter for a shared lookup such as Skill), and a value the load sets on an existing record
  (the Church, Website Settings) needs its undo. Insert a record that fires a Notification or starts a
  follow-up card inside `_as_quiet_import`, as the sample check-ins are. `TestSampleDataRoundTrip`
  fails when a load and a delete change a table's row count, a Series counter, a Singles value or a
  field of the Church. It loads with an outgoing Email Account, so the emails the load queues count too.
  For each doctype the delete empties, `_clear_history` also deletes every row that refers to its
  records (the tables in `_HISTORY`, Communications, ToDos, Files, Email Queue), a church's own included,
  because the emptied Series gives the next record an old name. Add a new Frappe table that stores a
  doctype and a name to `_HISTORY`.
- Tests must set `frappe.local.form_dict`, never `frappe.form_dict`, which replaces the proxy for the
  rest of the process and breaks later tests.
- Use `churchit/tests/helpers.py`: `ensure_root_church`, `make_branch`, `set_multi_church` and
  `force_single_church` put the site into a known mode inside the test transaction. Never look up the
  church with `frappe.db.get_value("Church", {}, ...)`; a site may hold branches.
- Make the records that a class shares once, in `setUpClass`. When its tests change them, extend
  `RollbackEachTest`: it rolls each test back to a savepoint and drops the caches the test changed. Do
  not use it for a test that writes a file, because the rollback removes the File record and leaves
  the file on disk.
- Call `frappe.clear_cache()` at most once per test class, never per test or in code that runs on every
  save. It drops the metadata of every doctype, and rebuilding that metadata is the slowest part of
  the suite. Clear only the doctype or document that changed.
- Frappe keeps a new record's defaults in `frappe.local.new_doc_templates` until the request ends, so
  a test that changes a default pops it.
- `churchit/tests/test_church_permissions.py` is where scoping behaviour is proved. Add to it when
  you add a surface that reads church data. `make_two_churches()` and `assert_scoped()` in
  `churchit/tests/helpers.py` make that two lines:

  ```python
  root, branch_a, branch_b = make_two_churches()
  assert_scoped(self, "Prayer Request", manager_a, request_in_a, request_in_b)
  ```
- Run `ruff format` only on the files you changed; the pinned version reformats older files.
- A test that sets a site default (`country`) restores it with `addClassCleanup`; the test site may
  have none. A test that calls Frappe's `get_open_count` resets `frappe.db.set_execution_timeout(0)`,
  because it limits the session to 1 second and later tests share the connection.
- Frappe saves no Version row while tests run: `Document.save` sets `ignore_version` from
  `frappe.in_test`. A test that needs the change history saves with `ignore_version=False`.
- Sample birthdays and anniversaries use `_this_week_in`, which keeps the date inside the current
  Monday-to-Sunday week. Pass a leap year, so a Feb 29 in this week exists in it. Do not use a plain
  day offset for a 'this week' record.

## Desk navigation

The Apps screen shows one Churchit tile (`add_to_apps_screen` in `hooks.py`), but a desk user opens
Summary after login: `church_summary/home.land_on_summary` sets their Default Workspace when they
first become a desk user, and leaves a choice they make later alone. Only a user with one of
Summary's roles gets it, so an ERPNext accountant on a shared site does not land on a page they
cannot open. A desk user with no Default
Workspace opens Summary too, because each desk role's home page is `/desk/summary`
(`fixtures/role.json`). The `ModuleShortcuts` block at the top of Summary draws a tile for each
entry of the user's dock, so it hides what the dock hides. A Frappe page that no churchit sidebar
lists opens in Framework, so `add_return_to_framework_dock` (after install and every migrate) puts
a Churchit entry first on the site's arrangement of Framework's rail. A saved arrangement is the
whole rail, so it also names every Framework entry. Inside the app, the dock on
the left lists the modules (`churchit/dock/churchit/churchit.json`), and each module has one sidebar
(`churchit/<module>/sidebar/`). Three rules fail silently, so
`churchit/tests/test_navigation_hygiene.py` checks them:

- **The dock must name every sidebar.** A sidebar the dock leaves out opens by URL only.
- **One sidebar per module.** The desk opens a workspace in the first sidebar of the workspace's
  module, so a second sidebar in one module shows the wrong one. A new dock entry needs its own
  module, the way Summary and Help have theirs.
- **A sidebar opens on a workspace of its own module.** A module opens on the first link of its
  sidebar, and a workspace of another module switches the sidebar on arrival.

Edit a sidebar or the dock on a developer-mode site, from the desk or with `doc.save()`. Frappe
writes the file itself. Church Features hides a disabled module through the site's own layer of the
dock and each user's (`Dock` rows with `standard` off), never through the files.

A saved arrangement of the dock keeps its own row order, so a new order in
`churchit/dock/churchit/churchit.json` does not reach a site that has one. Church Features saves the
site's arrangement when it hides a module. Change the shipped order together with a v1_0 patch that
reorders the site's arrangement when its rows are still in the previous shipped order, as
`order_the_dock_by_weekly_use` does. Leave users' own arrangements alone.

## Onboarding steps and form tours

A module's `Module Onboarding` is the checklist a new church works through, and each step carries a
`Form Tour` explaining the fields the form does not explain by itself. Five things here fail
silently, so `churchit/tests/test_onboarding_hygiene.py` checks them rather than leaving them to
review:

- **An onboarding is rendered only from an `onboarding` block in a workspace.** Frappe 16.50
  removed the sidebar panel, so an onboarding that no workspace's `content` names never shows. Put
  `{"id": "<10 characters>", "type": "onboarding", "data": {"onboarding_name": "<name>", "col": 12}}`
  on a workspace of the onboarding's own module. The block disappears when every required step is
  done or skipped (a Create Entry step counts as done once a record exists). Dismiss hides it for
  24 hours in that browser only. No onboarding shows until the setup wizard turns on Enable
  Onboarding in System Settings. A site that customized a workspace layout in the desk keeps its
  own snapshot (Custom Workspace), so it does not receive new blocks and does not follow relabelled
  rows.
- **Only two step actions start the tour.** `Create Entry` for a normal doctype and
  `Show Form Tour` for a Single, which routes to the settings page and then starts the tour.
  `Go to Page` and `Update Settings` both route to the form and ignore `form_tour` entirely, so a
  tour on either is dead configuration. Use `Go to Page` only for a step that has no form, the way
  `Sample Data` does.
- **A `Create Entry` step needs `Show Full Form`.** Without it the widget opens quick entry, which
  runs no tour.
- **A tour step names a fieldname, not a label.** Rename or hide the field and the tour stalls with
  no error. Point tours at fields the user can see. A field is not drawn when it is `hidden` (the
  `church` field included) or sits in a hidden tab, section or column. A field is also absent on a
  single-church site, which is most sites, when its `depends_on`, or the `depends_on` of its tab,
  section or column, is the multi-church switch (`test_onboarding_hygiene` checks this).
- **Tour steps follow the order of the form.** A step that sits above the previous one makes the
  user look back up the form. Reorder the steps when you move fields
  (`test_tour_steps_follow_the_order_of_the_form`).
- **One script adds 'Take the Tour'.** `public/js/help_icon_on_form.js` puts it in the '...' menu of
  every form that has a standard Form Tour, found by the tour's `reference_doctype`, because a tour
  name can differ from its doctype (Budget, Email Account Setup). Frappe 16.54 lists no tours at
  boot, so the script asks once per page load. Do not add a menu item for a tour in a doctype's own
  script, and give a doctype one tour (`tests/test_boards_and_tours.py`). Set `include_name_field`
  only for a doctype named by Prompt: on a doctype named by a field, the hidden name field leaves
  the tour with nothing to show at its first step
  (`test_a_tour_asks_for_a_name_only_where_the_form_has_a_name_field`). A tour step that points at a
  field behind `depends_on` stalls the tour when the user does not tick the switch. Put the hint in
  the step of the switch instead (Email Account Setup).

`Onboarding Step` carries no `module` field. A step belongs to the module folder it ships in, and its
name is global across every app, so name it after the doctype and do not prefix it.

## Desk lists and forms

Every module's lists, forms, sidebars and workspaces follow the same rules, so a secretary who knows
one module knows them all. Use a Frappe setting first. Use a form script or a hook only when no
setting does the job, and give the reason in the change. Most rules have a ratchet check: a test
with a list of today's exceptions. When you fix an exception, delete it from the list. The check
fails on a new violation and on an exception that is no longer needed, so the lists only get
shorter. The value of an exception is the reason it stays. Every ratchet uses
`assert_list_ratchet` in `tests/test_desk_ui_hygiene.py`.

### Lists

- Show the title, a status pill and 4 fields that answer the list's question. Up to 2 more fields
  can follow, so 6 `in_list_view` fields at most (`test_list_columns_stay_within_the_budget`). A
  phone shows 2 field columns. With a status pill these are fields 1 and 2. Without a pill they are
  fields 2 and 3, because Frappe draws columns 4 and 5 of the row (`ListView.get_left_html`), so the
  first field never shows on a phone: Person Note hides its Category there. On a list with no pill,
  put the field that matters least first. List columns follow the form's `field_order`: to move a
  column up, move the field up the form. A hidden field in the header section is fine.
- No Text, Small Text, Long Text, Text Editor, HTML Editor, Markdown Editor, Code, Table, Table
  MultiSelect or Geolocation column (`test_lists_have_no_text_columns`). No Link column whose
  `fetch_from` fills the title, because the subject shows it. The desk leaves the title field itself
  out of the field columns, so its `in_list_view` flag adds no column, but the budget still counts
  it (`test_lists_never_repeat_the_title`).
- 4 `in_standard_filter` fields at most. Frappe adds the title filter by itself. A multi-church site
  also shows the church and sharing filters, and the budget does not count them. A Check filter
  finds only ticked records, so use one only when ticked is what users look for, such as Publish or
  Bookable (`test_list_filters_stay_within_the_budget`).
- A doctype with a `title_field` hides its ID: set `hide_name_column` and `hide_name_filter` in
  `<doctype>_list.js`. Staff quote the number of a Collection, Expense, Fund Transfer, Online
  Donation, Counseling Case, Church Asset and Bible Translation, so these keep the ID. Room Booking
  hides the ID column but keeps the ID filter, because the setup sheet prints the BK number
  (`test_lists_with_a_title_hide_the_id`). Address keeps its ID column too, because the ID (address
  title and type) says whose address it is, and hiding it would need a list script that also changes
  ERPNext's Address list. A list that starts with an ID or a hash gets a title field.
- A title field adds its own filter box, so do not also set `in_standard_filter` on the Link that
  fills the title (Background Check, Authorized Pickup, Pickup Restriction and Person Note have a
  Link and a `*_name` title). A lookup named by one field (autoname `field:`) sets `title_field` to
  that field, so its column and filter read 'Type' or 'Skill', not 'ID'.
- A print format or a notification of a doctype that hides its ID shows the title, not `doc.name`
  (`test_prints_and_notifications_never_quote_a_hidden_id`).

### Status colors

A field named `status` gets its colors from the DocType `states`. They show in the list, the form
header and quick lists with no script. A status that other fields decide (dates, checkboxes), or a
status field with another name such as Person `membership_status`, gets a `get_indicator` in
`<doctype>_list.js`. Care Assignment shows Upcoming (blue, before Start Date), Current (green) or
Ended (gray, after End Date) this way, and Pickup Restriction shows Active or Ended from Valid
Until. A click on the pill saves one filter, and one filter cannot
say 'no end date, or an end date in the future'. So Ended is `end_date,is,set|end_date,<,Today` (a
plain `<` also matches an empty date, because Frappe compares `ifnull(date, '0001-01-01')`), and
Current or Active selects only the records with no end date. Each state title must be an option of
the field. For a Link status (Group,
Missionary, Prayer Request) the options are the records the app seeds, so a renamed status record
loses its color. `test_every_status_has_a_color` and
`test_every_state_title_is_an_option_of_its_field` check this. Take the color from this table:

| Color | Meaning | Examples |
| --- | --- | --- |
| Orange | Waiting for staff | Requested, Pending, New, Planned, Open |
| Yellow | In review | Triaged, Reviewed |
| Blue | Under way, or for information | In Progress, Scheduled, Letter Issued, Intake, Published |
| Green | Good result, still current | Active, Approved, Confirmed, Paid, Resolved, Completed, Given, Done |
| Red | Blocked, failed or refused | Conflict, Failed, Needs Review, Declined, Withdrawn, Overdrawn, Unbalanced |
| Purple | Set aside or passed on | Waitlisted, Referred, Blocked, Refunded |
| Gray | Finished or off | Closed, Cancelled, Denied, Inactive, Ended, Spam, Skipped, Draft |

### Sort, default filters and saved list settings

- Sort dated records by their own date, newest first. Sort a work queue by due date, soonest first,
  and a directory by name. Never sort by `modified`, except on a log
  (`test_lists_never_sort_by_modified`).
- `frappe.get_list` with no `order_by` sorts by the doctype's `sort_field`, so a page that reads
  records that way changes order with the list. The Beliefs page lists beliefs as the Belief list
  does: by `creation`, oldest first, which is the order a church writes its statement of faith. This
  is the one list that is not newest first or by name.
- A work queue opens on its own filter, set as `filters` in `listview_settings`. Care Request
  (unfinished), Group Join Request (Requested), Follow-up Card (Open), Church Task (not Completed)
  and Room Booking (not Denied or Cancelled) do this today. Room Booking does not filter on
  Requested, because its calendar view starts with the same `filters` and the calendar would lose
  the approved bookings; the Booking Requests report is its queue. The field of that filter is not
  also a standard filter: Frappe keeps the default filter and adds the standard filter on top, so
  Care Request with Status = Resolved would be empty. The status pill (a click replaces the default
  filter) and the Filters popover cover it (`test_default_list_filters_are_not_standard_filters`).
  An `=` filter is the exception: Frappe puts it in the standard filter box, where the user changes
  or clears it. The Person list opens on Status = Active this way.
- Frappe saves each user's last filters and sort on every list they open, and these win over
  `sort_field` and the `listview_settings` filters. An empty saved filter list wins too. So a change
  to a list's columns, filters or sort ships a v1_0 patch that calls
  `churchit.user_settings.clear_list_filters_and_sort` with those doctypes, and the release note
  says that saved filters and sorts on those lists were reset. A patch runs once on a site, so add a
  new patch for each change and never extend an old one. The patch keeps each user's Report view,
  Kanban and Calendar settings, saved filter layouts and grid columns.
- A church's own List Settings and Customize Form changes are site Property Setters and a List View
  Settings record. On that site they win over the app's list and form changes, and a patch never
  deletes them. A List View Settings record shows only the columns it names, so a new list column
  does not show. A System Manager who drags a column wider also saves one. A church field added
  with Customize Form saves the whole field order, so the form keeps the old order. The
  release note gives the reset: for a list, List Settings, '+ Add / Remove Fields', Reset Fields;
  for a form, Customize Form, Actions, Reset Layout. Never advise Reset All Customizations: it
  deletes the church's own fields and leaves the List View Settings record.

### Search and preview

- `search_fields` holds 2 or 3 fields that tell records with the same title apart. Person has 5,
  because its link search (`search_people`) reads every search field, in this order: primary
  phone, envelope number, nickname, previous last name, middle name
  (`test_search_fields_stay_short`). No rich text, and no Link to an autonumbered doctype, because
  the dropdown then shows raw IDs (`test_search_fields_hold_no_rich_text_or_raw_ids`).
- A doctype that other forms link to sets `show_preview_popup` with 3 to 6 `in_preview` fields. A
  small lookup may have fewer, but never none: with no `in_preview` field Frappe previews every
  required field. There is no preview on Counseling Case, Care Request, Person Note or Background
  Check (`test_previews_need_the_popup_and_skip_private_records`). No Geolocation, Check, rich text
  or Dynamic Link field in a preview (`test_previews_show_only_short_facts`).
- Ctrl+K indexes only the title field (`title_field`, permlevel 0) of the doctypes in
  `global_search_doctypes` (`hooks.py`): never `show_name_in_global_search`, never a second name
  field such as a nickname, and never a record about one person's care, prayer or history
  (`privacy.PERSONAL_DOCTYPES`, `RECORDS_ABOUT_THE_PERSON`, Prayer) (`test_global_search`). A new
  searched doctype sets `in_global_search` on its title field and joins the hook with the next
  `index`. Frappe reads the hook only in the setup wizard, so the same change adds a new v1_0 patch
  that calls `add_to_global_search` with only the new doctypes; never re-run
  `add_churchit_to_global_search`, because a church may have taken rows out on purpose. A new Person
  field that holds personal data goes in `privacy.PERSONAL_FIELDS`, so that Remove Personal Data
  clears it and rewrites the search row. After a `frappe.db.set_value` on a searched field, call
  `privacy.refresh_search_row`.

### Forms

- The first tab is 'Details', with about 15 visible inputs and the main grid of a typical record.
  Its first section has no label. Add a tab when the form has 2 or more separate jobs, or when
  Details is longer than about 2 screens at 1440x1000. 5 content tabs at most. A later tab is a noun
  of 1 or 2 words that the Manual also uses, with the fieldname `<noun>_tab`, and never 'Other',
  'More', 'Misc' or 'Advanced'. 'Connections' (`show_dashboard`) comes after the content tabs, and
  'Church Fields' is last. Singles are exempt from the Details rule
  (`test_tabs_follow_the_naming_rules`). Frappe puts its own Details tab ahead of fields that sit in
  no tab. The check does not look at where Connections sits.
- Put the sections in this order: who or what, when and where, status, the content (text or the main
  grid), then the optional sections. Safety fields (allergies, emergency contacts, pickup rules) sit
  directly under the header.
- A collapsible section has a label that names its content and a `collapsible_depends_on` that opens
  it when it holds something staff typed or must act on. A section of routine system values (gateway
  references, print toggles, maps) may stay closed: add it to `ROUTINE_COLLAPSED` with the reason,
  and give it a one-line description of what it holds
  (`test_collapsible_sections_open_when_they_hold_data`).
- Use `depends_on` only when a field cannot apply, and never on a section that a form tour points
  into. Empty read-only fields hide by themselves.
- Help never repeats the label (`test_help_never_repeats_the_label`). Inline help is 80 characters
  at most. For longer help, set `show_description_on_click` (the (i) icon). Section Break and Table
  help cannot hide, so it is 120 characters at most (`test_long_help_sits_behind_the_info_icon`).
  Put an example in `placeholder`.
- A Text, Long Text, Text Editor, HTML Editor, Markdown Editor or Code field on the first tab sets
  `max_height`, such as 12rem. Small Text is left out, because its box is only 150px
  (`test_first_tab_text_fields_have_a_max_height`). A Text Editor draws a 300px editor inside its
  box, so give it a `max_height` of 20rem or more. A smaller cap puts a scrolling box around a
  scrolling editor and cuts off the bottom of the editor.
- A form has 2 top-level custom buttons at most. Record actions go in the 'Actions' group and
  reports about the record in 'View' (the group argument of `add_custom_button`). Tours and rare or
  destructive items go in the '...' menu. Hide a button that cannot work yet.
- Group the Connections links. A group label never repeats a section label of the same form.
- Set `track_changes` on documents that staff edit, and `ignore_version` on automatic saves, but not
  on Counseling Case or Person Note: a Version row keeps the old text of a changed or deleted note,
  and a counselor who deletes a note expects it gone. Never set `timeline_field`, which shows nothing in Frappe 16.54 (`test_doctypes_set_no_timeline_field`).
  `track_views` stays on Person and Prayer Request only, where the 'viewed' rows are an audit of who
  read the record (`test_track_views_only_where_an_audit_is_needed`). A tracked doctype that links
  to a Person must lose that person's name and email from its Version rows when Remove Personal
  Data runs (`test_tracked_records_about_a_person_are_forgotten_with_them`). A Version row shows a
  changed Link to a Person as the person's name, not the ID. A record about one person goes in
  `privacy.RECORDS_ABOUT_THE_PERSON`, and anonymizing deletes its history. Any other tracked record
  that names the person keeps its history, and anonymizing writes Anonymized for their name and
  removes their email in it (`privacy.scrub_history`). Such a doctype needs a
  `PERSON_HISTORY_EXCEPTIONS` line that says so. A gap line there is a leak still to close in
  `church_people/privacy.py`. Reword or delete the line when you close the leak
  (`church_people/test_privacy_history.py` checks the lines by behavior).

### Child grids

Every `in_list_view` field of a child table sets `columns` from 1 to 12, which Frappe 16.54 draws as
60 to 600px. The column that identifies the row comes first and is the widest. A grid shows 5
columns at most and no Text, Long Text, Text Editor, HTML Editor, Markdown Editor or Code column. A
Check column has width 1 and a short label with no '?'. The value staff enter or read most (Amount
on Donation) stays in the first 300px, so it shows on a tablet. Show warning flags in the grid, such
as `is_bounced` on Email Address and `is_returned_mail` on Postal Address. A user's saved grid
columns win over these settings for that user (`test_grids_set_their_column_widths`). A child table
that only a Table MultiSelect uses has no grid, so these rules skip it.

### Sidebars and workspaces

These add to the rules in "Desk navigation".

- A sidebar starts with 'Home', then 5 to 8 daily items, each with its own icon, then folders. A
  folder is a Section Break with `indent`, `collapsible`, `keep_closed` and an icon. Its items set
  `child` and have no icon
  (`test_sections_are_closed_folders_with_icons_and_their_items_are_children`). Reports go at the
  end of their feature folder, and 'Setup' and 'Data' are closed folders at the end. With its
  folders closed, a sidebar shows 16 rows or fewer. A heading that stays open, such as Needs
  Attention on Summary, goes in `OPEN_SECTIONS` with the reason. A folder label differs from the
  label of every item above it in the sidebar. Frappe opens the folder of the active item by the
  first item with the folder's label, so a top-level 'Funds' link keeps the 'Funds' folder closed on
  arrival (`test_no_folder_shares_its_label_with_an_earlier_item`). A module with few pages (Study,
  Missions, Foundations and Web Site) lists its pages and reports at the top and has at most a Setup
  folder. Help lists each module's manual as an item, with the icon that the module has in the dock.
- A label is 24 characters at most, so the sidebar does not cut it off
  (`test_labels_fit_the_sidebar`). Every icon exists in a sprite that the desk loads
  (`test_every_icon_is_in_a_sprite_the_desk_loads`): sidebar items, sidebar header icons and dock
  icons. The desk loads Lucide from `lucide/icons.svg`, not from the older
  `public/icons/lucide.svg`, so an icon that is only in the old file, such as `book-marked`, draws
  nothing.
- Set `is_default_module` only on a Frappe doctype that churchit users need, and only once across
  all of churchit's sidebars. On a site with ERPNext, the claim sends that doctype to churchit's
  sidebar for every user. Two claims are settled by install order, and nothing tells you
  (`test_no_doctype_is_claimed_by_two_sidebar_items`). The Settings sidebar claims User, Role
  Profile and Data Import, and no other churchit sidebar item claims a doctype.
- Never add a URL item for a desk route, because Frappe opens every URL item in a new tab. A
  filtered list is a standard Report Builder report, because a filtered sidebar link saves its
  filters onto the plain list. A calendar is a workspace shortcut with `doc_view` Calendar
  (`test_no_url_item_opens_a_desk_route`). Frappe has no Map `doc_view`, so a map is a URL shortcut
  (see "Frappe behaviours worth knowing").
- A standard Report Builder report leaves the List view alone, but Frappe saves its filters as the
  doctype's plain Report view settings (`ListView.before_render`), so the Report view in the view
  switcher opens with them later. Report Builder filters cannot say 'before today': `<` with 'Today'
  compares text. The Report view keeps the first `order_by` key and adds the ID in the same
  direction (not for `name`, `creation` or `modified`), so write `order_by` that way, such as
  `` `tabFunction`.`start_date` asc, `tabFunction`.`name` asc ``. Another `order_by` shows 'Not
  Saved' each time the report opens. The Report view returns the filters that are not standard
  filter boxes first, then the standard boxes in field order, and shows 'Not Saved' when the saved
  order differs. A condition fills a box when its field is the title or an `in_standard_filter`
  field and it is `=` (or `like` on a non-Link), but not `= 0` on a Check. So save the `=`
  conditions on such fields last. Save a docstatus value as text, such as "0", because the filter
  box drops the number 0 and the report would list every record. A doctype with no `status` field
  also needs `docstatus` in `column_widths`. `church_setup/test_queue_reports.py` runs every
  standard Report Builder report, so a renamed field breaks the test and not the queue. It checks
  the order and the text, and that a Report shortcut to a Report Builder report names the report's
  doctype in `report_ref_doctype`, which the desk builds the route from.
- A module workspace has, in this order: the verse, the onboarding, shortcuts, number cards (6 at
  most) and 1 to 4 charts. Up to 6 shortcuts are attention shortcuts, which open a list, a calendar
  or a report of the work that waits. Up to 3 more open a page of the module, such as the Rolodex,
  the Check-In Station or a map (a Page or URL shortcut). It has no link cards and no quick lists,
  because the sidebar is the menu (`test_module_workspaces_show_blocks_in_the_standard_order`,
  `test_module_workspaces_stay_within_their_caps`, `test_module_workspaces_have_no_link_cards`,
  `test_module_workspaces_have_no_quick_lists`).
  Summary keeps its own order: verse, module grid, onboarding, Needs Attention, At a Glance, Trends.
- A shortcut color comes from Frappe's color list: Red for urgent or overdue, Orange for waiting,
  Blue for information (`test_shortcut_colors_come_from_frappes_list`). A count shortcut saves its
  filter onto the list, so give a count only to a queue whose filter is the list's own default
  filter. A queue with no default filter gets one first
  (`test_count_shortcuts_use_the_lists_default_filter`). Summary's My Assignments is the exception:
  ToDo is Frappe's list, and a report cannot filter on the current user. Never put a count on
  Person or Family, because the count includes every church
  (`test_people_and_families_have_no_count_shortcut`). A calendar is a URL shortcut, such as
  Summary's Church Calendar to `/desk/function/view/calendar`, which opens in a new tab with no
  count. A DocType shortcut always shows a count and saves its filter onto the calendar, which then
  hides the other weeks until the user clears it (`test_no_doctype_shortcut_opens_a_calendar`). A
  `stats_filter` may use `frappe.session.user`. Write a relative date as `Timespan`, such as 'next 7
  days', not as a `frappe.datetime` call, because a saved filter keeps the date it was saved with
  (`test_conditions_with_javascript_dates_are_read` reads both).
- Color a number card only when it asks for action. Set `show_percentage_stats` only on a running
  total, such as all giving or all expenses. Frappe repeats the card's filter with `creation`
  before one interval ago and compares the two totals, so the figure means nothing on a card with a
  date window, such as the collections of the last 7 days, or on a plain inventory count.
- A click on a Document Type number card puts the card's filter on the list it opens, and the list
  saves it, as for a count shortcut. So a card on a workspace has no filter, or the list's own
  default filter (`test_number_cards_use_the_lists_default_filter`). A filtered figure, such as the
  giving of this month, is a Custom card over a saved Report Builder list: its method calls
  `dashboard.total_of_saved_list`, which counts or sums what the list shows and opens that list, as
  Summary's At a Glance cards do. A Report card cannot help: `query_report.run` returns nothing for
  a Report Builder report.
- Each dock entry has its own Lucide icon, and the dock lists the modules in order of weekly use.

### Frappe features that churchit does not use

- Fold, because it does not work in a tabbed form.
- DocType Layout, because it is a second layout to keep and a sidebar cannot open it.
- List View Settings and List Filter layouts as defaults, because they cannot be the default for
  every user.
- DocType Actions, because they have no condition. Use `add_custom_button`.
- New Custom HTML Blocks. The `ModuleShortcuts` block on Summary stays.

### Before and after screenshots

Each change to a list, form, sidebar or workspace also updates the Manual, moves the form tour steps
into the new field order (`test_tour_steps_follow_the_order_of_the_form`), bumps `modified` in each
JSON file you edit by hand, and gets before and after screenshots:

1. On the dev site (`churchit.localhost`, which has the sample data), clear the saved filters and
   sort of the lists you change. Run `clear_list_filters_and_sort` in a console and commit.
2. Pick one sample record for each form, and use the same records for both sets of shots.
3. Take the before shots as `mary.johnson@example.com` with the run-churchit driver
   (`.claude/skills/run-churchit/driver.py`). Take each page at 1440x1000 (`viewport 1440 1000`
   before `nav`) and again with `--device mobile` (390x844). Name them `<page>-desktop` and
   `<page>-mobile`.
4. Make the change and migrate. Take the after shots of the same pages and records in the same way.
5. Delete each record that you made for the shots.

## Documentation obligations

The `Manual: <Module>` workspaces are the in-app user documentation, not developer notes. Update the
matching manual in the same change as any user-facing behaviour, and bump its `modified` timestamp
(see "Frappe behaviours worth knowing"). `Manual: Foundations` holds the multi-church explanation.
`docs/build_docs.py` renders these manuals into the documentation pages of the churchit.app website. It reads them through `churchit/manuals.py`, which also gives them to Flow as the Churchit Manual knowledge.

Write the manuals for a church volunteer or secretary, not for a developer. Say what to click and
what happens, name the doctype the way its form does (a Function, not an "event record"), and keep
one name for one thing across every manual. Explain a term the first time a manual uses it. Leave
class names, hook names, field types and file paths out: they belong in this file or in a docstring.
A link in a manual is a site path such as `/app/person`, never `http://app/person`;
`test_workspace_hygiene` checks that each desk link in a manual opens.

## House style

**Never use an em dash or an en dash.** Not in code, comments, docstrings, commit messages, manuals,
form tours, notifications, print formats, the README or the docs site. This is a hard rule, and it
applies to the escaped forms too, whether written as an HTML entity or a unicode escape
(U+2014 and U+2013). `churchit/tests/test_house_style.py` checks the file types it lists in
`SCANNED`.

Rewrite the sentence rather than swapping the character for a hyphen, which usually reads worse than
the punctuation the sentence actually wants:

- An aside becomes a comma pair, or parentheses: "Reports run raw, bypassing permissions entirely."
- A sharp break becomes a full stop or a semicolon: "Do not remove that. Replace it."
- A definition or expansion becomes a colon: "One rule matters most: `get_all` is not scoped."
- A range becomes "to": "10 to 20 rows", never "10-20 rows".

A hyphen is fine where a hyphen belongs, in a compound like `church-scoped` or `multi-church`.

## People events and history

`church_people/events.py` emits the people events from `Person.on_update`; its docstring lists them
and shows how an app subscribes. Install, patches and migrate emit nothing; data import does. A
`frappe.db.set_value` skips `on_update`, so it emits nothing.

Membership history is Milestone rows written by `membership.record_changes` for
`membership.TRACKED_FIELDS`, read by `membership.changed_between` and the Membership Changes report.
Do not add a Frappe Milestone Tracker on Person: Frappe allows one tracker per doctype, and clearing
the tracked field fails the save.

`church_people/history.py` adds a person's visits, care requests, life events with a full date,
member transfers and connection cards to the Person timeline as short cards, the 20 newest of each
kind. It reads each kind with `frappe.get_list` in `get_readable_rows`, so roles, church and User
Permissions apply, and Frappe leaves out fields above the reader's permission level. A filter or
sort on such a field raises, so a kind whose filter or date field the reader may not read shows
nothing. `get_list` does not check the permission level of the Person `life_events` table, so
`get_life_event_cards` checks it with the Person's own `get_permlevel_access`, as the form does.
`get_list` runs no `has_permission` hook per record, so a doctype with one is not added there
without a check on each row (`test_history` fails). Counseling Case and Background Check never go
on the timeline. A card shows no free text, only short facts and a link.

## Person summary fields and smart lists

A smart list is a saved Report Builder report on Person, so Frappe scopes and refreshes it. Person
carries read-only summary fields (attendance, groups, serving, giving, care, membership dates) from
`church_people/summaries/`, whose docstring is the contract. To add a figure, add a read-only Person
field and an area module; do not add a hook.

A save, cancel or delete adds its people with `summaries.queue_refresh`. Each transaction queues one
refresh job for all its people after the commit, and a rollback queues none. Queue a summary refresh
only through `queue_refresh`; call `summaries.refresh` directly only where the figures must be right
before the request ends, as `Person.merge` does. A test reads what a change queues with
`queued_people` in `summaries/test_serving.py`.

An area counts only the person's own church's records and shared ones (`summaries.same_church`). The
directory is shared, so a stored figure would otherwise show one church what a person did at
another. Giving and care figures carry permlevels 2 and 3 for the same reason, and
`Person.get_permlevel_access` drops both on single-document reads when the reader cannot see the
person's church. Lists, Report Builder and exports apply permlevels by role only. That gap is
accepted for now: while the directory is shared, another church's finance or care role reads and
filters these figures in lists, smart lists and exports, and Check-In, People Editor and Church
Manager read `medical_notes` (permlevel 1) on every person. Person Versions still record
`medical_notes` and the other fields above permlevel 0, so every Person reader sees those changes in
the timeline. Only a user who sees both churches can put a person into another church's Family. A
church that must keep them apart ticks Keep People and Families Private to Each Church, which
leaves the addresses readable (see "Roles"). A new figure that counts one church's records inherits
the gap; say so in the manuals.

`summaries.keep_stored_values` (in `Person._validate_links`, before Frappe's link check) puts the
stored figures and summary rows back on every save, because a refresh and a delete leave `modified`
alone. A form opened before a group or position was deleted therefore still saves. Never set a
summary field through a Person save.

A summary Table MultiSelect names other records, so add its child doctype to
`ignore_links_on_delete` in `hooks.py`: otherwise Frappe refuses to delete a record that a stored
row names. `summaries.delete_rows_naming` deletes those rows with the record, in the same
transaction, because a row left for the queued refresh fails every save of its person on Frappe's
link check. Like groups, the serving area leaves out the positions of an Inactive Ministry.

A smart list can also be a Custom Report (menu > Save) of a script report named in
`smart_lists.REPORT_LISTS`, such as Attendance Count; `smart_lists.get_people` runs it with its
saved filters and then applies the church and the living filter. A new list of that kind goes in
`REPORT_LISTS`, and its rows carry the person in `person`. Smart list pickers use
`smart_lists.search_smart_lists`. A filter on a Person child table joins one row per match, so
`get_people` and `dashboard.count_in_readers_churches` count each person once.

The standard lists ship as Report Builder JSON under `church_people/report/`. The Report view runs
the Person `listview_settings` too, so every saved list gets the Person list's Actions, and the
Report view opens on Status = Active, which Save As keeps in a new list unless the user clears it
first (Manual: People says so). The server side of the Actions, `church_people/list_actions.py`,
takes names from the browser, so it checks the right on every record: `email` to read addresses,
`write` to change them.

Person stores `primary_email` and `primary_phone`, copied from its contact tables by
`derived.sync_derived` on every save, because a list column, a preview and a Link search cannot read
a child table. Never set them yourself. Code that changes Email Address or Phone Number rows with
`frappe.db` leaves them stale until the person is saved again, so save the person after it, as a
merge does. Data Import matches a Person column headed Email or Phone to these fields, so during an
import `Person.take_imported_email_and_phone` makes such a value the primary row of its table before
the save copies it back. Both are in `privacy.PERSONAL_FIELDS`.

`Family.member_count` is stored by `Family.validate` from the Members table, so the Family list and
preview can show it. Change a household's members only by saving the Family
(`Person.sync_family_members`, `remove_from_family` and the merges do). A direct write to the Family
Members table leaves the count wrong. The patch `fill_family_member_counts` backfills it.

## Engagement, pathways, map and retention

A Pathway step is a smart list (`Pathway.get_steps_done` reads it through `smart_lists.get_people`).
A new way to judge a step must come in as a smart list, not as code in the Pathway Progress report.

`get_timeline_data` in `doctype/person/person.py` feeds the form heatmap through Frappe's
`get_open_count`, which `churchit.connections` overrides. Frappe calls it on the doctype's module,
so it stays a module-level function. It reads Function attendance through
`get_list` and returns `{}` when the reader cannot read Function, because an error there would break
the Connections counts.

Only `geocoding.geocode` writes Address `latitude` and `longitude`, with `db_set`: a save would
queue another lookup through Address `on_update`. Every Nominatim request goes through
`geocoding.get_coordinates`, which holds a bench-wide file lock because Nominatim allows one request
a second. A form asks the server for a map pin, as the Location and Missionary forms do, and never
calls Nominatim from the browser. People Settings `look_up_addresses` turns all of it off; check
`geocoding.is_address_lookup_on()` before anything that sends address text. Custom fields sync
after the patches, so a patch that needs one syncs its customization file first, as
`queue_address_coordinates` does.

An Address shows its street. The Address Property Setters in
`church_customizations/custom/address.json` set `title_field` to `address_line1`,
`show_title_field_in_link` and `search_fields` "address_line1, city" (`test_address_customization`).
They apply to ERPNext's addresses on a shared site too, and every migrate puts them back over a
site's own Customize Form choice. Address keeps List as its default view, because ERPNext uses the
same doctype; the map opens from the 'Map of Addresses' shortcut. Address also keeps its ID
column, because the ID (address title and type) says whose address it is, and hiding it would need a
list script that also changes ERPNext's Address list. `test_lists_with_a_title_hide_the_id` reads
only churchit's doctypes, so it does not check Address.

`privacy.get_due_query` is the one rule for whose data the daily retention job removes; the
Personal Data Due for Removal report scopes the same query.

## Duplicates, merging and anonymizing

`church_people/matching.find_matches` is the one matcher, and its weights are in `WEIGHTS`. It reads
every church unless it is given one, so anything that shows a match to a user must first filter it
through `frappe.get_list`, as `get_possible_matches` does. Match or search phones on Phone Number
`digits` (filled by `contacts.validate_contact_tables`), never on `phone_number`.

A merge is Frappe's own rename with merge (see `merge.py`). Frappe repoints every Link and Dynamic
Link but not a Data field that stores a Person ID (`Milestone.reference_name`), so
`Person.after_rename` moves those; a new Data field holding a Person ID needs the same. A new child
table that lists each person once goes in `person_data_map.ROSTERS`. A new Person table a merge
carries over goes in `MERGED_TABLES` in `doctype/person/person.py`. `person_data_map.linked_records`
finds every record naming a person from field metadata; use it instead of a list of doctypes.
Both ways of merging delete the removed record's Deleted Document when the merge commits: Frappe
deletes the record after every hook, so Person and Family `after_rename` call
`merge.drop_deleted_document`. Possible Duplicate pairs go with `delete_permanently`
(`duplicates.drop_pairs`, `matching.resolve_merged`).
A merge can also take the removed record's value of each field the user chooses
(`take_from_removed`): the kept record is saved with those values before the rename, as the user, so
a field must be in `merge.choosable_fields` (typed, not virtual, not the church, of a permlevel the
user may write). `merge.get_merge_choices` lists the fields where two people differ, and
`public/js/merge_choices.js` shows them as radios in the Person and Possible Duplicate merge
dialogs.

Anonymizing (`privacy.anonymize_person`) keeps the Person, clears `PERSONAL_FIELDS` and empties
`PERSONAL_TABLES`, so a new Person field or table holding personal data goes in one of them. The
first name becomes Anonymized and the last name stays, so the record sorts among its family name in
the People list; copies of the full name on other records still become Anonymized. A title that a
record builds again from the Person on its next save, such as a Prayer's or an Alms Request's, then
shows 'Anonymized' and the kept last name, as the Person does. A new
doctype about one person (its subject, not a caregiver or other role) goes in
`privacy.PERSONAL_DOCTYPES` when anonymizing should delete it, as for Person Note and Connection
Card. Otherwise it goes in `privacy.RECORDS_ABOUT_THE_PERSON`, and anonymizing deletes its history,
comments and attachments and blanks its messages.

Anonymizing also scrubs the change history of every other record that names the person
(`privacy.scrub_history`). It reads these records before the person leaves their family, spouse and
relatives. The copies of the person's name become Anonymized and their email addresses go. The
family's name loses their first name, in the history of the family and in the text and history of
the records that name it, such as the other members and an Alms Request for the family. A family
left with no one in it becomes Anonymized, and so does its name on those records. A record that no
longer names the person, such as a ministry with a new coordinator, keeps the person's name in its
history.

Anonymizing also clears every field added with Customize Form, on the Person and on an anonymized
Family (`privacy.blank_church_fields`), because Churchit cannot tell which of them are personal. A
mandatory one is cleared too, but the state field of an active Workflow stays, because a blank state
is a move back to the first state, which the workflow refuses. Church fields are site-wide: only a
System Manager adds them, after the shipped `church_fields_tab` tab, and Churchit adds no code to
sync fields.

A relationship to someone in another household is one `Person Relationship` row on the person who
records it, never a mirror row: the other person sees it in Connections through the Person `links`
entry on `person`. `Person.validate_relationships` refuses the person themselves, a member of their
own Family (the roster owns that) and, in a private directory, another church's person. After a
merge `remove_repeated_relationships` drops the rows that name the kept person on their own record
and repeats on others, and `remove_relationships_with` deletes every row that names a person when
they are anonymized or deleted. Deleting a person also clears the Shared From of the emails and
phones other people share from them (`contacts.stop_sharing_from`, also used by anonymizing), so
Frappe does not refuse the delete.

Custom questions go through `churchit/questions.py`. A doctype that asks a Question Set keeps the
answers in a Question Answer table and writes them only with `questions.set_answers`, after
`validate_answers`. Name the person who answers in a Link field of the owner doctype itself:
anonymizing clears the Question Answer tables and the change history of each record that names the
person in its own field (`clear_answers`), and a record that names the person only in a table row (one
attendee of a group) keeps its answers, which are the group's. Function Sign-Up is the exception:
each answer names its attendee row in the hidden `attendee` column, and anonymizing deletes the
answers of the attendee rows that name the person, with that sign-up's change history, and blanks the
registrant name, email and phone on the person's own sign-ups (`privacy.forget_sign_up_details`). A
guest sign-up left unlinked with one of the person's email addresses counts as their own
(`forget_unlinked_sign_ups`). A merge keeps the answers, because they stay on their record. Render the questions with `churchit.questions.render(wrapper, fields)` from
`questions.get_fields`; do not add conditional questions, `depends_on`, Web Form `eval:` text or
stored JSON.

Frappe logs list and Report Builder exports, prints and PDFs. A new export or print path for
personal data must call `make_access_log`, as the Church Directory PDF and `churchit/exports.py` do.

## People imports

Imports run through Frappe's Data Import. Each source is a virtual DocType in Church People whose
fields are the export's columns, labelled exactly as the export heads them, with Churchit's
fieldnames. To add a source, add such a DocType (and its `GLOBAL_DOCTYPES` entry), a
`SourceProvider` subclass in `church_people/imports/` and one `data_import_providers` line in
hooks.py. A person is found again by `legacy_system` and `legacy_id`, and a family by its household
ID, only in the importer's churches.

While `frappe.flags.in_import` is set, Frappe applies no field defaults and skips Select
validation, so a record made from a Person save during an import must set its mandatory fields
itself. Frappe reads `import_labels` aliases only for child-table fields, so a parent column matches
only its label, its translated label, its fieldname or `Label (fieldname)`.

Giving history imports through the virtual DocType Giving Import in Church Finances. Its provider,
`church_finances/imports/giving.GivingImportProvider`, subclasses Frappe's `ImportProvider`
directly, because a row makes a Donation, not a Person. It finds the giver by `legacy_system` and
`legacy_id`, else by the only holder of the email in the importer's churches, and adds the Donation
(Gift ID in `legacy_id`) to the draft Collection of the row's `import_batch` and date. It refuses a
Gift ID already on a Collection that is not cancelled, and a row that matches an Online Donation the
gateway charged. Finance submits the drafts, so nothing reaches the funds before a person checks it.
The Donation Acknowledgment notification skips a Collection with an `import_batch`. An import
DocType keeps no records, so its list script sends the user to the records it made. It does that in
`listview_settings.refresh` with `frappe.route_flags.replace_route`, never in `onload`: in `onload`
the import list takes the route options before the target list can use them.

## Person Notes

A Person Note's category decides who reads it (`notes.has_note_permission` and
`notes.note_query_conditions`). Church scoping does not cover categories, so read notes only with
`frappe.get_list`, or `get_doc` plus a permission check, never `get_all` or `qb`, even for a person
the reader can see. In Frappe a share overrides both hooks, so Person Note has no `share` right: do
not add one, and do not assign notes. Person Note does not track changes, because every System
Manager can read Version records. A Person's timeline does not show records linked to the person by
itself. Notes (`notes.get_timeline_notes`) and visits, care requests, dated life events, member
transfers and connection cards (`history.get_timeline_content`) reach it through
`additional_timeline_content`.

`PersonNote.validate` checks write on the stored note (see "A has_permission hook sees the edited
document"). Only `church_access.has_every_church` users add or delete a Note Category or change its
roles or Private. `tests/test_permission_hygiene.py` checks the reads, the share right and Track
Changes.

The shipped categories are General, Pastoral Care and Benevolence
(`note_category.create_note_categories`). A patch that adds one passes its name, so it does not
bring back a category a church deleted. Alms Request case notes are Benevolence notes on the
recipient, or on a Family's primary contact (`alms_request.js`). The form shows the Case Notes
item in the View menu and the Add Case Note item in the Actions menu from
`__onload.can_read_case_notes` and `can_add_case_notes`, which `AlmsRequest.onload` takes from the
rights on an unsaved Benevolence note. Do not decide them from the Person Note DocType rights in JS:
Church Staff holds those, but not the Benevolence category.

## Member portal

A portal member reaches their own Person, and an Adult also reads and writes the living Children of
their household who are under People Settings' adult age or of unknown age
(`household.get_editable_children`), through the Person `has_permission` hook and
`person_query_conditions`. To ask "may this member edit X", call
`frappe.has_permission("Person", "write", doc=X)`; do not compare `Person.user`. A member reads and
lists only their own Family, only its Adults write it, and `refuse_member_edits_beyond_photo` (first
in `Family.validate`) limits them to the photo. It steps aside for `ignore_permissions` saves, which
is how a Person keeps the roster, so never save a Family with `ignore_permissions` on values a member
sent. `/household` offers pre check-in to the people the member may edit.

An Adult adds a child on `/household` through `member_access.add_household_child`, the one way a
member adds a Person. It takes a first and last name, a birthday under People Settings' adult age
and a gender, and nothing else. The child joins the Adult's Family and church as a Visitor with
source Portal who shares nothing, `mark_as_child` makes the roster row Child and Son or Daughter,
and the matcher opens Possible Duplicates. The insert sets `flags.from_household_page`, which
`refuse_member_edits_beyond_personal_details` lets through. Do not set that flag anywhere else.

`Person.birthday` is virtual: a value set on a save rewrites the first Birth life event
(`sync_birthday`, before `sync_derived`). Read birthdays from `birth_month`, `birth_day` and
`birth_date`, never from `birthday`.

The defaults of `share_email`, `share_phone`, `share_address` and `share_birthday` are site-local
Property Setters that People Settings `on_update` writes. A Single field that migrate stores without
a save writes none, so a new People Settings default that drives a Person default needs a patch that
calls `set_share_defaults`. A People Settings field added after a site first saved its settings reads
as empty, not as its default: re-add `store_new_people_settings_defaults` to patches.txt (with a date
comment) when you add one. People added for someone who never saw the choice (a card guest, the
people with them, a walk-in at the Check-In Station, a portal sign-in) set all four to 0.

`/directory` lists only active people whose Membership is not Visitor or Contact
(`directory_filters`), and shows the list only to a viewer who passes the same rule, hidden or not;
anyone else sees a note. It shows only public photos. The Member Directory portal menu row's
`enabled` follows `member_directory` (`sync_directory_menu_item`); do not set it by hand.

`accounts.link_portal_user` (on_session_creation) sets `Person.user` with `db_set` and then calls
`sync_church_permission`, because the member guard refuses a member's change to Portal User. A
Person it adds carries `flags.from_portal_login`, which `refuse_member_edits_beyond_personal_details`
lets through. Only an own primary email counts; a row with Shared From does not. A failure is logged
and never stops the sign-in.

A login that a user links by hand, in Portal User or through Invite to Portal, must belong to no
other Person and hold only churches the user can see (`Person.refuse_linking_another_login`). The
app's own links save with `ignore_permissions` and skip that check, so never link a login a user
sent with `ignore_permissions`.

A guest key web form (Update Your Details) may not have a Link field, or a table with Link columns,
unless Guest can read the linked doctype: Frappe refuses to save or render it otherwise.
`details_link.close_details_request` (Web Form Request `validate`) keeps a details link to its one
Person and one use; Frappe alone lets a key add records and reopen its record until it expires.
Never put a request key in a Communication or Comment: anyone who reads the Person could use it.

`Person.team_calendar_key` is at permlevel 4 (System Manager only). Code reads and writes it with
`frappe.db`; do not read it through a document a user sees.

A person leads a group when their Group Member row has a Group Role with `is_leader` (Leads the
Group). Ask only `church_people/group_leaders.py`: `get_leaders`, `is_group_leader`,
`get_led_groups` and `require_leader`, which returns the session's Person or raises PermissionError
for a Guest, a user with no Person and a non-leader. They live outside `group.py` so that
`group_meetings.py` imports them without a cycle.

A join request is a Group Join Request, never a Group Member row: Person summaries, a Church Email
to a group and the directory read every member row. Only `group_api.join_group` makes one and only
`decide_join_request` decides one; staff have no create on it and add a member on the Group form.
Both lock the Group row first, then the request row (`for_update`), so a join and a decision cannot
deadlock and two decisions cannot both pass.
Approval appends the Group Member and saves the Group with `ignore_permissions`, so `Group.validate`
applies the group's requirements. A full or closed group refuses a join: `Group.is_full` and
`is_enrollment_open` work out `capacity` and `close_enrollment_on` when read, and no job stores
them. Members have no read on Group Join Request; a leader sees requests through
`get_open_join_requests`.

Group File is the member-only file store of a group. A portal member reads and lists only the files
of their own groups (`member_access.has_group_file_permission`, `group_file_query_conditions`), and
only a leader of the group adds one (`GroupFile.validate`, which runs under the web form's
`ignore_permissions` too). Its file must be private and one the user can open. File's
`before_insert` has written the content before a `doc_events` hook runs, so
`make_group_files_private` refuses a public file instead of flipping the flag, and
`GroupFile.validate` refuses a public URL, or a private file the user cannot open, that the web form
attached with `set_value`. The Attach field is `attached_file`, not `file`: Frappe's web form
uploads again for a saved result with a `file` key.

The Room Request web form (`/room-request`, `church_operations/web_form/room_request/`, Book a Room
in the portal menu) is members-only. `RoomBooking.set_portal_requester` sets the requester to
`session_person()` for a portal member or anyone on a web form, under the form's
`ignore_permissions` too, and refuses a login with no Person and a form edit of another person's
booking. `refuse_a_room_outside_the_members_church` refuses a room that `get_bookable_rooms()` does
not offer: the bookable rooms of the member's church and the shared ones, less each room whose
Question Set has a required question, the same read that fills the form's room options
(`allow_read_on_all_link_options` is 0). The form has no status or requester
field, because Frappe's `accept` sets every web form field from the browser. Its list reads with
`get_list` (Church User has `if_owner` read), and `get_list_context` filters on the requester and
leaves out Blocked times. The form asks no room questions, so it does not offer a room with a
required question; staff book that room. A member books no equipment:
`refuse_assets_that_cannot_be_booked` refuses an asset that a member, or anyone on a web form,
adds (Church User has no permission on Church Asset).

## Function sign-ups

Function Sign-Up `status`, `hold_expires_on`, `approved_by`, `amount_paid` and `payment_status` are
read only, but REST accepts them, so `restore_protected_fields` puts back the stored values unless
`flags.set_by_code` is set. Code that changes them sets the flag and saves the document, never
`db_set`, so attendance, the emails and the follow-up cards follow the change. `amount_due` and
`discount` are worked out on every save by `church_ministries/sign_up_amounts.py`, the one place for
sign-up money: the Function's own selection and item prices, less the largest discount that applies.
Codes match without case on the server only, and no page sends the discount rows. A Freely Given
discount applies to every sign-up; `is_freely_given` says when one takes the whole price off, and a
Function freely given with no end date needs no Sign-Up Fund. A change of the Function's prices or
discounts queues `settle_payment_holds`, which confirms each payment hold that now owes nothing; a
payment that arrives for a Function with no fund alerts Finance. The sign-up window
(`sign_ups_open_on`, `sign_ups_close_on`) is read when asked (`is_open_for_sign_up`,
`is_in_sign_up_window`), with no job; the desk is never refused.

Seats are the Function's `capacity` and each Selection's `capacity` (0 is no limit); a limited
Sign-Up Item's `quantity_needed` caps that item. A sign-up holds seats while Confirmed, or Pending
with an empty hold (waiting for approval) or a hold not yet passed (waiting for payment):
`holds_seats` is that rule, and the item totals use it too. Every change to seats takes the Function
row lock first (`get_seat_limits`) and then counts with a locking read (`get_seats_taken`), because
under REPEATABLE READ a plain count answers from an older snapshot. A new party that does not fit is
Waitlisted as a whole. Only `promote_waitlist` moves a party on, oldest first among those that fit,
after a cancel, a decline, a delete, a smaller party, a released hold (`release_expired_holds`, every
5 minutes) or a changed capacity (a job after the commit). It sends nothing itself. Each attendee
Person has a Signed-Up attendance row while the sign-up is Confirmed. A paid sign-up cannot grow into
a balance or move to another Function.

`approve` and `decline` need a role in `SIGN_UP_APPROVERS` as well as write, and
`record_offline_payment` and `record_refund` need `payments.PAYMENT_RECORDERS`, because a registrant
holds `if_owner` write on their own sign-up. Each takes the Function lock before the sign-up row.

A guest sign-up has no `person`. `function_sign_up.link_registrant` runs after the commit as the
guest, locks the Function and then the sign-up, and links the one strong match or adds a Visitor
(source Sign-Up) through `matching.find_or_add_person`, the one matcher-and-adder that Connection
Cards and Form Responses use too. When that Person is already on another live sign-up of the
Function, it leaves `person` empty and comments with that sign-up.

Emails that answer the registrant's own request (the Sign-Up Confirmation with its `.ics` and the
Sign-Up Payment Due) go through `FunctionSignUp.send_registrant_email`: to the Person's primary
email, or to the sign-up's `email` only while it has no Person, with no consent check, and only when
an outgoing account exists. Reminders go through `send()` (see "Church Emails, consent and
bounces"). The event comes from `get_function_calendar`, whose UID is the Function name, as in the
public calendar feed.

Sign-ups of a shared Function have an empty church, so every church sees them.

Function Sign-Up Item is one grid for two parents. Its JSON lists only the columns both forms show
(Item, Quantity Needed, Quantity Signed Up). `function.js` adds Price and `function_sign_up.js` adds
My Quantity with `update_docfield_property`, and each calls `grid.reset_grid()`, because the grid
keeps the columns it drew first. Frappe copies a child table's docfields for each parent document,
so the override on one form does not reach the other.

## Room bookings

Room Booking `status` stores Requested, Approved, Denied, Cancelled, Completed, Blocked and
Conflict. Do not rename them, and append a new value at the end.

`Room.get_approvers` and `Room.is_approver` are the one rule for who approves. The users in the
room's Approvers table approve while they hold Church Staff or Church Manager; when the table is
empty, the Church Managers and System Managers do. Each needs `has_church_access` to the room's
church. A new booking on a gated room is Approved when an approver of the room makes it, never on a
write with `ignore_permissions` (the recurrence copy stays Requested or becomes Conflict). A move of
an Approved booking by a user who is not an approver sends it back to Requested.

A booking that waits (Requested or Conflict) is assigned to the approvers with `assign_to`, and the
assignment closes when the status or the room changes (`update_approver_assignments`). That ToDo is
the alert; add no second email. The maker hears of the decision from the Room Booking Decided
Notification (see "Notifications"). The form shows the decision buttons from `__onload.is_approver`,
not from the assignment.

| Status | Who sets it |
| --- | --- |
| Requested | A new booking on a gated room, or a move of an Approved one by a user who is not an approver. |
| Approved | A new booking on an open room or by an approver, a booking of equipment only, `approve`, `resolve_conflict`. |
| Denied | `deny`, `resolve_conflict("keep")`, and a Blocked save over a Requested or Conflict booking. On a gated room, `validate_approver` refuses any other save to Denied, or out of Denied to a status other than Cancelled, by a user who is not an approver. |
| Cancelled | A user who may write the booking. |
| Completed | A user who may write the booking, and `check_in`. |
| Blocked | Only an approver of the room (`validate_blocked`), with a room and no requester. Changing, releasing or deleting it (`on_trash`) needs an approver too. Every other status needs a requester (`refuse_a_request_with_no_requester`, because Frappe checks `mandatory_depends_on` only in the form). |
| Conflict | A clash saved with `request_anyway`, unless it clashes with a Blocked time. |

`approve`, `deny` and `resolve_conflict` are POST doc methods. Each checks the role
(`frappe.only_for`), reloads, checks read and `is_approver`, then saves with
`save(ignore_permissions=True)` (`set_booking_values` for the other bookings), never `db_set`, so
`validate`, the assignments and the Notification run. `resolve_conflict("keep")` denies the
Requested and Conflict bookings it clashes with, except those that both share the room, and approves
this one; an Approved or Blocked booking that still clashes refuses it. "share" ticks Can Share Room
on each clashing booking that is not Blocked and approves this one.

`RoomBooking.is_clash` decides a clash: a Blocked save clashes only with an Approved booking, a
stored Blocked booking clashes with every request, a Conflict booking holds no room time, and two
bookings with Can Share Room do not clash. A clash message names bookings only through
`describe_clashes`, from (name, church) pairs, which counts but does not name a booking whose church
the user cannot access. A clash read crosses churches with a `# church-scope:` reason, under locks
so two saves at once cannot both pass. Frappe locks a booking's own row before `validate`, so
`RoomBooking.load_doc_before_save` first calls `lock_room_and_assets`: the Room row, then each
Church Asset row in name order. Two saves that share a room or an asset then wait in turn and do not
deadlock; `resolve_conflict` takes the same locks. Under them, `check_conflicts`
(`get_room_clashes`) and `check_asset_conflicts` (`get_equipment_clashes`, from Room Booking Asset)
each make one locking read. The indexes on Room Booking `room` and Room Booking Asset `asset` keep
each read to the rows of one room or one asset; without them two saves of other bookings deadlock.
Take a new lock for a booking save only in `lock_room_and_assets`, and run the race tests in
`test_room_booking.py`, `test_room_booking_assets.py` and `test_room_booking_loans.py` again after
you change a clash read or one of these indexes.

On the desk form the clash message also says to tick Request Anyway on the Room Booking form. It
does not on the Room Request web form, for a portal member, on a save with `ignore_permissions`
(decisions and recurrence copies) or for a clash with a Blocked time, where Request Anyway cannot
help. The Function form's Book a Room dialog gets the message too and has no such box.

A booking reserves bookable Church Assets in its `assets` table (Room Booking Asset, labelled
Equipment), with or without a room. A booking with no room is never gated and takes its church from
`ensure_church`. A booking of a shared room judges its equipment against `shared_by_church`, the
church that made it, so a recurrence copy that runs as Administrator keeps it. An equipment clash
always refuses: Requested, Approved and Conflict bookings hold their equipment, Blocked ones do
not.

A loan is an Approved Room Booking with `assets` rows and normally no room; add no single asset
field. `check_out` and `check_in` are POST doc methods for Church Manager and System Manager
(`frappe.only_for(APPROVER_ROLES)`, reload, `check_permission("write")`, then `save()`). `check_out`
sets `checked_out_on` once, on an Approved booking with equipment. `check_in` sets `returned_on` and
Completed, once, after a check out. Only these two set the loan times:
`refuse_a_loan_recorded_by_hand` refuses any other save that sets, changes or clears them (except
under `ignore_permissions`), because read only on the form is not checked on the server.
`refuse_equipment_still_on_loan` runs in `validate` under the Church Asset locks of
`lock_room_and_assets`, and refuses equipment that another booking has out and has not returned,
also after that booking's end. Completed bookings hold no room and no equipment, so
`check_conflicts` and `check_asset_conflicts` skip them.

`setup` is text that `validate_setup` checks against the room's Room Setup rows when the setup or
the room changes, not a Link to the child table. A booking asks its room's Question Set
(`set_room_answers`); the desk form reads the fields from the GET `room_booking.get_room_questions`,
which checks read on the Room. A saved booking keeps its answer rows while its room and answers do
not change, so a decision never asks new questions; after a change of room, answers to another set
are dropped. A Blocked booking asks nothing. A Room names only a Question Set of its church or a
shared one (`Room.refuse_another_churches_question_set`).

Room Booking opens on its calendar (`/desk/room-booking/view/calendar`): `default_view` is
Calendar, without `force_re_route_to_default_view`, so the list stays in the view switcher, and Room
Bookings in the Operations sidebar opens the calendar. `room_booking_list.js` hides Denied and
Cancelled bookings by default, and the calendar view extends the list view, so it starts with the
same filter. Both read through `get_list`. Do not narrow that filter to Requested: the calendar
would lose the approved bookings. `room_booking_calendar.js` colors each booking from the DocType
`states` and orders a day by start time, because Frappe orders a day's events by the list sort,
which is newest first. The Room Usage report scopes Room Booking with `scoped`, so a booking of a
shared room shows for every church, as in the list.

## Church tasks and work orders

Church Task has no assignee field: Frappe's Assign To (ToDo) owns it. `church_task.on_assignment`
(ToDo `after_insert`) refuses a user without write on the task, sets an Open task to Assigned with a
real save and dates the ToDo from `due_date`. `church_task.refuse_moved_assignment` (ToDo
`validate`) asks for the same write when a ToDo is moved onto a Church Task, because each assignee
gets the task's reminder. `ChurchTask.on_update` moves open ToDo dates with `frappe.db.set_value`
and closes every assignment when the task is Completed. Never save or insert a ToDo from the task's
`on_update`, because the ToDo hook saves the task. Work order links (`requester`, `asset`, `room`)
go through `refuse_another_churches_record` when the link or the task's church changes.

## Bible memory

Bible Memory Item `group` is set only by `assign_memory`, on the items it makes for the group's
members. `validate` refuses any other change of `group`, and deleting a Group clears it from the
items (`clear_group`, Group `on_trash`). The Bible Memory report joins Person on `user` and scopes
Person, so a limited reader sees only users whose Person is in their churches. Bible Memory Item
stays in `GLOBAL_DOCTYPES`, so its list view is not church scoped.

## Songs and worship planning

A shared Song shares its charts and media with every church, and each church needs its own CCLI
license, so lyrics, charts and media reach only staff, the volunteers assigned to a function with
the song and, for a `public_domain` song, guests. Staff read Songs through `frappe.get_list` or
`frappe.has_permission`. Portal members have no Song read: a member sees keys, arrangements, team
notes, need notes and Song Media only through `function.get_team_schedule`, for a function where
they have an assignment that is not Declined. It reads Function Schedule, Function Team Need and
Song Media with literal doctypes, so the published-field scan badges them. The Bulletin calls
`get_schedule_rows`, which carries no team details, so it never prints team notes.

Song Media files are private. `songs/media.get_team_song_file` is the only way a member opens one:
it checks the session person's own assignment (not Declined, the function ended 7 days ago or less,
the song on its schedule), streams only a File attached to that Song with `get_content()`, and
never hands out the private URL. `Function.validate_schedule_songs` refuses a new or changed Song
row whose song the editor cannot read, because its media then reach this Function's team.

`church_ministries/songs/chordpro.py` is the one ChordPro reader: `parse`, `transpose`, `to_html`
and `lyrics`. The chart of a Song Arrangement is the source. Song slides are a generated copy that
`song.make_slides` replaces. `to_html` escapes every part of a chart, because charts come from
imports. `transpose` moves a chart only to a key of its own mode, and raises ValueError for a change
from major to minor or back.

`songs/song_files.import_song_text` is the one way to make a Song from a file. It reads ChordPro and
SongSelect `.usr` text with the standard library only, inserts without `ignore_permissions`, makes
the slides through `make_slides`, and skips a song that the importer's `frappe.get_list` already
shows by CCLI number, else by title. Churchit parses no song XML: `openlyrics.py` only writes it.
An import reads each File through `frappe.get_doc` and `check_permission("read")`, refuses a file
over 1 MB on disk (never trust `File.file_size`, the uploader sets it), reads it as UTF-8 or
Windows-1252, and deletes the caller's own unattached uploads after a successful import. A theme
of a file becomes a Tag only when it matches `PLAIN_THEME`: the desk list shows tags unescaped and
splits them on commas.

`songs/hymns/` ships public-domain hymns from WorshipCommons as ChordPro files; keep its
`LICENSE.txt`. A new hymn needs `{meta: year}` 1930 or earlier and one `{meta: died}` 1955 or
earlier for each `{meta: author}` (every writer of the words, the tune and the verses), read from
the source's own metadata. Leave out a hymn whose source names a setting or arranger who died after
1955. `test_hymns` enforces the year and the deaths. Hymns go in only through
`add_public_domain_hymns`, never in `after_install`, because the songs belong to the church.

## Ministry team scheduling

`church_ministries/availability.py` is the one place for scheduling problems.
`get_problems(person, start, end, position, exclude_function)` gives the texts (blocks, repeating
blocks too, double booking, missing checks, the monthly limit of the person's roster row), and
`is_available` adds "not deceased". Blocks and limits only warn: a Ministry Team Assignment shows
the texts and never refuses because of them. Code that picks people itself calls `is_available`
and orders them with `rank`. A repeating Ministry Team Block repeats its From Date to To Date span
with `dateutil.rrule` (`get_covered_dates`), so never filter blocks on `to_date` alone.
`member_ministry_team.set_own_frequency` changes a member's `max_times_per_month` by saving the
Position loaded with `for_update`, so a stale desk save fails.

`church_ministries/auto_schedule.py` fills open places. For each Function it commits, then locks the
Function with `for_update` and reads its assignments with a locking read (see "Care and child
safety" on REPEATABLE READ), so a range fill holds one lock at a time. Before any plain read it also
locks the roster rows of the positions the Function needs and their Person rows, in name order, so a
fill of another Function that can ask the same people waits and then sees these requests. It counts
Pending and Accepted against the needs and asks roster people in `rank` order who pass
`is_available` (with no `exclude_function`, so one person fills one position of a function) and have
no assignment of any status for that place. It inserts Pending assignments without
`ignore_permissions`, so the church guards run, and fills only positions that are shared or of the
church the assignment takes. The daily job sends the requests. The Ministry Team Grid report reads
`get_needs` and `get_assignments` from the Ministry Team Schedule report, so both count open places
the same way.

A replacement request is a Ministry Team Assignment with `replaces`. Only
`member_ministry_team.ask_replacement` makes one (`flags.is_replacement_request`):
`validate_replacement` refuses a link set by hand, and `on_update` refuses a change of it. It locks
the Function, then the original, takes only a person from `get_candidates` (roster people that
`is_available` passes with no `exclude_function`, so not someone who serves at the function in
another position, and that were not asked for that place), and allows one Pending request for each
original. When the request is Accepted, `on_update` declines the original with "Replaced by ..." and
the coordinator email follows, with `replaced_by` in its context. A declined request leaves the
original as it was and does not email the coordinator. Either answer emails the original person with
the Ministry Team Replacement Email Template. Keep the names and arguments of `answer_by_key`,
`answer_own_assignment`, `add_own_block` and `send_team_emails`, the `/ministry-team-response` route
(emails sent before a change link to it) and the stored statuses Pending, Accepted and Declined.

## Care and child safety

`background_check.is_cleared(person, on_date, check_types)` is the one rule for "cleared to serve":
code that decides who may serve calls it. `Person.background_check_status` and the Person form's
indicator show only the latest check, so do not filter on them to find who may serve. A Care
Request's caregiver gets the request through `assign_to`, which shares it only when the session user
has the share right. So `CareRequest.assign` shares it first, with `ignore_share_permission`.
`before_save` has already refused a caregiver outside the request's church
(`refuse_a_caregiver_outside_the_church`). Care Request, Care Assignment, Visitation Log and Member
Transfer set `track_changes`. Remove Personal Data deletes their Version rows (`forget`), and
`church_people/test_care_history.py` proves it.

`background_check.get_check_problem(person, on_date, check_types, label)` is the one message for a
missing check, and Ministry Team Assignment and Group both call it. A Group with
`needs_background_check` checks, in `group_requirements.check_member_requirements` (from
`Group.validate`), only member rows whose (person, role) pair is new since the last save, and with
Checks Apply To Leaders only rows whose Group Role leads the group. `block_without_checks` throws;
otherwise the save warns. The requirement fields are on Group, not on the global Group Type, so one
church cannot weaken another church's rule.

At the Check-In Station, `function_check_in.add_check_ins(function, persons, kind)` is the one way
code checks people in: the station, the kiosk and pre check-in call it after their own permission
checks. Every writer of a Function Check-In takes its locks in one order: the Function row
(`frappe.db.get_value("Function", function, "name", for_update=True)`), then the Check-In Settings
code lock (`get_single_value(..., for_update=True)`), then check-in rows. A path that locks several
Functions takes them in name order. `checkout.lock_check_in` (release, check-out, undo),
`check_in_limits.get_capacity(for_update=True)` and `kiosk.add_household_check_ins` follow this
order. `add_check_ins` takes the code lock on every call, then finds the people's check-ins with a
locking read. MariaDB runs REPEATABLE READ, so a plain read after a lock answers from the request's older
snapshot: a read that decides a write after a lock is a locking read, and Function Check-In has an
index on `function` so that read locks one Function's rows. `get_security_code` gives a household
one code a day, unique on the site. A Volunteer check-in gets no code, does not count in a room, and
starts no First Check-In card. Neither does a check-in saved under `frappe.flags.in_import`, which is history.

`check_in_limits` owns who may check in. `get_bound_problem(function, person)` measures the
Function's age and grade bounds on its start date, and an unknown age or grade fails a set bound:
the station asks to confirm, and the kiosk and pre check-in do not offer the Function.
`add_check_ins` calls `refuse_a_full_room` under the Function row lock. In Block mode it counts the
check-ins that are not collected (Volunteers left out) with a locking read and raises
`RoomFullError`. An insert without `ignore_permissions` (the form or REST) is checked one at a time
in `FunctionCheckIn.before_insert`, and `check_in_kind` is `set_only_once`, so a later change cannot
free a place. `get_capacity` sums the rooms of the Function's Approved Room Bookings, and 0 means
no limit. Self check-in (kiosk and pre check-in) needs a Function Type with `allow_self_check_in`
and `is_check_in_open`.

`check_in.get_pickup_families` gates on the Function Check-In rows the reader may read
(`frappe.get_list`), then reads the people those rows name with `get_all`, whatever their church. Do
not fetch Person fields through the check-in's link (`person.full_name` in `get_list`): Frappe
applies Person permission to that join, and a child at a shared function loses their name. Who may
collect a child is the living household Adults plus the family's Authorized Pickup records.
Authorized Pickup is a record of its own with the family's `church` (Church Manager and Church
People Editor only), so lists, Report Builder and `/api/resource` scope it like any record. Its
church follows the family's church (`set_pickups_church`, called from `Family.on_update` and
`Person.sync_family_church`). A Pickup Restriction names someone who may not collect a child, a
household Adult included. Only Church Manager and Church People Editor read it, because its reason
and court order are private. The station reads both only in `check_in.get_pickup_family`
(restrictions through `get_restrictions`), with `get_all`, and never sends a restriction's reason or
file. `release` refuses a restricted collector unless a Church Manager gives an `override_reason`,
stored with `overridden_by` on the Function Check-In. Never put custody details on Authorized
Pickup. `check_in.release_children` reads the families again before it stores who collected a child
(`collected_by`, `collected_at`, `released_by`). `collected_at` is the one checkout state:
`checkout.check_out` sets it for a row with no security code. The controller refuses a delete of a
row that has it, a change to `CHECKOUT_FIELDS` from anything but `check_out` and `release`
(`flags.checkout`), and a new row that sets one of them unless `add_check_ins` inserts it
(`ignore_permissions`), because Frappe does not enforce `read_only` on insert.

The station finds people only through `group_by_family(matched, get_people_scope(function))`, Scan
Card and the New Visitor matches (`page/check_in/visitors.find_visitor_matches`) included, so a new
way to find people there must use it. `search_people` and `find_card_holder` need the Function
Check-In create right. `group_by_family` sends allergies and grade to every station reader, and
`CARE_FIELDS` (medical notes and the emergency contact) only when the reader's roles hold Person
permlevel 1; do not send those rows to the kiosk as they are. The self check-in kiosk
(`church_ministries/kiosk.py`, `/check-in-kiosk`) applies the station's rule to the kiosk's one
church, checks in only the (person, Function) pairs that its phone lookup offered, and never prints
a security code that an earlier check-in holds. A pre check-in code
(`church_ministries/pre_check_in.py`) is `get_signed_params` of the Function, the people and an
expiry, made on `/household` for people the member may write and an open self check-in Function of
their church. `read_payload` accepts only the keys `f`, `p`, `u` in that order, because other signed
links share the secret. The station (Scan Card) and the kiosk check the Function with their own gate
and print only new check-ins, so a second scan prints nothing.

The roster (`get_check_ins`) and the pickup lists name people of every church on purpose, because
they are keyed to a function the reader may read. The roster polls `get_check_ins` every 10 s only
while a Function is picked and the page is visible; do not add `publish_realtime` or `doc_subscribe`
to it. A page to a child's parents (`page/check_in/paging.page_parents`) goes only to the household
Adults of the child's Family that no active Pickup Restriction names, with the Child Safety purpose,
so it honors consent. It texts only when `sending.can_send_texts()` and the user passes
`check_sms_permission`, one `send` and one commit for each Adult, and emails everyone else, with a
separate send key for each channel, because `send` dedupes a person on (source, key) whatever the
channel. `page_parents` commits its claim before it sends, and the copies are about the child's
Person: `send` locks its source until the commit, a gateway call has no timeout, and every code draw
on the site locks the day's coded check-ins. Never hold a Function Check-In row lock across a
network call. Do not add Authorized Pickup to `person_data_map.ROSTERS`: a merge would strip the merged
person from every other family's pickup list. The Member QR Card and the pickup tag need
`get_qr_code` in the `jinja` hook; never `frappe.call(...)` from print Jinja, which fails outside a
request or a job. Check-In Settings picks each tag's Print Format through `get_template(kind)`: a
Tag Formats by Kind row for the check-in's kind, else the Single's formats; pickup tags always use
the Single's. `render_name_tags` passes a Volunteer check-in's `position` (`team.get_position`) into
the template context, so print Jinja reads no team assignment. The Team tab's `team.get_team` reads
assignments with `get_all`, because Church Check-In has no DocPerm on Ministry Team Assignment; it
gates on Function read.

`church_prayers/prayer_access.py` holds the Prayer Request Visibility rules. The Church Prayer Team
DocPerm reads every request; the hooks take back other people's Private requests from a user whose
only role that reads every request is Church Prayer Team. Code that reads past permissions applies
Visibility itself: `get_community_filters` for the community page, `has_webform_permission` and
`create_prayer`, and `WHOLE_CHURCH` only for bulletins (`bulletin.py`). A web form's
`condition_json` reaches the community `get_list` as `{field: [operator, value]}`. A request shows
on the community list and in bulletins only while it is open, approved for the list and not past its
end date (`prayer_access.get_open_request_filters`). A guest request starts with Approved for List
off.

Prayer Request `prayer_count` belongs to `prayer.recount_prayers`. Prayer locks every request that
its old and new topics name, in name order, in `validate` (and `on_trash`), before it writes topic
rows. `on_update` and `after_delete` count the distinct Prayers with a locking read, which the
Prayer Topic `topic` index keeps to one request, and write the count with `update_modified=False`,
so praying does not move a request up the lists that sort by `modified`. `PrayerRequest.validate`
reads the count back with a lock, so a stale form cannot undo it. A desk save that adds a topic
needs read on that request, because child tables skip User Permissions. Moderation uses only
`approved_for_list` (permlevel 1), which Church Staff cannot set, also from the list Edit action.

## Follow-up cards

`followup.add_card` is the one way code opens a card. `followup.start_cards` is the one way an event
about one person reaches the workflows that start on it; the daily `start_smart_list_cards` job reads
the On Smart List triggers itself and calls `add_card`. A person has one open card per workflow:
`add_card` and the card's `validate` both ask `followup.get_open_card`, which locks the Person row,
because a plain read answers from the job's older snapshot.
`followup.on_sign_up` queues `start_sign_up_cards` after the commit for each attendee Person a
Confirmed sign-up gained (Signed Up, by Function Type), so it runs as Guest after `/register` and the
person-linking job. `FormResponse.process` starts the Form Submitted workflows of its Question Set.
In both, a shared Function or set follows up at the Person's own church.

A workflow's Actions table sends an email or a text, adds the person to a group, or tags them when a
card opens, reaches a step or closes. The card's `after_insert` and `on_update` call
`followup.queue_actions`, which queues `run_actions` after the commit only when the workflow has an
action for that event or another workflow starts on it. `followup.close_quietly` closes a card with
`flags.closed_quietly` and queues nothing: a merge closes the repeated cards with it, and anonymizing
closes the person's open cards with it, so no tag, group or new card is made for them. The job runs as the saver, Guest
after a connection card, and writes with `ignore_permissions`. Pass the event as `run_on`:
`frappe.enqueue` keeps an `event` argument for itself. Each action is logged once in a Follow-up
Action Run, inserted first under the unique key `<card>:<row>:<event>:<step hash>` (a short sha256
of the step, because a step name alone can fill a Data field), then run under a savepoint and
committed on its own: a failure rolls back to the savepoint and logs Failed, a send that reaches
nobody logs Skipped, and nothing is retried (Frappe still reruns a job after a deadlock; the keys
skip the actions already committed). Sends go through `send()` with the card as source, the key
`<row>:<event>:<step hash>` and `{{ step }}` in the context; the workflow checks the text and the
Email Template placeholders on save. Add Tag writes `_user_tags`, read with `for_update`, and the
Tag Link itself, because `DocTags.add` checks write on the Person as the session user; the Tag Link
insert refuses a tag that does not exist. A Step Reached or Card Closed trigger names another
workflow of the same church (and for Step Reached, optionally one of its steps); `run_actions` then
calls `start_cards` with the card's workflow as value and its step. A desk alert is still a
Notification on Follow-up Card. Deleting a card deletes its runs, and anonymizing blanks the `error`
of the runs of the person's cards (`privacy.forget_records_about`), because a failed text's error
can hold the number.

The workflow owns its Kanban Board: `FollowupWorkflow.sync_board` rewrites its columns and filters
on every save, so never edit the board by hand. The form hides the workflow's Board link; Open Board
opens the board. A Follow-up Action Run takes its title from its card (`title_field` card, a Link),
never from a stored copy of the person's name: a run has no Person link, so Remove Personal Data
would not rewrite a copy. `Follow-up Card.step` stays a Data field, because Kanban v2 takes columns
from the board, not from Select options. Frappe checks a Dynamic Link before `validate`, so a
trigger's `value_type` is set in the workflow's `_validate_links` override from
`followup.VALUE_TYPES`. Moving a card closes its ToDos and assigns through
`assign_to._add(ignore_permissions=True)`, as Assignment Rule does. `has_card_permission` reads
`_assign` from the database: a form sends none, and a caller could send a forged one.

## Connection Cards

The Connection Card web form saves as Guest, and `ConnectionCard.process` runs as a job after the
commit, as the sender, writing with `ignore_permissions`; anything it reaches (`start_cards`,
`add_card`, the Follow-up Card hooks) must work as Guest. Guest input never changes an existing
Person: a card links only on `is_strong_match` and otherwise adds a Visitor and records Possible
Duplicates. A card that adds a Visitor copies its `how_heard` to the new Person only. A strong match
keeps the person's own value. The honeypot is checked in the job, because `accept` returns the saved
document to the sender.

Frappe fills web form fields from the query string but drops it when it redirects `/<route>` to
`/<route>/new`, so a link carrying `?church=` points at `/new`. Web Form Field has no Table
MultiSelect: the form shows the table as a Table field and draws checkboxes from the options Frappe
lists for its Link column (`connection_card.js`).

`ConnectionCard.record_consent` turns the Stay in Touch ticks into Given (Church News, method Web
Form) for the card's person, desk cards included. A tick counts only for an address or number
already on the person's record (`contacts.get_holders`, phones on `digits`), and never overrides a
withdrawal on record, because guest input cannot prove who ticked it.

## Forms

A Question Set with Publish as a Form is answered at `/form/new?question_set=<name>`, the `form`
Web Form (`church_setup/web_form/form/`). The question set is a hidden Data field, never a Link, and
the page draws the questions from the guest GET `form_response.get_form`, which answers only for a
published set and refuses a members-only one to anyone without a Person. `FormResponse.validate`
checks the same on insert only, so a later change to the set never blocks a save, and rebuilds the
answer rows with `questions.set_answers`, so the browser sends no label or unknown question. A
member's response takes `session_person()`. `FormResponse.process` runs after the commit as the
sender, as `ConnectionCard.process` does: it locks the response, returns unless it is New, links or
adds the person (source Form) through `matching.find_or_add_person`, sets Processed and starts the
follow-up. Responses to a shared set have an empty church, so every church sees them.
`restore_payment_fields` keeps `amount_paid` and `payment_status` as code stored them. A saved,
published set links to its form as Open Form in the form sidebar (`question_set.js`).

## Church Emails, consent and bounces

A Church Email works out its recipients when it is sent, all from its own church: its people, one
of its groups, a smart list, or Chosen People that `validate` checks on save. A smart list is read
only through `smart_lists.get_people(report, church)`, which applies `church_filters` and leaves out
the dead. Unsubscribes are Email Unsubscribe records against a church, and `newsletter.email_church`
is the one place that says which church: the root church on a single-church site, where records
carry none.

Include Their Households (`include_household`) adds the living members of each recipient's Family
through `household.members`, limited to the roles in Household Members. On a multi-church site, only
the message's own church's people are added. Consent applies to each added person in
`get_recipients`.

A Church Email fills placeholders with `sending.render` (see the `sending.py` docstring). Never
render it with `frappe.render_template`, and keep `sending.check_placeholders` in `validate`.

Each copy is a Communication with reference Person and a timeline link to the Church Email.
`sending.get_people_sent` reads those links to decide who already got it, and a delivery commits
every batch (100 emails, or each text, sent before its commit), so a rerun never sends twice. Do
not create or delete these Communications any other way. Anonymizing blanks a copy's address and
text and keeps the copy. People sharing one address or number get one copy, recorded on the first
of them by Person ID.
Frappe's `send_sms` writes an SMS Log only for numbers the gateway accepted, so a text copy's
`delivery_status` is Sent or Error from that log. `get_people_sent` leaves out Error copies for the
Number Sent count, and a delivery asks with `include_failed=True`, so a failed copy is never sent
again.
Texts go through Frappe's public `send_sms`, so the SMS Settings Allowed Roles apply in the job, and
`require_sending_set_up` checks them at click time. The scheduler only claims and queues `deliver`
on the long queue; a job that times out stays Sending for the stalled retry.

Any other record that messages people calls `sending.send(people, channel, purpose, source, *,
key=..., ...)`, with every argument after `source` as a keyword. It applies consent for the channel
and purpose (`sending.get_recipients`, which a Church Email uses too), fills placeholders like a
Church Email plus the names in `context`, and keeps each copy as a Communication on the Person,
linked to `source`, with `key` in the Custom Field `send_key`. It locks the source row and skips
everyone who has a copy for that source and key, so a rerun sends nothing and a new key (a
reminder) sends again. It does not commit. A text leaves at once, so a caller that texts many people
calls `send` once per person and commits after each, as `Delivery.send_all` does: a rollback after a
text left forgets its copy, and a rerun texts that person again. Church Email copies keep a blank
`send_key`. New code that messages people uses it, not `frappe.sendmail` or `send_sms`, so consent
and the copy apply. Giving statements are the exception: they are tax receipts, so
`GivingStatement.send_by_email` sends them with `frappe.sendmail` and the Giving Statement Email
Template, as Online Donation sends its receipt, with no consent check (a global unsubscribe still
stops them; see "Giving and the fund ledger").

`send(..., PUSH, ...)` sends a push notification: *subject* is the title and *text* the plain-text
body (a push with no text is refused). A click opens *url*, a page of this site. Without it the
click opens `source.get_url()`, the desk form, which members with only Church User cannot open, so a
caller that pushes to members passes a member page. It reaches only people whose Person has a User
with a subscribed browser while `push.is_push_on()`, and a copy no browser took is Error. A push
copy is a Communication with medium Other. Push leaves after the commit, so a caller needs no commit
for each person. Send email or a text to the people `send` did not return, as paging does. No
feature sends push notifications yet; a caller adds Push on purpose (a leader's group message
refuses it).

Every group message goes through `send` with the purpose Group Messages
(`communication_purpose.GROUP_MESSAGES`, which cannot be deleted): a leader's message, the daily
attendance reminder, a join request to the leaders and the decision to the person. A leader's
subject and text are `context` values, never template source. A leader's message takes the name of
its Comment on the Group as its key, so the same words sent twice both go out. `send` sends nothing
for an empty list of people.

Every message to volunteers goes out under the purpose Serving (`communication_purpose.SERVING`,
which cannot be deleted). Ministry team request and reminder emails keep no consent check, because
an email consent check for a new purpose would stop every request in a church with
`contact_only_with_consent`, and they go only when the site can send email. Each assignment is also
texted through `send(..., SMS, SERVING, ...)` while `TeamTexts.is_on` (`paging.can_text()`: the
site can text and the user passes SMS Settings Allowed Roles), one commit after each text. When the
site can text but the user cannot (`TeamTexts.is_held`), a run skips the people who allow Serving
texts, so the daily job sends them the email and the text and no text is lost. A gateway error is
logged and turns the texts off for the rest of the run.

A sign-up reminder (`function_sign_up.send_reminders`, daily) goes through `send` with the purpose
Event Registrations (`communication_purpose.EVENT_REGISTRATIONS`, which cannot be deleted), to the
registrant's Person only, with the key `reminder` for the email and `reminder-text` for the text, so
a rerun sends nothing. It waits while the site has no outgoing email account. The confirmation and
payment emails answer the registrant's own request, so they go through `send_registrant_email`
instead (see "Function sign-ups").

Consent is answered only by `consent.allowed`, or `consent.allowed_people` for a list. The newest
record decides, ties by creation; a blank-purpose Given never undoes a withdrawal for one purpose.
Recorded On may not be in the future. A Notification has no purpose, so only consent for every
purpose counts, and staff (System Users) are never dropped. An address or number is refused only
when every Person holding it is refused. An unsubscribe link or an Email Unsubscribe withdraws every
holder of the address. A Communication Preferences switch, and any Given, records only the person
who chose it. An Email Unsubscribe made with `db_insert` runs no hooks, so call
`consent.record_unsubscribe` after it, as `newsletter.set_subscribed` does. Texts and push
notifications are opt-in: with no record for SMS or Push nobody gets them, whatever the church's
setting (`consent.default_statuses`).

An unsubscribe link carries the purpose and the recipient Person, signed (see
`newsletter.unsubscribe`). The Consent Renewal notification asks `consent.is_due_for_renewal`, so
each yes is asked about once, and its signed link (`consent_renewal_link`, a jinja method) runs
`consent.renew`. The Communication Preferences page (`church_communications/preferences.py`) changes
only the session's own Person and takes no person argument. Its Push column shows only while push
is on and the member has a subscribed browser (`preferences.get_channels`). Church News by email
also goes through `newsletter.set_subscribed`, and a yes to any email purpose lifts the address's
global Email Unsubscribe. Only `newsletter.py` writes Email Unsubscribe records. Ask
`sending.can_send_texts()` wherever the question is whether this site can send texts.

`bounces.record_bounce` reads a bounce report's text, one pattern per format (the `bounces.py`
docstring explains why); a new format needs a pattern and a real sample in `test_bounces.py`. Decide
whether to send to an address only through `bounces.bounced_addresses`. `is_bounced` (Bounced) is
cleared only in `contacts.validate_contact_tables` when a row's address changes; a raw write
(`db.set_value`, `db_insert`) skips that.
