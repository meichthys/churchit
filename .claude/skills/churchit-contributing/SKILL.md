---
name: churchit-contributing
description: How to change the churchit codebase so that the maintainer can merge the pull request without rework. Use it before you write or change churchit code, doctype JSON, reports, patches, pages, desk scripts, manuals or tests, and before you commit or open a pull request. It gives the workflow, where each rule lives in AGENTS.md, the code style, the checks to run, and the commit and pull request format.
---

# Contributing to Churchit

Churchit is a church management app on Frappe Framework v16. It installs into a Frappe bench like any other Frappe app. The maintainer reviews every pull request by hand. A pull request that follows this skill merges with little rework. A pull request that skips it usually comes back.

## Sources of truth

| File | What it holds |
| --- | --- |
| [AGENTS.md](../../../AGENTS.md) | The rules that a diff does not show and that fail with no error, above all church scoping. AGENTS.md is the authority. This skill tells you which part to read and when. |
| [README.md](../../../README.md#before-you-open-a-pull-request) | Pre-commit setup, the steps for a new doctype, and how the app ships data. |
| [checklist.md](checklist.md) | The merge-ready checklist for each kind of change. The `churchit-reviewer` agent checks the same list. |
| Module docstrings | How each area works. Read the docstring of a module before you change it. |

AGENTS.md has about 2,400 lines, too many to read at once. Find a section with `grep -n '^##' AGENTS.md`, then read from its line to the next heading. When this skill and AGENTS.md disagree, follow AGENTS.md and tell the contributor, so that someone corrects the skill.

## Workflow

### 1. Agree on the scope

- Ask the contributor what problem the change solves, and for whom. The pull request needs this in their words. The maintainer rejects or delays AI pull requests with no personal input ([README "AI Policy"](../../../README.md#-ai-policy)).
- A large change needs the maintainer's agreement before you build it: a new doctype, a new area of the app, or a change across more than one module. Tell the contributor to open a GitHub issue first and to wait for a reply.
- Give each pull request one purpose. Split a feature that has a doctype, reports and a portal page into pull requests that each work alone, schema first.
- Branch from `develop` and open the pull request against `develop`.

### 2. Read the rules

Always read these AGENTS.md sections: [The one invariant](../../../AGENTS.md#the-one-invariant), [Reading data](../../../AGENTS.md#reading-data-the-rule-that-matters-most), [Whitelisted endpoints](../../../AGENTS.md#whitelisted-endpoints-the-desk-is-not-a-rule), [Testing](../../../AGENTS.md#testing) and [House style](../../../AGENTS.md#house-style). Then read the sections for each kind of change:

| You change | Also read in AGENTS.md |
| --- | --- |
| A doctype, or its fields | [Adding a doctype](../../../AGENTS.md#adding-a-doctype), [Records a church can share](../../../AGENTS.md#records-a-church-can-share), [Roles](../../../AGENTS.md#roles), [Desk lists and forms](../../../AGENTS.md#desk-lists-and-forms), [Onboarding steps and form tours](../../../AGENTS.md#onboarding-steps-and-form-tours) |
| A report, dashboard chart or number card | [Adding a report, chart or number card](../../../AGENTS.md#adding-a-report-chart-or-number-card) |
| A notification or an email | [Notifications](../../../AGENTS.md#notifications), [Church Emails, consent and bounces](../../../AGENTS.md#church-emails-consent-and-bounces) |
| A public page, portal page or web form | [Public website and portal](../../../AGENTS.md#public-website-and-portal), [Member portal](../../../AGENTS.md#member-portal) |
| A setting that one church can override | [Settings a church can differ on](../../../AGENTS.md#settings-a-church-can-differ-on) |
| Gifts, funds or expenses | [Giving and the fund ledger](../../../AGENTS.md#giving-and-the-fund-ledger) |
| An outside service (payments, SMS, calendars) | [Integrations](../../../AGENTS.md#integrations) |
| An AI feature | [AI](../../../AGENTS.md#ai) |
| A desk script | [Client side](../../../AGENTS.md#client-side), [Desk lists and forms](../../../AGENTS.md#desk-lists-and-forms) |
| A workspace, a sidebar or the dock | [Desk navigation](../../../AGENTS.md#desk-navigation), [Sidebars and workspaces](../../../AGENTS.md#sidebars-and-workspaces) |
| Shipped records, a patch, or a renamed or removed field | [README "Managing App Data"](../../../README.md#managing-app-data) and the patch items in [checklist.md](checklist.md) |
| An area with its own section (people, sign-ups, room bookings, care, follow-up cards and others) | That section. Find it with grep. |

Also skim [Frappe behaviours worth knowing](../../../AGENTS.md#frappe-behaviours-worth-knowing) once. Most surprises in review come from it.

### 3. Show a design before you build

For anything larger than a small fix, show the contributor a short design and wait for agreement. Include:

- The Frappe features that do the work. Churchit wants native Frappe at fit 4 or better: 5 is shipped configuration or records, 4 is a standard doctype, controller, hook or Frappe API with light glue, 3 is custom logic. Accept fit 3 only for a real Frappe gap or for security, and say why. Look first for the Frappe feature that already does the job (Notification, Assignment, Kanban, Workflow, Web Form, Report Builder, Number Card, Communication). Do not use the features in [Frappe features that churchit does not use](../../../AGENTS.md#frappe-features-that-churchit-does-not-use).
- Each new doctype and field, its name, and the church that each record belongs to (or why the record is global).
- The roles that read and change each record.
- How data ships: a fixture, after-install starter data or a versioned patch. Say what existing sites need, and how they keep working after the upgrade.
- The manual, onboarding and tests that change.

### 4. Write the code

Follow "Code style" below and the items in [checklist.md](checklist.md) for each kind of change. Build the smallest change that works, then extend it. Change only the files that the change needs.

### 5. Run the checks

See "Checks" below. Run the full test suite before you open the pull request.

### 6. Review

Run the `churchit-reviewer` agent on the branch. Fix each blocking finding, then run the checks again. Show the contributor the diff and the findings that you did not fix. The contributor reads the diff before the pull request opens, because they own it.

### 7. Commit and open the pull request

See "Commits" and "Pull requests" below. Do not push or open the pull request until the contributor asks.

## Code style

### Python

- Ruff settings are in `pyproject.toml`: tabs, 110 columns, double quotes. Use ruff 0.8.1, the version that pre-commit pins (`uvx ruff@0.8.1`). Format only the files that you changed. A whole-repo format rewrites old files and hides your change in noise.
- Put code where its area lives: the doctype controller for one record, a named module in its `churchit/church_<module>/` folder for an area (`household.py`, `derived.py`). Do not add `utils`, `helpers` or `common` modules.
- Use the shared modules before you write a new helper: `churchit/church_scope.py` (church filters), `churchit/contacts.py` (email, phone and address tables), `churchit/utils.py` (`set_report_link_titles`), `churchit/query.py`, `churchit/dashboard.py` (people counts and chart helpers), `churchit/scripture.py` (Bible references) and `churchit/tests/helpers.py`.
- A new Python or JavaScript file starts with the two-line "freely given" notice that its neighbors carry. The pre-commit hook puts it into the files that Frappe generates.
- A module starts with a docstring that says what the module owns. A class docstring is one line that says what the record is.
- A function docstring is one short line that says what the function returns or does, with parameter names in `*asterisks*`: `"""*person*'s household role on their family's roster, or None."""`. Add a paragraph only for what the code does not show.
- Give public functions type hints. A whitelisted function gives every parameter a type hint.
- Use whole words, not abbreviations. Start a boolean name with `is_` or `has_`. Make a computed value with no arguments a `@property`. Call a function that takes arguments and returns a value `get_<what_it_returns>()`.
- Keep functions short (about 25 lines) with little branching, and modules under about 500 lines. Do not split a readable function into single-use helpers.
- Keep comments short. A comment says why, never what the next line does. Put the long explanation in the commit message.
- Wrap user-facing text in `_()` with numbered placeholders: `_("{0} belongs to another church.").format(name)`. Never put an f-string inside `_()`.
- Refuse with `frappe.throw(_("..."))` and a sentence that the user can act on, or with a specific exception. Catch only an error that the code can recover from. At an outside service, log with `frappe.log_error` and tell the user. Never hide an error with `except Exception: pass`.
- Do not call `frappe.db.commit()` in a request, a document event or a whitelisted function. Frappe commits at the end of the request.
- Use `ignore_permissions=True` only after the code has checked that the caller may make the same change.
- Do not add a dependency to `pyproject.toml` unless the maintainer agrees. Do not commit a `uv.lock` change that your change does not need.

### JavaScript

- Pre-commit runs prettier and eslint. Add a global that churchit defines for the browser, such as `church`, to `.eslintrc`.
- Wrap user-facing text in `__()`.
- Call a read method with GET: `frappe.xcall(method, args, "GET")`.
- Read church state from `frappe.boot.churchit`, not from a server call.
- Decide what a form shows in the field's `depends_on`, not with `frm.toggle_display` on refresh.

### Doctype and other shipped JSON

- Change a doctype in the desk with developer mode on, so that Frappe writes the JSON. Do not reformat a JSON file by hand.
- When you edit a Workspace, Report, Dashboard or other shipped JSON by hand, set `modified` to the current time. Migrate skips the file without it. Never set a future time.

### Prose

This covers manuals, the README, docstrings, commit messages and pull requests.

- Write Simplified Technical English: short sentences, active voice, common words, one name for one thing.
- Never write an em dash or an en dash, in any file. `test_house_style` fails on one. Rewrite the sentence with a comma, a colon, a full stop or "to".
- Write the manuals for a church volunteer, not for a developer ([Documentation obligations](../../../AGENTS.md#documentation-obligations)).

## Checks

From the bench root. Do the first two once:

```bash
bench set-config -g developer_mode 1                    # the desk saves doctype changes as JSON
bench --site <test-site> set-config allow_tests true
bench --site <site> migrate                             # after a doctype, fixture, workspace or patch change
bench --site <test-site> run-tests --module churchit.church_people.doctype.person.test_person
bench --site <test-site> run-tests --app churchit       # the full suite, a few minutes
```

From the app directory:

```bash
pre-commit run --files <changed files>
```

- The full suite deletes and creates the sample data again on its site. Run it on a test site, not on a site with data that you need.
- CI runs only the lint checks, not the tests. The maintainer relies on the test run that you report.
- When a test also fails on a clean `develop`, do not fix it in your pull request. Name it in the pull request.
- Check the change in the browser as a Church Manager on a site with the sample data: `mary.johnson@example.com`, with the email as the password. Do not check as Administrator, because church permissions do not apply to it. Then turn on multi-church in Church Features, add a branch church, and make sure that a branch user does not see the records of another church.
- Take the screenshots that [Before and after screenshots](../../../AGENTS.md#before-and-after-screenshots) asks for. `.claude/skills/run-churchit/driver.py --url <site URL>` can take them.

## Commits

- Subject: `type(scope): Sentence case`, under about 72 characters. Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `chore`. The scope is the module name without `church_` (`people`, `finances`, `ministries`, `missions`, `prayers`, `foundations`, `study`, `communications`, `operations`, `website`, `setup`, `summary`, `help`), or `ai`, `desk` or `manuals`.
- Body: the problem first, then the final state, in plain sentences. No file list and no step-by-step story.
- Each commit passes ruff and the tests on its own.

Example:

```text
fix(prayers): Keep private prayer requests off the community page

The community page listed every request whose church matched, so a
request marked Private showed to every signed-in member. The page now
reads with get_list and leaves out Private requests.
```

## Pull requests

Title: the Conventional Commit format of the main commit. Description:

```text
Closes #<issue>

## Summary
<One or two sentences: the capability or the fix, and why it matters.>

## Why
<The contributor's reason, in their words.>

## What changed
- <Behavior, settings, roles and permissions, patches, anything that a reviewer must know. No file names.>

## Tests
<The commands that you ran and their result. Name each failure that is also on develop.>

## Screenshots
<Before and after, desktop and mobile, for a desk or portal change. Omit for other changes.>
```

Leave out the `Closes` line when there is no issue.
