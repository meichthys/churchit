[![Discord](https://img.shields.io/discord/1513373810685116466?logo=discord&label=Discord)](https://discord.gg/AJHKHQXp) [![Matrix](https://img.shields.io/matrix/the-church-app%3Amatrix.org?label=Matrix%20Chat)](https://matrix.to/#/#the-church-app:matrix.org) [![Static Badge](https://img.shields.io/badge/YouTube%20-%20red?style=flat)](https://youtube.com/channel/UCnz8vdrDuI-msXF479NSerg) [![GitHub License](https://img.shields.io/github/license/meichthys/churchit)](https://github.com/meichthys/churchit?tab=readme-ov-file#-license-mit) ![GitHub contributors](https://img.shields.io/github/contributors/meichthys/churchit) ![GitHub last commit](https://img.shields.io/github/last-commit/meichthys/churchit) [![Static Badge](https://img.shields.io/badge/Demo%20-%20User%3A%20demo%40demo.com%20%7C%20Pass%3A%20Matthew10%3A8b%20-%20black?style=flat)](https://church.meichthys.com)

> [!NOTE]
> **This project is looking for additional developers!** If you are interested in contributing, please reach out on the [Discord](https://discord.gg/AJHKHQXp)/[Matrix](https://matrix.to/#/#the-church-app:matrix.org) chat, or [open an issue on GitHub](https://github.com/meichthys/churchit/issues/new).

# ⛪ Churchit

A fully open-source church management system built on the [Frappe Framework](https://frappe.io/framework).

<img width="900" height="504" alt="churchit-tour" src="https://github.com/user-attachments/assets/a636d7d1-6224-4df6-b148-4c3d5818b86e" />

## 🧪 Demo

If you would like to test out the current state of the application, you can try our Demo instance. Please keep in mind that this project is under active development and that there will likely be rough edges, bugs, and incomplete features. If you come across any of these, feel free to report them on our [issue tracker](https://github.com/meichthys/churchit/issues).

[![Demo](./churchit/public/media/demo_button.png)](https://church.meichthys.com/login)

> When logging in, use the following credentials:
> ```
> Username: demo@demo.com
> Password: Matthew10:8b
> ```
> ⚠️ The demo instance is reset every Midnight (EST)

## ✨ Features

The following features have been implemented in this app (see the [🗺️ Roadmap](#-feature-roadmap) below for future plans):

### People & Families
- Comprehensive person profiles with contact info, photos, notes, etc.
- Membership tracking with custom statuses and baptism records
- Family/household management with head-of-household relationship tracking
- Spouse tracking with automatic bidirectional sync
- Church position tracking
- Background check tracking: record checks from any screening provider with status, expiry, and the report; cleared checks expire automatically
- Portal invitations: invite people to a self-service portal

### Portal & Website
- Portal invitations "Invite to Portal" auto-creates a user account and sends a welcome email
- Portal pages for personal details, prayer requests, alms requests, function sign-ups, and bulletin PDFs
- Anonymous prayer request submission (no login required)
- Publishable beliefs/statement of faith
- Publishable missionary profiles with sensitive-info redaction
- Website themes: the shipped **Churchit** look, or Frappe's plain **Standard** look — pick one under Website Settings → Website Theme. Both have a light and a dark mode; visitors switch with the sun/moon button in the navbar, and it follows their system setting until they do

### Functions (Events) & Attendance
- Function (event) tracking with types, scheduling, person & item sign-ups, check-ins, and attendance tracking
- Recurring functions: Functions are automatically created based on a given frequency.
- Calendar view (Private & Public)
- Attendance types (Confirmed, Assumed, Absent, etc.)
- Song tracking for worship services
- Reports: attendance by function, attendance by person, function count by type

### Sermons & Presentations
- Sermon management with slides referencing any church document
- Presentation mode with configurable field display per slide
- Presentation history tracking with date, presenter, and location
- Audio/video recording support
- Sermon handouts: fill-in-the-blank outlines started from the sermon notes, printed as bulletin inserts

### Bulletins
- Printed bulletins per function: a half-fold Letter sheet with a cover image, verse of the week, welcome and announcements
- Sections switched on per bulletin, with defaults in Bulletin Settings: contact information, order of worship, church leadership by configurable roles, upcoming functions, ministries, missionary of the week (rotated weekly, with override), picked prayer requests, birthdays and anniversaries, and a 2-up sermon handout insert
- Published bulletins downloadable as PDFs from the member portal

### Finances
- Collection and donation tracking with fund allocation
- Anonymous donation support
- Payment type tracking (cash, check, etc.)
- Fund management with automatic balance updates on submission
- Fund transfers between accounts
- Expense tracking by category
- Alms request system for financial assistance (with web form)

### Missions
- Missionary profiles with contact info, location, and support details
- Missionary agency tracking
- Support frequency and amount tracking
- Letter/correspondence tracking

### Prayer
- Prayer request management with status tracking and types
- Authenticated and anonymous web-form submissions
- Privacy options (private vs. shared with congregation)
- Prayer recording with topics referencing requests, people, and verses

### Bible & Study
- Full Bible book, verse, and reference structure
- Multiple translation support
- Bible text fetching

### Operations
- Task tracking with document references
- Asset tracking (location, details, status)
- Letter tracking from people and missionaries

### Reports
- Churches overview (people and family counts)
- People report (filterable by name, family, role, membership, baptism)
- Function attendance by type and by person
- Function count by type
- Church directory (printable, with photos, roles, family grouping, and other options)
- Person letters, birthdays, current positions, and more

### Administration
- Role-based access: System Manager, Church Manager, Church User
- Built-in documentation for each module
- Guided setup/onboarding

## 📥 Installing Churchit

There are three ways to run Churchit. Pick the one that fits you:

| | Best for | Cost | Effort |
|---|---|---|---|
| [Frappe Cloud](#frappe-cloud) | Anyone who does not want to run a server | A few dollars/month | Click **Install** |
| [Self-hosted with Docker](#self-hosted-with-docker-recommended) | Running Churchit on your own machine | Free | One command |
| [Existing Frappe bench (Pilot)](#existing-frappe-bench-pilot) | Admins who already run Frappe, or want other Frappe apps alongside Churchit | Free | A few commands |

### Frappe Cloud

1. Log into your [Frappe Cloud](https://frappe.cloud/) dashboard.
2. Open the [Churchit listing on the Frappe Marketplace](https://frappecloud.com/marketplace/apps/church) (or search for "Churchit" from **Marketplace** in the sidebar).
3. Click **Install**, then choose the site you want to install it on.
4. Frappe Cloud handles the download, install, and migrate automatically. Once the deploy completes, log into your site and you should see the `Churchit` icons in the desk.

**To update:** open the site page → **Apps** tab → **Update**.

Frappe Cloud fees go to [Frappe](https://frappe.io/), not to the Churchit maintainers. Churchit itself is free.

### Self-hosted with Docker (recommended)

Runs on any spare Linux machine, VPS, or mini-PC (4 GB+ RAM). Windows (via WSL) and macOS work too with Docker Desktop.

```bash
curl -fsSL https://raw.githubusercontent.com/meichthys/churchit/version-16/deploy/setup.sh | bash
```

The script installs Docker if it is missing, asks for your domain (press Enter to try it out locally at `http://churchit.localhost`), generates passwords, and starts everything. When it finishes it prints your site address and the `Administrator` password.

**To update:**

```bash
cd ~/churchit && docker compose pull && docker compose up -d
```

For Windows/macOS steps, making the site reachable from the internet (domain, DNS, HTTPS, port forwarding), password resets, and uninstalling, see the [self-hosting guide](deploy/README.md).

### Existing Frappe bench (Pilot)

[Pilot](https://github.com/frappe/pilot) is Frappe's official tool for running benches on your own Linux server. Use it if you already have a Pilot bench, or want Churchit next to other Frappe apps. Follow Pilot's README to install it and create a bench, then:

```bash
# Replace "church" with your bench name and church.example.org with your domain.
pilot -b church get-app https://github.com/meichthys/churchit --install-dependencies
pilot -b church new-site church.example.org --apps churchit
pilot -b church setup production
```

**To update:** `pilot -b church update`.

On a plain `bench` (without Pilot), the equivalent is `bench get-app https://github.com/meichthys/churchit`, `bench --site <your-site> install-app churchit`, and `bench update` to upgrade.

### First steps after installing

1. Change the `Administrator` password if you have not already (top-right avatar → **My Settings**). Keep this account for site administration only — do not use it day to day.
2. Create your own user: type `New User` in the search bar. Under **Roles & Permissions**, give the user the `Church Manager` Role Profile and the `Church` Module Profile. This user can manage all aspects of the church.
3. For additional people, create users with the `Church User` Role Profile and the `Church` Module Profile. They can read and update most information, but not critical settings. Open the `Role Permissions Manager` and select `Church Manager` or `Church User` to see exactly what each role can do.

## 🗺️ Feature Roadmap

Hopefully this roadmap will help avoid too much scope creep and provide a sense of where this project is headed. The items below are listed in order of current priority.

- [Add standard church website pages:](https://github.com/meichthys/churchit/issues/13)
  - Calendar
- Additional portal pages
  - Show tracked giving
  - Show tracked attendance
    - Allow updating attendance status(?)

# 🆘 Support
If you need help setting up the app or configuring it, you can reach out in our [Discord server](https://discord.gg/AJHKHQXp) or [Matrix Chat](https://matrix.to/#/#the-church-app:matrix.org).


# 🤖 AI Policy

Disclaimer:This app was developed pre-AI but AI is used in current development of Churchit.

- Fully automated AI pull-requests without personal input will likely be rejected or de-prioritized.

# 🤝 Contributing

Contributions are very welcome! If you plan any large contributions, please let me know first so we can coordinate and make the chances of a merged pull-request more likely.

- Doctype Naming: I've generally been using a single fieldname for the doctype names when the records in the doctype have low chance of clashing. If there is a higher chance of clashing, I've been using multiple fields in the name along with a `{#}` auto increment. The number of digits in the auto-increment are just sane values that should never be exceeded. I then specify the Title Field in the View Settings, and check the `Show Title in LInk Fields` option. This mostly hides the autonumber name from the user and lets the user only see the not-so-confusing name specified in the `Title Field` (sometimes I create a custom field to concatenate values - since the `Title Field` cannot take multiple fields at once afaik.)

## Before you open a pull request

Every pull request runs the same lint and format checks with [pre-commit.ci](https://pre-commit.ci/). A pull request with a failed check cannot merge. Run the checks locally before you push.

1. Install pre-commit once. From this app directory (`apps/churchit` in your bench):

   ```bash
   uv tool install pre-commit   # or: pipx install pre-commit
   pre-commit install
   ```

   After this, `git commit` runs the checks on the files in the commit. A failed check stops the commit. Some hooks fix the files for you (ruff, prettier). Stage the changed files and commit again.

2. To check the whole repository at any time:

   ```bash
   pre-commit run --all-files
   ```

3. Run the tests from the bench root:

   ```bash
   bench --site churchit.localhost run-tests --app churchit
   ```

The hooks are listed in `.pre-commit-config.yaml`. Frappe renders web form scripts (`web_form/*/*.js`) through Jinja. If your script uses Jinja tags, add the file to the `exclude` list of the prettier and eslint hooks, or the JavaScript parser fails on it. Global names that churchit defines for the browser, such as `church`, go in the `globals` list of `.eslintrc`.

## Steps for adding a new doctype:
  - Add a doctype description on the settings tab
  - Add fields for the doctype (if necessary add field descriptions).
  - Add permissions to the doctype for `Church User` and `Church Admin` roles. (Not necessary for child tables)
  - Add the doctype to the relevant workspace. (not necessary for child tables)
  - Document the doctype in the module's `Manual: <Module>` workspace. The manuals are the in-app documentation, so update them whenever user-facing behavior changes. Bump the workspace JSON's `modified` timestamp or `bench migrate` skips it.
  - Set the doctype's `Documentation Link` (Settings tab) to that manual, e.g. `/app/manual%3A-people`. The form's help icon opens it, and `churchit/tests/test_doctype_documentation.py` fails if it is missing.
  - If necessary, add an onboarding step & form tour to explain specific fields.
  - If any default records for this doctype should be shipped with the app, see [Managing App Data](#managing-app-data) below.
  - If necessary, update this readme with the new functionality

## Managing App Data

There are two mechanisms for shipping data with the app. Choosing the right one depends on whether the data belongs to the **app** or to the **user**.

### Fixtures: app-owned data (re-applied on every `bench migrate`)

We use fixtures to load data/configurations that the user should not change. If a user modifies or deletes a fixture record, it will be restored on the next migration.

**Current fixtures in this app:**
- `Role`: church-specific user roles
- `Role Profile`: church-specific user role profiles
- `Property Setter`: customizations to built-in Frappe doctypes

To add a new fixture, add an entry to the `fixtures` list in `hooks.py` and run:
```bash
bench export-fixtures --app churchit
```

### After-install data: user-owned starter data (applied once, on new installs only)

We use `patches/after_install/` for shipping default documents. Users can modify or delete them freely and they will not be recreated on migration or upgrade. Examples: default funds, event types, Bible translations, web pages, etc.

This data is loaded by the `after_install` hook (`churchit.patches.after_install.execute`) which runs only when the app is first installed on a new site. Existing sites are not affected.

#### Process for adding new starter data

Starter data is hand-written directly in `patches/after_install/__init__.py` — there's no Desk-export step or generated data files.

1. Write a `_create_*()` (or `_setup_*()`) function that inserts the record(s), guarded so it's safe to run more than once. Use the `_insert_if_missing()` helper for simple lookups:
   ```python
   def _create_my_lookup():
       for value in ("Foo", "Bar"):
           _insert_if_missing("My Doctype", {"some_field": value}, some_field=value)
   ```
   For anything more involved, check `frappe.db.exists(...)` yourself before inserting; see the other `_create_*`/`_setup_*` functions in the file for examples.
2. Call the function from `execute()`, ordered after anything it depends on (e.g. a parent document before its children).

Demo/sample content (fake people, families, funds, etc. used to try out the app) is a separate concern — it lives in `churchit/setup/sample_data.py` and runs from the `setup_wizard_complete` hook, not `after_install`.

#### Pushing new starter data to existing sites

The `after_install` hook does not run on existing installations. If we need to push new records to **all** sites (new and existing), write a versioned patch instead — same mechanism as [Removing data from existing sites](#removing-data-from-existing-sites) below, just inserting instead of deleting:

```
churchit/patches/v2_0/add_livestream_attendance_type.py
```

```python
import frappe


def execute():
    if not frappe.db.exists("Function Attendance Type", "Livestream"):
        frappe.get_doc({"doctype": "Function Attendance Type", "type": "Livestream"}).insert()
```

Then append to `patches.txt` (always append — never insert above existing entries):

```
churchit.patches.v2_0.add_livestream_attendance_type
```

#### Removing data from existing sites

Removal always requires a hand-written patch — there is no automated utility script for this. Be cautious: check whether the record still exists and whether other records might be linking to it before deleting.

Create a descriptively named patch file alongside the other patches in the relevant version directory:

```
churchit/patches/v2_0/remove_old_attendance_type.py
```

```python
import frappe


def execute():
    if frappe.db.exists("Event Attendance Type", "Old Type"):
        frappe.delete_doc("Event Attendance Type", "Old Type", force=True)
```

Then append to `patches.txt` (always append — never insert above existing entries):

```
churchit.patches.v2_0.remove_old_attendance_type
```


# 🔑 License: MIT-0

```
MIT No Attribution

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

[![Freely given](churchit/public/media/freely_given.svg)](https://sellingjesus.org)
`This resource is freely given (Matt 10:8) for the sake of the gospel`