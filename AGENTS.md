# AGENTS.md

Notes for anyone (person or agent) adding functionality to Churchit. `CLAUDE.md` describes the
architecture and the commands; this file covers the things that are not visible in a diff and will
break quietly if you do not know them.

Read this before adding a doctype, a report, a chart, a notification, or a page.

## The one invariant

A site can run in **multi-church** mode: one main church with branch churches under it, switched on
in `Church Features`. Records belong to a church, and a user sees only their own church's records
unless they opt into the branches beneath it.

People and families are the exception. Every church reads the whole directory, the way one
congregation over several campuses expects. Only a person's own church may change them.
`Keep People and Families Private to Each Church` in `Church Features` scopes them like every
other record. Records about a person, such as care requests, counseling and giving, keep their own
church either way.

The failure mode is silent. Nothing errors when you get this wrong; a branch simply sees rows that
belong to another church. That is why the rules below are enforced by
`churchit/tests/test_church_scope_hygiene.py` rather than left to review.

Access rides on native Frappe **User Permissions** on `Church`. A user's `Person.church` drives the
permission; `hide_descendants` is the "include branch churches" switch. `permission_query_conditions`
is deliberately unused.

The directory is the one custom piece. The `church` Link on `Person` and `Family` ships with
`ignore_user_permissions: 1`, so User Permissions do not filter them. A User Permission cannot
tell a read from a write, so the `has_permission` hook
`church_scope.refuse_changing_another_churches_people` refuses every other action outside the
user's churches. A Frappe `has_permission` hook refuses on any falsy return, `None` included. When
the directory is private, `multi_church.apply_people_privacy` adds a Property Setter that turns
the flag off.

A read of `Person` or `Family` that a user sees must follow the setting. `frappe.get_list` does this
by itself. A raw read asks `church_scope.is_people_directory_private()`, as the Check-In Station does.
A count is the opposite case. A Number Card or Dashboard Chart over `Person` or `Family` must be
Custom and count only the reader's churches (`churchit.dashboard.count_people`). Frappe's own count
totals every church.

## Reading data: the rule that matters most

| API                      | Applies the reader's church?    |
| ------------------------ | ------------------------------- |
| `frappe.get_list`        | **yes**, Frappe does it for you, shared records included |
| `frappe.get_all`         | **no**                          |
| `frappe.db.count`        | **no**                          |
| `frappe.qb` / raw SQL    | **no**                          |
| Child tables, by any API | **no**, ever                    |

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

Child tables are never filtered by Frappe, whatever you call, and they carry no church of their own.
Scope the parent and join to it, the way the Life Events chart source joins `Life Event` to `Person`.

The hygiene test fails on any unfiltered read of a scoped doctype in a module that does not use
`church_scope`. If a particular read genuinely cannot cross churches, say so where it happens:

```python
# church-scope: clashes within one room, and a room belongs to one church
conflicts = frappe.qb.from_(Booking).where(Booking.room == self.room)
```

The reason is required and lives in the function holding the read, so review sees it and the next
read in the same file still has to justify itself. The function, not the file, is the unit: a module
that scopes one read used to vouch for every other read in it, which is how an unscoped Budget
lookup sat next to a scoped one.

## Whitelisted endpoints: the desk is not a rule

Every scoping hole found by auditing this app from the API side had the same shape. A link field's
dropdown filters by church and its pre-save check refuses a name typed in by hand, so the desk looks
safe; but a whitelisted function that takes a name is called directly by anyone with a login, and
`PRSN-.####` names are a counter anyone can walk.

- A **document method** (`self`) is safe on its own: Frappe checks read or write on the document
  before running it.
- A **module-level function taking a name** is not. `frappe.get_doc`, `frappe.db.get_value` and
  `frappe.qb` check nothing. Add the check yourself, against the record the caller named:

```python
frappe.has_permission("Function", doc=function, throw=True)   # before reading anything about it
frappe.get_doc("Group", group).check_permission("read")        # when you need the document anyway
```

Do not reason from "this is keyed to one function, and a function belongs to one church". That says
the *data* cannot cross churches; it says nothing about whether this caller may see that function.
"Templates are shared on purpose" is the same trap: it justifies reading a template, not reading any
function whose name the caller supplies, so `apply_template` checks that the source is one.

Watch for three things that switch the checks off, because together they hid a hole where any
manager could take any member of any church (`Member Transfer`):

- **A plain Link to a scoped doctype.** Frappe applies user permissions to `Church`, not to `Person`,
  so a `person` field is never measured against whose member it is. Check the linked record's church
  yourself, as `MemberTransfer.validate_both_churches_are_mine` does.
- **`ignore_user_permissions: 1`** on a Link exempts that field from the only check Frappe would make.
  It is right on `shared_by_church`, on tree parents and on the directory's `church` fields, and
  suspicious anywhere else.
- **`ignore_permissions=True`** on a write reached from a whitelisted call. It skips the check that
  refuses the same edit made on the form.

## Adding a doctype

Every doctype that stores records must either carry a church or be declared global; the hygiene test
fails until one is true. Child tables and Singles are exempt automatically.

Scoped doctype: add this field near the top of the form, after the title field.

```json
{ "fieldname": "church", "fieldtype": "Link", "options": "Church", "label": "Church",
  "hidden": 1, "in_standard_filter": 0 }
```

Leave it `hidden`. `Church Features` creates site-local Property Setters that reveal it when
multi-church is on, so single-church sites never see it. `church_scope.ensure_church` (a wildcard
`validate` hook) fills it on save and refuses the save if it cannot.

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
entries are lookup and type tables, shared reference data such as Bible Translation, and records
that belong to a person rather than a church.

### Records a church can share

Between the two lies a third bucket: a doctype in `SHAREABLE_DOCTYPES` (`churchit/church_scope.py`)
is scoped as usual, but each record may be handed to every church with a **Shared with all churches**
checkbox. Today that is the reusable content, the supplier directory, the places and equipment that
congregations share, the occasions they hold together (Function, Meeting Minutes), and the two
containers money runs through (Fund, Ministry).

**A container may be shared; money never is.** Every Collection, Expense and Online Donation keeps
the church that gave or spent it, so per-church figures come from those rows at read time. What a
shared container holds is the joint pot, and a stored total on it has to be the joint truth rather
than one reader's share: `Fund.balance` is the joint balance, `Ministry.total_expenses` the combined
spending, `Function.attendance_total` the one head count of one joint service. Say the consequence
out loud when you add a doctype here, because it is the owning church's decision to publish that
figure: sharing a fund publishes its balance and its ledger to every church.

**A global record may not name church-owned money.** Expense Type is global and carries the Fund an
expense debits, so every church's expenses of one type used to debit whichever single church owned
that fund. It happened silently, through `frappe.db.get_value`, which ignores permissions. Any link from a
global or shared record into a church-owned one needs
`church_scope.refuse_another_churches_record(doc, doctype, name)` on the pointing document's
`validate`: it compares churches rather than permissions, because the writes that most need it run
with `ignore_permissions`. The fix for the church that trips over it is to share the fund.

Call the guard from the controller, not from a `doc_events` hook: a hook runs *after* the
controller's own `validate`, which is where `ensure_church` settles the church, so the guard resolves
the church itself rather than reading a field that is still empty.

Listing a doctype only offers the checkbox. Nothing is shared until someone ticks it on a record, so
widening `SHAREABLE_DOCTYPES` changes no existing data.

**Only the church in `shared_by_church` may take a shared record away from the rest.** That covers
unticking the box and deleting the record, which are the same loss through different doors, so both
go through `only_the_sharing_church_may`. Administrator is nobody's church and bypasses it; a user
holding no Church permission does not, because holding none means unrestricted *reading*, not
ownership of what other churches shared. Records that took their church from a shared one, such as a
booking of a shared room, are stamped back to its church by `restamp_dependents` when it stops being
shared: without that the booking stayed on show to every church for good.

A shared record stores the **empty string** in `church`, which is exactly what Frappe's permission
clause reads as "every church", so the read side costs nothing. Two rules follow from that, and
breaking either is how this gets confusing:

- **An empty church is the empty string, not NULL.** Frappe's permission clause reads both as
  shared, but `church == SHARED` only matches the empty string, so a NULL stopped sharing from
  propagating to records that derive their church. `multi_church.normalise_shared_church` settles
  this on the transition.
- **An empty church always means shared, never "not filled in yet".** `church` carries a
  `depends_on` so it vanishes when the box is ticked, and the desk prefills it on new documents
  (`church.prefill_church`). Keep both if you add a shareable doctype.
- **The church that shared it is kept in `shared_by_church`**, revealed alongside the checkbox so a
  record shared by the main church does not look like one the branch shared itself. The form also
  notes it and locks the checkbox, from `frappe.boot.churchit.churches`
  (`church.note_shared_by_another_church`). Unticking the box returns the record home rather than to
  whoever happened to save it, and only that church may untick it
  (`church_scope.refuse_unsharing_by_another_church`). A shared record is writable by every church,
  so without that guard any branch could pull a resource out of the whole organisation, itself
  included. There is no per-recipient opt-out: a branch that wants something gone asks the owner.
  The guard steps aside for `ignore_permissions` saves, so patches and jobs are unaffected.

Sharing is not hierarchical: a branch may share upward and sideways, not only the main church
downward.

A record that derives its church with `fetch_from` inherits sharing too. A booking of a shared room
is itself shared, so every church sees that the room is taken, with `shared_by_church` recording who
booked it. `church_scope.inherits_a_shared_church` is what keeps `ensure_church` from stamping its
own default over an inherited blank.

Two shapes that are neither, and how they are handled today:

- **Family** follows its head of household's church (`Family.follow_head_of_households_church`),
  because a household can span branches. The directory therefore lists a family under every branch
  that has one of its members, rather than filtering on the family's own church.
- **Function Type** templates are shared configuration, so `template_function` carries
  `ignore_user_permissions` and `apply_template` checks the role, not the document.

Budgets are the one aggregate anchored to a record's church rather than the reader's scope. A budget
counts its own church, and counts the churches beneath it only when **Include Branch Churches** is
ticked, which is how a main church budgets for the whole organisation without forcing that on every
budget it owns. That is also why Budget is not shareable: a shared budget would have no church to
anchor to and would show organisation-wide spending to everyone.

## Adding a report, chart or number card

Reports run raw and bypass permissions entirely; `query_report.run` only checks the role-level
report permission.

- Server, and this is the one that matters: pass `filters` through to the query and wrap it in
  `scoped(query, Table, filters)`. Scope the table that owns `church`; for a child table, scope its
  parent. Forget this and the report shows every church's rows to everyone.
- Client: spread the shared filter into the report's own: `filters: [...church.report_filters(), ...]`.
  This is the picker, not the guard. A report without it is still scoped, because the server falls
  back to the reader's own churches; the reader simply cannot narrow to one branch.

Both are enforced, with separate messages so you can tell a leak from a missing picker. Charts and
number cards of type **Document Type**
go through `get_list` and are scoped already. **Custom** sources and methods are not: scope them by
hand, as `churchit/dashboard.py` and the Life Events chart source do.

A **Custom** chart or card method is whitelisted, so any signed-in user can call it, portal
members included. Start it with `frappe.has_permission(<doctype>, "report", throw=True)`: the
report right is what staff roles hold and Church User does not. Give a Custom chart a
`document_type` as well. Frappe shows a chart with neither roles nor a doctype to System
Managers only.

## Roles

Church User is the **portal member** role, with no desk access. Staff hold desk roles, bundled
into Role Profiles in `fixtures/role_profile.json`:

| Role | Owns |
| --- | --- |
| Church Staff | The baseline for every staff login: reads people, events, groups, ministries and the lookup types. Changes only records it created. |
| Church People Editor | Person, Family, Group, Member Transfer |
| Church Pastoral Care | Care, counseling, visitation, background checks, prayer, alms |
| Church Finance | Collections, expenses, funds, budgets, statements, vendors |
| Church Check-In | The Check-In Station. Reads people, families and functions. |
| Church Manager | Everything, including settings |

A new doctype gives its rights to Church Manager and to the role that owns its area, and read to
Church Staff if staff look it up. `tests/test_role_hygiene.py` fails when a profile can fill in a
form but cannot pick what one of its Link fields points at. Reports, workspaces and desktop icons
carry the same roles.

A portal member reaches their own records through `if_owner` DocPerms, and their own Person
through `church_people/member_access.py`. That module also limits their Person edits to the
Personal Details form's fields, and a prayer or alms recipient to their own church. A web form
renders the name of every record its Link fields may list, hidden fields included, so a member
form must not link to Person. `tests/test_portal_members.py` checks this.

## Notifications and email

`Notification` is overridden by `churchit/church_communications/scoped_notification.py`. Recipients
resolved from a **role** are dropped when their church permission excludes the document's church,
covering email, the desk bell and SMS, for records your users create too.

Recipients resolved from a document field are inherently fine. If you add a notification on a
doctype with no church field there is nothing to filter by, so every role recipient receives it.

Newsletters use one Email Group per church in multi-church mode
(`churchit/church_communications/newsletter.py`); the group name is derived in one place.

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

Two portal surfaces bypass document permissions by design and need the church applied by hand: the
community prayer request list and the groups list. Guest endpoints take `church` as an argument.

Frappe caches rendered pages by path alone, shared between guests and users, so
`church_website.context.before_request` disables the cache for signed-in visitors in multi-church
mode. Do not remove that without replacing it.

Every field a page shows carries a badge on its desk form, worked out by scanning the pages
themselves (`church_website/published_fields.py`). Nothing is declared by hand: a new www page,
published Web Page, Web Form or guest endpoint is picked up, and so are the helpers, jinja methods
and included templates it calls. Each source is marked public or members-only (a web form's
`login_required`, or a page that sends every guest to the login screen), so a portal-only field is
not announced as public. Two things defeat the scan, and both fail a test rather than going
quiet: reading records with `frappe.qb` or raw SQL on a public page, and giving a doctype a web
view, which renders from a template no source reads. Extend `code_sources()` before adding either.

### Settings a church can differ on

Four Singles hold configuration the whole site shared, and each now takes per-church
overrides through one resolution point, so no caller threads a church around:

| Single | Override | Resolved by |
| ------ | -------- | ----------- |
| Giving Settings | a `church` column on each `Giving Gateway` row | `gateways_for(church)` |
| Giving Settings | `Church Giving Wording` rows | `get_thank_you_message`, `get_statement_acknowledgment` |
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
- **`for_church` returns a copy, never a mutated Single.** `frappe.get_cached_doc` hands
  out one shared instance, so applying a branch's overrides onto it would follow every
  later reader in the process.

A gateway is the one with teeth: without it a gift given on a branch's page is taken
through whichever merchant account the main church configured.

## The switch

`Church Features.enable_multi_church` is off by default and a single-church site must notice nothing.
Turning it on, once only, stamps the root church on every existing record and gives every enabled
user a root permission with branches hidden. It cannot be turned off while branches exist. The
transition runs on the off-to-on edge only, never on migrate, so a permission an administrator
deleted stays deleted.

A login made **after** the switch is scoped too, by `church_access.scope_new_user` on User
`after_insert`: it takes the church the request is about, which is the branch whose page took a
sign-up, or the church of whoever is adding the user in the desk. Without it a user with no Church
permission is unrestricted, so a new staff account silently saw every church. Linking a Person
repoints the permission afterwards, so this is only the starting point.

## Client side

`frappe.boot.churchit` carries `multi_church`, `church`, `include_branches`, `single_church` and
`expand_church_filters` (`church_scope.extend_bootinfo`). Use it rather than querying from JS.
Anything keyed on it must behave when multi-church is off.

`churchit/public/js/church_utils.js` hooks one Frappe client method so the "expand filters to
branches" option reaches list views. It is guarded and falls back to exact matching if a Frappe
upgrade moves that method; if list filters stop expanding after an upgrade, look there first.

## Frappe behaviours worth knowing

- **Administrator is never restricted.** User permissions do not apply to it, so it always sees every
  church. Test scoping as a Church Manager, never as Administrator.
- **Booleans over `frappe.xcall` arrive as strings.** Use `frappe.utils.sbool`, not `cint`.
- **User defaults are cached per worker** and lag a write by a request; read the `DefaultValue` row
  directly when a choice must take effect immediately.
- **Hand-edited Workspace, Report and similar JSON is skipped by migrate** unless its `modified`
  timestamp is newer than the row in the database. Bump it or your edit silently does nothing.
- **Property Setters created at runtime are site-local.** The `church` field ones are deliberately
  not fixtures, so they never ship to a single-church site.
- **Frappe imports module folders only for the doctypes in its own `IMPORTABLE_DOCTYPES` list**
  (`frappe/model/sync.py`), which covers Notification but not Letter Head or Email Template. Records
  shipped as JSON beside their module for anything outside that list never reach a site, however
  correct the file; `patches/after_install.create_unsynced_records` seeds those.
- **`get_church()` returns a cached document shared process-wide.** Never mutate and save it; load a
  fresh copy with `frappe.get_doc("Church", get_church().name)`. A save on the cached copy leaves it
  holding a timestamp a rolled-back row no longer has, and the next save fails as stale. After a
  `frappe.db.set_value` on the Church use `frappe.clear_document_cache`, not `clear_cache(doctype=…)`,
  which only clears the meta.

## Testing

Run the whole suite before committing anything broad: `bench --site <site> run-tests --app churchit`.

- The suite is **destructive on a site you care about**. `TestSampleDataRoundTrip` deletes unfiltered
  doctypes and commits part way, so it rewrites the sample data. Restore with
  `churchit.setup.sample_data.create_sample_data()`, which is idempotent, or run single modules while
  developing.
- Tests must set `frappe.local.form_dict`, never `frappe.form_dict`, which replaces the proxy for the
  rest of the process and breaks later tests.
- Use `churchit/tests/helpers.py`: `ensure_root_church`, `make_branch`, `set_multi_church` and
  `force_single_church` put the site into a known mode inside the test transaction. Never look up the
  church with `frappe.db.get_value("Church", {}, ...)`; a site may hold branches.
- `churchit/tests/test_church_permissions.py` is where scoping behaviour is proved. Add to it when
  you add a surface that reads church data. `make_two_churches()` and `assert_scoped()` in
  `churchit/tests/helpers.py` make that two lines:

  ```python
  root, branch_a, branch_b = make_two_churches()
  assert_scoped(self, "Prayer Request", manager_a, request_in_a, request_in_b)
  ```
- Run `ruff format` only on the files you changed; the pinned version reformats older files.

## Onboarding steps and form tours

A module's `Module Onboarding` is the checklist a new church works through, and each step carries a
`Form Tour` explaining the fields the form does not explain by itself. Four things here fail
silently, so `churchit/tests/test_onboarding_hygiene.py` checks them rather than leaving them to
review:

- **An onboarding is rendered only where a `Workspace Sidebar` names it.** Set
  `module_onboarding` on the module's sidebar record in `churchit/workspace_sidebar/`, and bump its
  `modified`. Without it the records import, the desk shows nothing, and no error is raised. The
  `onboarding` block some workspaces still carry in their `content` is the pre-v16 mechanism and
  renders nothing.
- **Only two step actions start the tour.** `Create Entry` for a normal doctype and
  `Show Form Tour` for a Single, which routes to the settings page and then starts the tour.
  `Go to Page` and `Update Settings` both route to the form and ignore `form_tour` entirely, so a
  tour on either is dead configuration. Use `Go to Page` only for a step that has no form, the way
  `Sample Data` does.
- **A `Create Entry` step needs `Show Full Form`.** Without it the widget opens quick entry, which
  runs no tour.
- **A tour step names a fieldname, not a label.** Rename or hide the field and the tour stalls with
  no error. Point tours at fields the user can actually see: a `hidden` field, the `church` field
  included, is never rendered, and a field whose `depends_on` is the multi-church switch is absent on
  the single-church sites that are most of them.

`Onboarding Step` carries no `module` field. A step belongs to the module folder it ships in, and its
name is global across every app, so name it after the doctype and do not prefix it.

## Documentation obligations

The `Manual: <Module>` workspaces are the in-app user documentation, not developer notes. Update the
matching manual in the same change as any user-facing behaviour, and bump its `modified` timestamp.
`Manual: Foundations` holds the multi-church explanation.
These manuals are parsed to generate the documentation for the churchit.app website docs page.

Write the manuals for a church volunteer or secretary, not for a developer. Say what to click and
what happens, name the doctype the way its form does (a Function, not an "event record"), and keep
one name for one thing across every manual. Explain a term the first time a manual uses it. Leave
class names, hook names, field types and file paths out: they belong in this file or in a docstring.

## House style

**Never use an em dash or an en dash.** Not in code, comments, docstrings, commit messages, manuals,
form tours, notifications, print formats, the README or the docs site. This is a hard rule, and it
applies to the escaped forms too, whether written as an HTML entity or a unicode escape
(U+2014 and U+2013).

Rewrite the sentence rather than swapping the character for a hyphen, which usually reads worse than
the punctuation the sentence actually wants:

- An aside becomes a comma pair, or parentheses: "Reports run raw, bypassing permissions entirely."
- A sharp break becomes a full stop or a semicolon: "Do not remove that. Replace it."
- A definition or expansion becomes a colon: "One rule matters most: `get_all` is not scoped."
- A range becomes "to": "10 to 20 rows", never "10-20 rows".

A hyphen is fine where a hyphen belongs, in a compound like `church-scoped` or `multi-church`.
