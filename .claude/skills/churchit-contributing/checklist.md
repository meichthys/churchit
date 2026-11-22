# Merge-ready checklist

Work through "Every change" and each section that the change touches. Each item names the rule and the test that enforces it, when one does. The links go to the full rule. The `churchit-reviewer` agent checks this list.

## Every change

- [ ] The pull request has one purpose. It changes no unrelated file, reformats no line that it does not change, and adds no dependency or `uv.lock` change that the maintainer did not agree to.
- [ ] No em dash or en dash in any file, escaped forms included (`test_house_style`, [House style](../../../AGENTS.md#house-style)).
- [ ] `pre-commit run --files <changed files>` passes. Ruff 0.8.1 formatted only the changed files.
- [ ] New or changed behavior has a test, and the full suite ran on a test site. The pull request reports the result.
- [ ] A user-facing change updates the matching `Manual: <Module>` workspace in the same pull request, with desk links as `/desk/...` site paths and `modified` set to now ([Documentation obligations](../../../AGENTS.md#documentation-obligations), `test_workspace_hygiene`, `test_json_hygiene`).
- [ ] A manual, field description or README line that names an AI feature says that it needs AI turned on ([Documentation obligations](../../../AGENTS.md#documentation-obligations)).
- [ ] A new user-facing feature is in the README feature list.
- [ ] User-facing text is in `_()` or `__()`.
- [ ] A full date in a page, email, notification, print or stored title uses the long form `LONG_DATE_FORMAT` ("EEEE, MMMM d, yyyy"), and a stored title uses `churchit.utils.get_dated_title`. Only a tight space (portal list, table column, Kanban card, name tag) uses the System Settings format ([House style](../../../AGENTS.md#house-style)).
- [ ] A message about a fund goes through `fund.show_fund_change` or `fund.warn_of_negative_balance`, and an amount in it through `fund.format_amount`, never a written '$' or a raw float ([Giving and the fund ledger](../../../AGENTS.md#giving-and-the-fund-ledger)).
- [ ] A currency comes from `giving_settings.get_currency()`, and a shipped number card or chart leaves `currency` empty ([Giving and the fund ledger](../../../AGENTS.md#giving-and-the-fund-ledger)).
- [ ] Existing sites keep working after migrate: no renamed or removed field, setting, whitelisted method or route without a patch and an upgrade path.

## Reading data

[Reading data](../../../AGENTS.md#reading-data-the-rule-that-matters-most), `test_church_scope_hygiene`.

- [ ] Data that a user sees comes from `frappe.get_list`, or from `frappe.get_doc` plus `check_permission`. `frappe.get_all`, `frappe.db.count`, `frappe.qb` and SQL do not apply the reader's church.
- [ ] Each `get_all`, `db.count` or `qb` read of a doctype with a church goes through `church_scope` (`scoped`, `church_query_filters` or `church_filters`), or its function has a `# church-scope:` comment that gives the reason the read is safe.
- [ ] A child table is read with `get_list(..., parent_doctype=...)`, or joined to its parent and the parent is scoped.
- [ ] A count of people or families uses `dashboard.count_people` or `count_families`, because Frappe's own count totals every church.

## Whitelisted functions and document methods

[Whitelisted endpoints](../../../AGENTS.md#whitelisted-endpoints-the-desk-is-not-a-rule), `test_http_method_hygiene`, `test_doc_method_hygiene`, `test_agent_docs_hygiene`.

- [ ] There is no bare `@frappe.whitelist()`. A function that changes data or sends a message takes `methods=["POST"]`. A read takes `methods=["GET"]`, and its callers send GET.
- [ ] The first docstring line ends with "Reads only.", "Changes data." or "Sends messages.". Every parameter has a type hint, and a read has a return annotation.
- [ ] The function checks the caller's right to the record that the caller named: `frappe.has_permission(doctype, doc=name, throw=True)` or `frappe.get_doc(doctype, name).check_permission(...)`. A plain Link to a person does not prove that the person is in the caller's church.
- [ ] A document method that writes, sends or reads beyond the document first checks the stored record (`self.reload()` or `load_from_db()`, then `self.check_permission(...)`).
- [ ] `ignore_permissions=True` follows such a check, and never replaces it.
- [ ] `allow_guest=True` is only for a public page. The function checks each argument and has a rate limit.
- [ ] No whitelisted method that a script under `public/js` calls is renamed or removed. Browsers keep those scripts for 12 hours, so the old path works for one more release.

## New doctype

[Adding a doctype](../../../AGENTS.md#adding-a-doctype), [README steps](../../../README.md#steps-for-adding-a-new-doctype), `test_church_scope_hygiene`, `test_permission_hygiene`, `test_doctype_documentation`, `test_desk_ui_hygiene`, `test_navigation_hygiene`, `test_role_hygiene`.

- [ ] The name is unlikely in another Frappe app. Put "Church" before a common word (`Church Task`, `Church Budget`). ERPNext ships `Bank Transaction`, `Payment Entry`, `Budget`, `Project`, `Task`, `Location` and many more, and the app installed last takes over the record.
- [ ] The doctype has the hidden `church` field from AGENTS.md (`hidden: 1`, `in_standard_filter: 0`, the `single_church` `depends_on`), with `fetch_from` and `read_only` when the record hangs off another scoped record. A doctype that belongs to no church is in `GLOBAL_DOCTYPES` in the hygiene test, with the reason.
- [ ] The Settings tab has a description. Each field that is not obvious has a description.
- [ ] Church Manager and the role that owns the area have permissions. Church Staff reads it if staff look it up. Church User has only `if_owner` rights, for records that a member makes on the portal (Pledge and Function Sign-Up also give it read, which `member_access` hooks limit to the member's own, because staff record them for members) ([Roles](../../../AGENTS.md#roles)). Child tables have no permissions.
- [ ] The name is one field when clashes are unlikely. Otherwise it combines fields with a `{#}` counter, and the doctype sets a Title Field with "Show Title in Link Fields".
- [ ] A record whose ID is printed or sent sets `allow_rename` to 0. A name that must be unique in one church uses `churchit/unique_names.py` ([Forms](../../../AGENTS.md#forms), [Records a church can share](../../../AGENTS.md#records-a-church-can-share)).
- [ ] A default list filter on a Link field gives every profile that reads the list read or select on the target (`test_role_hygiene`, [Roles](../../../AGENTS.md#roles)).
- [ ] The Documentation Link on the Settings tab opens the module manual, for example `/app/manual%3A-people`.
- [ ] The doctype is on its module workspace and in its module sidebar under `churchit/<module>/sidebar/` (not for child tables).
- [ ] A doctype that needs setting up has an onboarding step and a form tour, listed in the module onboarding ([Onboarding steps and form tours](../../../AGENTS.md#onboarding-steps-and-form-tours), `test_onboarding_hygiene`).
- [ ] The list and form follow [Desk lists and forms](../../../AGENTS.md#desk-lists-and-forms).
- [ ] Sample records for the doctype have a delete step in `delete_sample_data` (`test_sample_data`).
- [ ] A lookup that every church shares (no `church` field) is in `church_access.GLOBAL_LOOKUPS` ([Settings a church can differ on](../../../AGENTS.md#settings-a-church-can-differ-on), `test_church_permissions`).
- [ ] A per-church table on a shared Single is listed in the controller's `church_access.refuse_changing_shared_settings` call, its `church` Link has `ignore_user_permissions: 1`, and the form sets a `set_query` on it ([Settings a church can differ on](../../../AGENTS.md#settings-a-church-can-differ-on)).

## Reports, charts and number cards

[Adding a report, chart or number card](../../../AGENTS.md#adding-a-report-chart-or-number-card), `test_reports_hygiene`, `test_reports_execute`.

- [ ] A script report passes `filters` to the query and wraps it in `scoped(query, Table, filters)`, on the table that owns `church` (the parent, for a child table).
- [ ] The report script spreads `...church.report_filters()` into its filters, and the report calls `set_report_link_titles`.
- [ ] A scoped script report whose rows each belong to one church selects `church` and ends its columns with `get_church_columns(filters)`.
- [ ] A report, card or page that reads Function dates or attendance filters `auto_repeat = 0`: a recurring template is only a rule ([Adding a report, chart or number card](../../../AGENTS.md#adding-a-report-chart-or-number-card)).
- [ ] A report that takes a record name in its filters checks that record with `frappe.has_permission`.
- [ ] The report name is specific to churchit. "Reconciliation" or "Variance" alone is too general.
- [ ] A Custom chart or card method starts with `frappe.has_permission(<doctype>, "report", throw=True)` and scopes its query by hand.
- [ ] A changed Add Total Row, Disabled or Prepared Report on a shipped report has a patch: migrate keeps the site's value ([Adding a report, chart or number card](../../../AGENTS.md#adding-a-report-chart-or-number-card)).
- [ ] A report passes `frappe.utils.getdate()` as a value, never CURDATE(), and takes a week from `query.this_week()` (`test_reports_hygiene`).
- [ ] A field that a report, card or summary filters a large table by has `search_index`, and a value per row comes from one grouped query, not a subquery per row.

## Shipped data, patches and schema changes

[README "Managing App Data"](../../../README.md#managing-app-data), `test_patches`, `test_json_hygiene`.

- [ ] The mechanism fits the owner of the data. A fixture is app-owned and comes back on each migrate. `patches/after_install/` is starter data for new sites only. A versioned patch in `patches/v1_0/` changes existing sites.
- [ ] A new patch is the last line of its section in `patches.txt`: `[pre_model_sync]` for work on the old schema, `[post_model_sync]` for work on the new one.
- [ ] A patch is safe to run twice, and it checks that a record, column or table exists before it uses it.
- [ ] A patch that reads a removed field or doctype uses `frappe.qb.DocType` or SQL behind `frappe.db.has_column` or `frappe.db.table_exists`, not `frappe.get_all`, because the metadata can be gone.
- [ ] A `rename_field` is guarded, so that a second run does not overwrite values entered since the first.
- [ ] A settings read that a wildcard hook can reach goes through `church_scope.is_feature_enabled` or a similar guard. Patches run those hooks on the old schema.
- [ ] A hand-edited Workspace, Report, Dashboard or other shipped JSON has `modified` set to now, never to a future time.

## Notifications and emails

[Notifications](../../../AGENTS.md#notifications), [Church Emails, consent and bounces](../../../AGENTS.md#church-emails-consent-and-bounces), `test_notification_templates`.

- [ ] A notification with role recipients is on a doctype with a `church` field, so that each church gets only its own.
- [ ] The message uses fields that exist on the doctype. A wrong `doc.` field renders blank, with no error.
- [ ] A change to who a Church Email reaches goes in `sending.get_usable_emails` or `get_recipients`, so that the left-out notes of Preview and Send (`sending.get_left_out`) follow it.
- [ ] A yearly notification (a birthday or an anniversary) uses Days Before on `next_birthday` or `next_anniversary`. Days Before and Days After match the year too, so a birth date or an anniversary never sends ([Adding a report, chart or number card](../../../AGENTS.md#adding-a-report-chart-or-number-card)).

## Public website, portal and web forms

[Public website and portal](../../../AGENTS.md#public-website-and-portal), [Member portal](../../../AGENTS.md#member-portal), `churchit/church_website/test_published_fields.py`, `test_web_forms`.

- [ ] Page data is scoped with `selected_church_filters(...)` in Jinja, or with `church_filters(selected_church_name(), ...)` in Python.
- [ ] A page reads no doctype data with `frappe.qb` or SQL. `test_published_fields` fails on one, and it must pass, because it badges each field that the website shows.
- [ ] Guest input is checked on the server, and a guest form or API has a rate limit.
- [ ] A new shipped page that tells visitors about the church is in `VISITOR_PAGES`, and a page that an emailed key opens for someone with no login is in `EMAILED_KEY_PAGES` ([Public website and portal](../../../AGENTS.md#public-website-and-portal)).
- [ ] A /register endpoint checks the function against `register.get_open_functions` ([Function sign-ups](../../../AGENTS.md#function-sign-ups)).
- [ ] A web form script that uses Jinja tags is in the prettier and eslint `exclude` lists of `.pre-commit-config.yaml`.

## Member app (/portal)

[The member app](../../../AGENTS.md#the-member-app), `test_published_fields`, `test_house_style`, `test_http_method_hygiene`.

- [ ] An endpoint for the app lives in `churchit/portal/<area>.py`, starts with `access.require_person()` and `access.require_page("<old route>")`, takes the member from the session, and returns explicit fields, never a whole document. The module never contains the text `frappe.qb` or `frappe.db.sql`.
- [ ] A page uses the components in `frontend/src/components`, frappe-ui's semantic tokens only, and `__()` for every string, frappe-ui props included. It works at 390px wide with 44px tap targets, and reads through `useRead` (GET) and writes through `useAction` (POST).
- [ ] `yarn build` in `frontend/` passes and the build output stays out of git. A new npm package was agreed with the maintainer.
- [ ] A change the member should see at once sends `churchit.portal.realtime.notify` from where it happens, never through a doctype room.
- [ ] An old member route keeps working: it redirects into the app (`hooks.py` `website_redirects`), and the app accepts its legacy sub-paths.

## Desk lists, forms, sidebars and workspaces

[Desk lists and forms](../../../AGENTS.md#desk-lists-and-forms), [Desk navigation](../../../AGENTS.md#desk-navigation), `test_desk_ui_hygiene`, `test_navigation_hygiene`, `test_workspace_hygiene`.

- [ ] A Frappe setting does the job before a form script or a hook does. A script or hook gives its reason in the change.
- [ ] A list of 6 desktop columns or more sets a `width` on its title field, so it scrolls sideways instead of cutting the titles (`test_desk_ui_hygiene`).
- [ ] A role's home page is a desk page, because Administrator holds every role and could land outside the setup wizard (`test_home`, [Desk navigation](../../../AGENTS.md#desk-navigation)).
- [ ] Form tour steps follow the order of the fields on the form.
- [ ] A table refuses a repeated person with `churchit/church_people/repeated_rows.py`, and a pair of dates or limits is refused only when one of its fields changes in the save ([Forms](../../../AGENTS.md#forms)).
- [ ] A form tour with Save on Complete has a step on each field the user must type, and onboarding step, tour step and doctype descriptions have no backticks (`test_onboarding_hygiene`).
- [ ] An action on a set of people goes in `churchit/public/js/people_actions.js` for the Person list and the Rolodex to share, and no key or export there is renamed or removed ([Client side](../../../AGENTS.md#client-side)).
- [ ] The pull request has before and after screenshots, desktop and mobile ([Before and after screenshots](../../../AGENTS.md#before-and-after-screenshots)).

## AI features

[AI](../../../AGENTS.md#ai), `test_ai_hygiene`.

- [ ] The feature checks `switch.is_ai_on()` before it offers AI, and an endpoint calls `switch.require_ai(feature)`.
- [ ] AI returns a draft that a person checks and saves. AI code never saves a record by itself.
- [ ] AI code reads with `frappe.get_list` or `get_doc` plus `check_permission`. It does not use `get_all`, `db.count`, `qb` or SQL.
- [ ] Text that guests and members write is data. It never goes into an instruction, and it never chooses a method or a recipient.
- [ ] The feature calls `opt_outs.refuse_kept_away` on its record and leaves kept-away people out of what it sends. A feature that runs without a person asking only enqueues in the request and runs as a named reviewer in a job.
- [ ] A check gets only the answer. The answer names its record, the check reads it again as the caller, and it takes a model value only when it has the expected type. Model text that lands in a field, a title or a Notification Log goes through `escape_html`, and a check on links reads a URL as a browser does ([AI](../../../AGENTS.md#ai), rules 13 to 15).
- [ ] A feature that reads a photo passes the File names to `runner.start(attachments=...)`, and the File is private and attached to its record.
- [ ] An AI result about a request lives on its own record that only the right roles read, such as Church AI Suggestion, never on the request. An alert assigns that record, because every reader of the request sees the request's assignments.

## Tests

[Testing](../../../AGENTS.md#testing).

- [ ] Tests use `churchit/tests/helpers.py` (`make_person`, `make_two_churches`, `assert_scoped`, `set_multi_church`, `force_single_church`). They never find the church with `frappe.db.get_value("Church", {}, ...)`.
- [ ] A new surface that reads church data has a scoping test in `churchit/tests/test_church_permissions.py`. It runs as a Church Manager of one branch, never as Administrator.
- [ ] A class whose tests change shared records extends `RollbackEachTest`. Shared records are made once, in `setUpClass`.
- [ ] Tests set `frappe.local.form_dict`, never `frappe.form_dict`.
- [ ] Tests call `frappe.clear_cache()` at most once for each class.
- [ ] Tests do not depend on order, on the date, or on records that another test made.
