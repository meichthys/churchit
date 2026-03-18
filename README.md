[![Matrix](https://img.shields.io/matrix/the-church-app%3Amatrix.org?label=Matrix%20Chat)](https://matrix.to/#/#the-church-app:matrix.org) [![GitHub License](https://img.shields.io/github/license/meichthys/church)](https://github.com/meichthys/church?tab=readme-ov-file#-license-mit) ![GitHub contributors](https://img.shields.io/github/contributors/meichthys/church) ![GitHub last commit](https://img.shields.io/github/last-commit/meichthys/church) [![Static Badge](https://img.shields.io/badge/Demo%20-%20User%3A%20demo%40demo.com%20%7C%20Pass%3A%20Matthew10%3A8b%20-%20black?style=flat)](https://church.meichthys.com)

> [!WARNING]
> This app is not ready for production. Large changes should be expected until a 1.0.0 version is released.

# ⛪ Church

A fully open-source church management system built on the [Frappe Framework](https://frappe.io/framework).

![](./church/public/media/feature_image.png)



## 🧪 Demo

If you would like to test out the current state of the application, you can try our Demo instance. Please keep in mind that this project is under active development and that there will likely be rough edges, bugs, and incomplete features. If you come across any of these, feel free to report them on our [issue tracker](https://github.com/meichthys/church/issues).

[![Demo](./church/public/media/demo_button.png)](https://church.meichthys.com/login)

> When logging in, use the following credentials:
> ```
> Username: demo@demo.com
> Password: Matthew10:8b
> ```
> ⚠️ The demo instance is reset every Midnight (EST)

## ✨ Features

The following features have been implemented in this app (see the [🗺️ Roadmap](#-feature-roadmap) below for future plans):

### Multi-Church Support
- Hierarchical church structure
- All data is scoped to a church — users only see what they have access to
- Church filter auto-hides in single-church setups for a cleaner experience

### People & Families
- Comprehensive person profiles with contact info, photos, notes, etc.
- Membership tracking with custom statuses and baptism records
- Family/household management with head-of-household relationship tracking
- Spouse tracking with automatic bidirectional sync
- Church position tracking
- Portal invitations: invite people to a self-service portal

### Portal & Website
- Portal invitations — one-click "Invite to Portal" auto-creates a user account and sends a welcome email
- Portal pages for personal details, prayer requests, and alms requests
- Anonymous prayer request submission (no login required)
- Publishable beliefs/statement of faith
- Publishable missionary profiles with sensitive-info redaction

### Events & Attendance
- Function (event) tracking with types, scheduling, and attendance
- Attendance types (Confirmed, Assumed, Absent, etc.)
- Song tracking for worship services
- Reports: attendance by function, attendance by person, function count by type

### Sermons & Presentations
- Sermon management with slides referencing any church document
- Presentation mode with configurable field display per slide
- Presentation history tracking with date, presenter, and location
- Audio/video recording support

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

## 📥 Installing Frappe

To use the 'Church' app, you must have a working Frappe environment first. There are a variety of ways to install a Frappe instance.
  If you are running a Frappe v15 environment, then use the `version-15` branch.
  If you are running a Frappe v16 environment, then use the `version-16` branch

The recommended ways for installig this project are:

### ☁️ In the Cloud
The easiest (but not free) way to get a working Frappe environment is to use [Frappe Cloud](https://frappe.io/cloud). For a few dollars per month you can run an instance in the cloud. You get your choice of support options and shouldn't need to worry about data loss yourself.
Note: With this option, the money you pay to FrappeCloud is not received by maintainers of this 'Church' app. - We offer the 'Church' software for free, but you pay the cloud hosting costs to [Frappe](https://frappe.io/).

### 💪 Self-Host
If you're the more technical and/or frugal type, you can self-host an instance of the Church app on a home pc or server. [Frappe Manager](https://github.com/rtcamp/frappe-manager) can be used to quickly setup a local frappe instance. It's not as easy as a simple app install, but we think you can do it (Please ask us for help if you can't)! The general steps are:

1. Find a machine onto which you can install Frappe (A dedicated linux-based machine is best. Windows is possible, but is not recommended as it requires some extra steps and the use of [WSL](https://learn.microsoft.com/en-us/windows/wsl/install).)
2. Run the [frappe-manager install script](https://github.com/rtCamp/Frappe-Manager/tree/develop/scripts)
3. Create a new site using frappe-manager: `fm create -e prod <church.your_site.com>`.
4. Update DNS records to point to your new site. This is a bit outside the scope of this project, but basically you need to either update your hosts file to map your site url (used in the above command) to the ip address of the machine hosting the frappe instance. Alternatively, you can update your DNS server on your router to point to your new site. If you need help with this, you can file an issue and I'd be glad to schedule a call to try to help you set it up.

Making a local instance of frappe accessible from outside of your network is currently out of the scope of this project, but with some persistence and some technical expertise, it can be achieved. If you are completely lost or uncomfortable with this, it may be best to use the Frappe Cloud option above, or contact us for help. We'd be glad to help where we can.

## ⛪ Installing this Church app
To install this app on your frappe instance:

- If hosting on Frappe Cloud, you should be able to log into your Frappe Cloud dashboard, select your site, and install the app from the list of apps.
- If you are self-hosting, you can use bench by activating the [bench](https://github.com/frappe/bench) environment with `fm shell` and then running the following

  ```bash
  # Set the bench command to use your site (Replace `<church.your_site.com>` with your actual site name):
  bench use <church.your_site.com>

  # Download the app:
  bench get-app https://github.com/meichthys/church
  ## Or if you want to try the latest development version:
  bench get-app https://github.com/meichthys/church --branch develop

  # Install the app:
  bench install-app church

  # Migrate the app for good measure:
  bench migrate

  # In the future, to update the app to the latest version, log into the host server and run:
  fm shell
  bench update
  bench migrate
  ```

After the above installation you should be able to access the web interface using the URL you defined in the `bench create` command above. You should see the `Church` app installed when you view `Help > About`.

Before you start using the app be sure to:

1. Change the `Administrator` users's password (the default is `admin`). This user should only be used by the site administrator - and should not be used on a daily basis.
2. Setup a new user in the system by typing `New User` in the searchbar. Under the "Roles & Permissions" tab, Give this user the `Church Manager` Role Profile and `Church` Module Profile.
   This user will be able to manage all aspects of the church.
3. If you want more than one user on the system, or if you want to delegate some responsibilities to other people, you can create additional users with the `Church User` Role Profile and `Church` Module Profiles.
   These types of users will be able to read and update most information, but not certain critical information.
   - To see a list of permissions you can open the `Role Permissions Manager` and select the `Church Manager` or `Church User` roles to see what permissions these users roles have.

## 🗺️ Feature Roadmap

Hopefully this roadmap will help avoid too much scope creep and provide a sense of where this project is headed. The items below are listed in order of current priority.

- [Add standard church website pages:](https://github.com/meichthys/church/issues/13)
  - Calendar
- Additional portal pages
  - Show tracked giving
  - Show tracked attendance
    - Allow updating attendance status(?)
- Add Onboarding Tours
  - Add 'Tutorial' button to each doctype form

# 🆘 Support
If you need help setting up the app or configuring it, you can reach out in our [Matrix Chat](https://matrix.to/#/#the-church-app:matrix.org).

# 🤝 Contributing

Contributions are very welcome! If you plan any large contributions, please let me know first so we can coordinate and make the chances of a merged pull-request more likely.

- Doctype Naming: I've generally been using a single fieldname for the doctype names when the records in the doctype have low chance of clashing. If there is a higher chance of clashing, I've been using multiple fields in the name along with a `{#}` auto increment. The number of digits in the auto-increment are just sane values that should never be exceeded. I then specify the Title Field in the View Settings, and check the `Show Title in LInk Fields` option. This mostly hides the autonumber name from the user and lets the user only see the not-so-confusing name specified in the `Title Field` (sometimes I create a custom field to concatenate values - since the `Title Field` cannot take multiple fields at once afaik.)

## Steps for adding a new doctype:
  - Add a doctype description on the settings tab
  - Add fields for the doctype (if necessary add field descriptions).
  - Add permissions to the doctype for `Church User` and `Church Admin` roles. (Not necessary for child tables)
  - Add the doctype to the relevant workspace. (not necessary for child tables)
  - If necessary, add an onboarding step & form tour to explain specific fields.
  - If any default records for this doctype should be shipped with the app, see [Managing App Data](#managing-app-data) below.
  - If necessary, update this readme with the new functionality

## Managing App Data

There are two mechanisms for shipping data with the app. Choosing the right one depends on whether the data belongs to the **app** or to the **user**.

### Fixtures — app-owned data (re-applied on every `bench migrate`)

We use fixtures to load data/configurations that the user should not change. If a user modifies or deletes a fixture record, it will be restored on the next migration.

**Current fixtures in this app:**
- `Role` — church-specific user roles
- `Role Profile` — church-specific user role profiles
- `Property Setter` — customizations to built-in Frappe doctypes

To add a new fixture, add an entry to the `fixtures` list in `hooks.py` and run:
```bash
bench execute church.utils.export_fixtures
```

### After-install data — user-owned starter data (applied once, on new installs only)

We use `patches/after_install/` for shipping default documents. Users can modify or delete them freely and they will not be recreated on migration or upgrade. Examples: default funds, event types, Bible translations, web pages, etc.

This data is loaded by the `after_install` hook (`church.patches.after_install.execute`) which runs only when the app is first installed on a new site. Existing sites are not affected.

#### Process for adding new starter data

1. Set up the records in the Frappe desk exactly as you want them shipped.
2. Add the doctype as a fixture in `hooks.py` with a `"patch": "after_install"` key (leave it there permanently — it tells the `update_patches` utility script where to move the files):
   ```python
   {"dt": "My Doctype", "filters": [...], "patch": "after_install"}
   ```
   Use the optional `"order"` key if this doctype must be inserted before others (e.g. a parent document before its children):
   ```python
   {"dt": "My Doctype", "filters": [...], "patch": "after_install", "order": 4}
   ```
3. Run the `export_fixtures` utility script — it exports all fixtures and automatically moves patch fixture files into `patches/after_install/data/`:
   ```bash
   bench execute church.utils.export_fixtures
   ```
   - If the file is **new or changed**, it is moved to `patches/after_install/data/`.
   - If the file is **identical** to the existing one, it is removed (no change needed).

> [!WARNING]
> Never run `bench export-fixtures` directly. Always use `bench execute church.utils.export_fixtures` instead, which handles routing patch fixture files automatically.

#### Pushing new starter data to existing sites

The `after_install` hook does not run on existing installations. If we need to push new records to **all** sites (new and existing), we can use a versioned patch instead:

1. Add the doctype as a fixture in `hooks.py` with `"patch": "<patch_name>"` (e.g. `"patch": "v2_0"`).
2. Run the `export_fixtures` utility script — it exports all fixtures, moves the files, scaffolds `__init__.py` and `insert_data.py` from the template, and registers the patch in `patches.txt` automatically:
   ```bash
   bench execute church.utils.export_fixtures
   ```

#### Removing data from existing sites

Removal always requires a hand-written patch — there is no automated utility script for this. Be cautious: check whether the record still exists and whether other records might be linking to it before deleting.

Create a descriptively named patch file alongside the other patches in the relevant version directory:

```
church/patches/v2_0/remove_old_attendance_type.py
```

```python
import frappe


def execute():
    if frappe.db.exists("Event Attendance Type", "Old Type"):
        frappe.delete_doc("Event Attendance Type", "Old Type", force=True)
```

Then append to `patches.txt` (always append — never insert above existing entries):

```
church.patches.v2_0.remove_old_attendance_type
```

# 🔑 License: MIT

>You can copy, translate, modify, and distribute this resource, without restriction, and without needing to ask permission. This resource is freely given (Matt 10:8) for the sake of the gospel.

![Freely given](church/public/media/freely_given.svg)
