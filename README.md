<div align="center">

<img src="./churchit/public/media/church_logo.png" alt="Churchit logo" width="128" height="128" />

# Churchit

**A fully open-source church management system built on the [Frappe Framework](https://frappe.io/framework).**

[![Discord](https://img.shields.io/discord/1513373810685116466?logo=discord&label=Discord)](https://discord.gg/YxpdU6qM5w)
[![Matrix](https://img.shields.io/matrix/the-church-app%3Amatrix.org?label=Matrix%20Chat)](https://matrix.to/#/#the-church-app:matrix.org)
[![Static Badge](https://img.shields.io/badge/YouTube%20-%20red?style=flat)](https://youtube.com/channel/UCnz8vdrDuI-msXF479NSerg)
<br />
[![GitHub License](https://img.shields.io/github/license/meichthys/churchit)](https://github.com/meichthys/churchit?tab=readme-ov-file#-license-mit)
![GitHub contributors](https://img.shields.io/github/contributors/meichthys/churchit)
![GitHub last commit](https://img.shields.io/github/last-commit/meichthys/churchit)
<br />
[![Static Badge](https://img.shields.io/badge/Demo%20-%20User%3A%20demo%40demo.com%20%7C%20Pass%3A%20Matthew10%3A8b%20-%20black?style=flat)](https://demo.churchit.app)

[Demo](#-demo) · [Features](#-features) · [Screenshots](https://churchit.app/screenshots.html) · [Roadmap](#-feature-roadmap) · [Install](#-installing-churchit) · [Get help](https://discord.gg/YxpdU6qM5w)

<img width="900" height="504" alt="churchit-tour" src="https://github.com/user-attachments/assets/a636d7d1-6224-4df6-b148-4c3d5818b86e" />

</div>

> [!NOTE]
> **This project is looking for additional developers!** If you are interested in contributing, please reach out on the [Discord](https://discord.gg/YxpdU6qM5w)/[Matrix](https://matrix.to/#/#the-church-app:matrix.org) chat, or [open an issue on GitHub](https://github.com/meichthys/churchit/issues/new).

## 🧪 Demo

If you would like to test out the current state of the application, you can try our Demo instance. Please keep in mind that this project is under active development and that there will likely be rough edges, bugs, and incomplete features. If you come across any of these, feel free to report them on our [issue tracker](https://github.com/meichthys/churchit/issues).

[![Demo](./churchit/public/media/demo_button.png)](https://demo.churchit.app/login)

> When logging in, use the following credentials:
> ```
> Username: demo@demo.com
> Password: Matthew10:8b
> ```
> ⚠️ The demo instance is reset every Midnight (EST)

## ✨ Features

The following features have been implemented in this app (see the [🗺️ Roadmap](#-feature-roadmap) below for future plans):

### People & Families
- Comprehensive person profiles with contact info, photos, life events, school grade and an engagement panel (attendance heatmap, groups, serving, giving)
- Membership tracking: how each person is connected (Member, Regular Attender, Visitor, Contact), an Active or Inactive status with a reason, and baptism records
- Family/household management with household roles, spouse sync and authorized pickups
- Church position tracking
- Person Notes in categories that decide who reads them, with alert notes at the top of the form
- Follow-up workflows on a Kanban board per workflow, started by a guest card, a first check-in, an event sign-up, a form, a membership change, a life event or a smart list
- Smart lists: saved reports of people with email, Rolodex, group and Church Email actions
- Pathways: ordered steps, each a smart list, with a progress report; an Assimilation Funnel report
- Care requests with a caregiver and due date, and background checks a position or a group can require
- Duplicate warnings, merging, and imports from Planning Center, Rock RMS or a spreadsheet
- Envelope numbers, unique in each church, that find the giver in a gift's Person field
- Remove Personal Data on request or after a set number of inactive years
- A Map of Addresses
- Portal invitations: invite people to a self-service portal

### Groups
- Group types (Small Group, Class, Support Group, Youth Group) that fill in a new group's defaults
- Group meetings are Functions: Set Up Meetings makes a group's recurring schedule, and the group shows when and where it meets
- A capacity, a closing date and leader approval for each group; members ask to join from the portal or from the public Find a Group page
- Find a Group: a public page with a map and type and day filters, which shows the city of each group's meeting place but never the street
- Lead a Group: on the portal, leaders see their members, record attendance, approve or deny join requests and message their group. They get a reminder the day after a meeting with no attendance recorded
- Group files: leaders share private files with the members of their group on the portal
- Background checks that a group can require of its leaders or of every member
- A Group Attendance report, and a group filter on the attendance reports

### Portal & Website
- Portal invitations "Invite to Portal" auto-creates a user account and sends a welcome email
- Portal pages for personal details, my household, a member directory with per-person sharing, communication preferences, prayer requests, alms requests, function sign-ups, attendance history, giving statements, pledges, room requests, and bulletin PDFs
- Forms: publish a Question Set as a web form for anyone or only members, with an optional price, and follow up each response
- A guest Connection Card with a QR code, a one-time link for a person to update their details without a login, and new portal logins linked to their person
- Anonymous prayer request submission (no login required)
- Publishable beliefs/statement of faith
- Publishable missionary profiles with sensitive-info redaction
- Website themes: the shipped **Churchit** look, or Frappe's plain **Standard** look. Pick one under Website Settings → Website Theme. Both have a light and a dark mode; visitors switch with the sun/moon button in the navbar, and it follows their system setting until they do

### Functions (Events) & Attendance
- Function (event) tracking with types, scheduling, person & item sign-ups, check-ins, and attendance tracking
- Event registration: guests and members register on the public Register page between open and close dates (the page is not in the website menu until you add it), and bring their household or others they name
- A capacity for each function and each selection (such as Adult or Child), limited sign-up items, a waitlist that fills freed seats, and sign-up approval by staff
- Prices for selections and items, discount codes, early bird and group discounts, a one-click Freely Given discount that makes a function free, and online payment with a Pay now link; Finance records offline payments and refunds
- Registration questions for each attendee, a confirmation email with a calendar file, and reminders by email and text before the event
- Check-In Station: search by name or phone number or scan a Member QR Card, check whole families in with a tap, and add first-time visitors on the spot after the station offers people already on file. Each person shows their grade and allergies, and check-in volunteers also see medical notes and an emergency contact
- A live list at the station that shows the check-ins and checkouts of other stations within seconds, with photos, the booked rooms and a name or code filter. From it, undo, reprint, check out people who have no pickup tag, and page a child's parents by text or email
- Pickup: verify a pickup code, typed or scanned from the QR code on the pickup tag, and record who collected each child. Authorized Pickups and Pickup Restrictions say who may and who may not collect a child, and only a Church Manager can override a restriction
- Age and grade limits on a function, room capacity from its room bookings (warn or block), and a headcount for people in the room who are not checked in by name: the attendance total uses the larger count
- Volunteer check-in from a Team tab that lists the function's accepted ministry team, with the position on the volunteer's name tag
- Self check-in kiosk: a family types its phone number on a tablet at the door, picks who to check in, and takes its name tags. Only Function types that allow self check-in, and only from a set number of minutes before the start to the end
- Pre check-in: a member picks who is coming to today's function on My Household and shows a QR code at the Check-In Station or the kiosk. The code works only until the function ends
- Name tags: printed per check-in through the browser's print dialog (any printer), or silently in ZPL to Zebra label printers such as the ZD421 via Zebra Browser Print, QZ Tray, or straight over the network. Optional pickup codes for children's ministry print on each tag and on a parent pickup tag; a household keeps one code for the day. Each kind of check-in (Regular, Guest, Volunteer) can print its own tag. The label layouts are Print Formats a church can copy and customize
- Recurring functions: every n days, weeks, months or years, on a day of the month or a weekday of the month (the second Sunday), created weeks ahead for the calendar, with skip dates and room bookings
- Calendar view (Private & Public). The public calendar shows the rooms, a map, an online meeting link and a link to open each function, and it can include the functions of branch churches
- A public calendar feed that visitors subscribe to in their phone or computer calendar, for the whole church or one published ministry, with Subscribe and Download .ics links on the Calendar page
- Link-only functions that do not show on the calendar, the feed, the home page or the Register list, but open from their link
- Attendance types (Confirmed, Assumed, Absent, etc.)
- Song tracking for worship services, and a Song Usage report with CCLI numbers for CCLI reporting
- Reports: attendance by function, attendance by person, function count by type

### Ministry Teams
- Ministry team positions (e.g. Greeter, Usher, Nursery Worker) with the people who can fill each one, and an optional background check rule
- Team needs on each function, copied to recurring functions from their template
- Assignments that ask one person to fill one position, with warnings for blocked dates, double booking, missing background checks and missing email addresses
- Request and reminder emails with accept and decline links that work without signing in, and an email to the ministry's coordinator for each decline
- A portal page where members answer their requests, see the schedule of each function they serve at, and block out the dates they cannot serve
- A calendar link that shows each member the functions they accepted in their phone or computer calendar
- Email the Team on a function: one email, in BCC, to everyone asked to serve who has not declined
- Ministry Team Schedule report: what each function needs, who is asked, and which places are still open

### Sermons & Presentations
- Sermon management with slides referencing any church document
- Presentation mode with configurable field display per slide
- Presentation history tracking with date, presenter, and location
- Audio/video recording support
- Sermon handouts: fill-in-the-blank outlines started from the sermon notes, printed as bulletin inserts

### Bulletins
- Printed bulletins per function: a half-fold Letter sheet with a cover image, verse of the week, welcome and announcements
- Sections switched on per bulletin, with defaults in Bulletin Settings: contact information, church verse, order of worship, church leadership by configurable roles, upcoming functions, ministries, missionary of the week (rotated weekly, with override), picked prayer requests, birthdays and anniversaries, and a 2-up sermon handout insert
- Published bulletins downloadable as PDFs from the member portal

### Church Emails & Consent
- One email or text to active people, active members, a Group, a smart list or chosen people, each person getting their own copy on their timeline
- Email templates, name placeholders, a preview, a test send and a scheduled send time
- Consent per channel and purpose: texts need a yes, every email has an unsubscribe link for its purpose, and churches that ask first can send consent renewal reminders
- Bounced addresses and refused texts are marked, and later emails skip them

### Finances
- Collection and donation tracking with fund allocation
- Anonymous donation support
- Payment type tracking (cash, check, etc.)
- Fund management with automatic balance updates on submission
- Fund transfers between accounts
- Expense tracking by category
- Alms request system for financial assistance (with web form)
- Online giving on /give through Stripe or PayPal, with an optional processing fee that the giver can cover
- Give links and QR codes for a fund, which open /give with the fund and an amount filled in
- Other ways to give (bank transfer, standing order, mailed check) on /give, per church
- Event registration fees and form payments recorded as collections at the event's church, off giving statements
- Finance can link a guest's online gift to a person, and a cancelled gift Collection marks the gift Refunded
- Non-cash gifts (donated property) recorded with a description and no value
- Funds that are not tax deductible stay off giving statements
- Email every giving statement with its PDF in one step
- Pledge campaigns: members pledge on the portal, and the Pledge Progress report compares each pledge and each campaign goal with the gifts received
- Import giving history from another system, a spreadsheet or a payment processor's export into draft collections
- GL export: map funds, payment types, expense types and the church to accounts, and export a balanced GL Journal as CSV

### Missions
- Missionary profiles with contact info, location, and support details
- Missionary agency tracking
- Support frequency and amount tracking
- Letter/correspondence tracking

### Prayer
- Prayer request management with status tracking and types
- Authenticated and anonymous web-form submissions
- Who can see each request: private, the prayer team, or the whole church
- Prayer recording with topics referencing requests, people, and other records

### Bible & Study
- A Bible reader in the desk and on the website, one chapter at a time
- Bible translations that keep their own text: the default one downloads at install, each other free translation downloads itself the first time someone opens it, and a translation that is not free takes an import of a licensed copy that only signed-in users can read
- Downloads from a self-hosted copy of the Free Use Bible API when the site config key `free_use_bible_api_url` names one
- Bible references typed as plain text (such as `Romans 8:28-30; Psalm 23`) on churches, bulletins, beliefs, sermon slides and Bible Memory, kept as typed rather than reordered or expanded into verses, with their text from the church's default translation
- Bible Memory practice in the portal, with passages managers can assign to people and groups

### Operations
- Task tracking with document references
- Asset tracking (location, details, status)
- Room booking with approvers for each room, blocked times, and conflicts that an approver resolves by keeping one booking or sharing the room
- Equipment booking (bookable Church Assets) with a room or on its own, and several rooms for a Function from one dialog. Each church names its rooms freely, so two campuses can each have a Sanctuary
- Room setups (such as Banquet or Theatre) and room questions on each booking, and a Setup Sheet to print for the people who set up the room
- A room calendar in the desk, a Room Usage report, and a Book a Room page where members ask for a room
- Letter tracking from people and missionaries

### Reports
- Churches overview (people and family counts)
- People report (filterable by name, family, role, membership, baptism)
- Function attendance by type and by person, with a group filter
- Function Registrations: one row per attendee with the status, the payment and a column for each question
- Group attendance: meetings held, average attendance and attendance rate for each group
- Function count by type
- Room Usage: one row per room booking in a date range with its room, equipment, hours, status and requester
- Church directory (printable, with photos, roles, family grouping, and other options)
- Person letters, birthdays, current positions, and more

### Administration
- Role-based access: a Church Manager, desk roles for staff (Staff, People Editor, Pastoral Care, Finance, Check-In) bundled into role profiles, Church User for portal members, and Church Check-In Kiosk for a self check-in device
- Optional multi-church mode: branch or satellite churches under one main church, with every record and user scoped to a church (parent-church users can include branches), per-church emails and notifications, and a Locations switcher on the public website
- A people directory shared by every church: any church can look up a person or family, only their own church can change them, and a Church Features option keeps each church's people private instead
- Songs, sermons, vendors, rooms, assets, funds and ministries can be shared with every church, so branches reuse the main church's library and give to joint funds, while each gift and expense keeps the church that gave or spent it
- Built-in documentation for each module
- Guided setup/onboarding

## 📥 Installing Churchit

There are three ways to run Churchit. Pick the one that fits you:

|                                                                 | Best for                                                                    | Cost                | Effort            |
| --------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------- | ----------------- |
| [Frappe Cloud](#frappe-cloud)                                   | Anyone who does not want to run a server                                    | A few dollars/month | Click **Install** |
| [Self-hosted with Docker](#self-hosted-with-docker-recommended) | Running Churchit on your own machine                                        | Free                | One command       |
| [Existing Frappe bench (Pilot)](#existing-frappe-bench-pilot)   | Admins who already run Frappe, or want other Frappe apps alongside Churchit | Free                | A few commands    |

### Frappe Cloud

1. Create a free account at [Frappe Cloud](https://frappecloud.com/dashboard/signup) and verify your email address.
2. Click **New Site**. Choose the **Version 16** release group, a region, and a plan. The cheapest plan is fine for a typical church. Enter a site name (for example `mychurch`) and click **Create Site**.
3. Wait for the site to finish creating.
4. Open the [Churchit listing on the Frappe Marketplace](https://frappecloud.com/marketplace/apps/churchit) (or search for "Churchit" from **Marketplace** in the sidebar).
5. Click **Install**, then choose the site you created. Frappe Cloud handles the download, install, and migrate automatically.
6. Once the install completes, go to **Sites** → your site name → **Visit Site** and complete the setup wizard.
7. To use your own domain, see [Setting up a public domain](#setting-up-a-public-domain).

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

For Windows/macOS steps, password resets, and uninstalling, see the [self-hosting guide](deploy/README.md). To make the site reachable from the internet with your own domain, see [Setting up a public domain](#setting-up-a-public-domain).

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

Churchit cannot share a site with an app that has a doctype of the same name. Today this includes ERPNext (Budget, Location), Frappe Learning (Function) and Frappe Suite (Email Address, Slide). Installing Churchit on such a site, or installing such an app on a Churchit site, stops with an error that names the shared doctypes.

To make the site reachable from the internet with your own domain, see [Setting up a public domain](#setting-up-a-public-domain).

### First steps after installing

1. Change the `Administrator` password if you have not already (top-right avatar → **My Settings**). Keep this account for site administration only. Do not use it day to day.
2. Create your own user: type `New User` in the search bar. Under **Roles & Permissions**, give the user the `Church Manager` Role Profile and the `Church` Module Profile. This user can manage all aspects of the church.
3. For other staff and volunteers, create users with the Role Profile that matches their job, and the `Church` Module Profile:

   | Role Profile | For | Can change |
   |---|---|---|
   | `Church Staff` | Staff who look things up | Their own prayer requests, sign-ups, care requests and room bookings. Reads people, events, groups and ministries. |
   | `Church Office` | Office administrators | People, families, groups and member transfers |
   | `Church Care Team` | Pastors, deacons, care team | Care, counseling, visitation, background checks, prayer and alms requests |
   | `Church Treasurer` | Treasurer, bookkeeper | Collections, expenses, funds, budgets and giving statements |
   | `Church Check-In Volunteer` | Check-in desk | The Check-In Station only |

   Combine profiles when one person has several jobs. Open the `Role Permissions Manager` to see exactly what each role can do.
4. Members do not need a desk login. Use **Invite to Portal** on their Person. It gives them the `Church User` role, which reaches the portal and their own records only.

### Setting up a public domain

A domain lets people open your site at an address like `www.mychurch.org`. The goal is the same on every deployment path:

1. **Get a domain name.** Register one with a domain registrar, or use a subdomain you already own (for example `churchit.mychurch.org`).
2. **Point the domain at your site.** Follow the part below that matches how you run Churchit.
3. **Check HTTPS.** Open `https://` plus your domain from a phone that is not on your home or office Wi-Fi. The page should load with a padlock.

**Frappe Cloud.** At your domain provider, add a DNS record. For a subdomain, add a `CNAME` record pointing to your Frappe Cloud site name (for example `mychurch.frappe.cloud`). For a bare domain like `mychurch.org`, add a single `A` record pointing to the **Inbound IP** shown on your Frappe site's page. Then open your site's **Domains** tab, click **Add Domain**, enter the domain, click **Verify DNS**, and click **Add Domain** again. Frappe Cloud sets up the HTTPS certificate for you. See [Frappe's custom domain guide](https://docs.frappe.io/cloud/sites/custom-domains) for details.

**Self-hosted (Docker or Pilot).** Your server has to be reachable from the internet, and the exact setup depends on your network.

- **Tunnel (recommended).** A service such as Cloudflare Tunnel or Tailscale Funnel connects out from your server, so you open no ports and change nothing on your router. It also works if your internet provider does not give you a public IP (CGNAT). The tunnel handles DNS and HTTPS. Install the tunnel on the server and point it at Churchit's local address.
- **Reverse proxy or port forwarding.** With port forwarding, add an `A` record to your domain pointing to your public IP address, and forward TCP ports 80 and 443 from your router to the server. If your public IP changes, use a dynamic DNS service to keep the record current. If you already run a [reverse proxy](https://en.wikipedia.org/wiki/Reverse_proxy) such as Nginx, Caddy, or Traefik, point your domain at the proxy and have the proxy forward traffic to Churchit. Pass the original `Host` header through, so Frappe can tell which site the request is for. Learn more about [port forwarding](https://en.wikipedia.org/wiki/Port_forwarding).

For Docker with port forwarding, enter your domain when the setup script asks, and Churchit gets a free HTTPS certificate automatically once DNS and ports are right. The [self-hosting guide](deploy/README.md#making-churchit-reachable-from-the-internet) has the full steps. For Pilot, create the site with your domain as its name, as in the example above, and see Pilot's README for HTTPS.

Putting a site on the internet has security risks. Use a strong `Administrator` password, keep the server up to date, and take regular backups.

### Customising the website pages

The public pages (Home, Beliefs, Sermons, Missions, Ministries) are `Web Page` records, created once when the app is installed. They belong to your church: edit them freely, and upgrades will not overwrite them.

- Open **Website → Web Page** and pick a page. The content is in **Main Section (HTML)**. Content Type is `HTML` with **Dynamic Template** checked, so the HTML is a Jinja template that can read published records, e.g. `{% set sermons = frappe.get_all("Sermon", filters={"publish": 1}) %}` or `{% set church = get_church() %}`. The page then updates itself as you publish records.
- For a page you would rather write by hand, switch Content Type to `Rich Text` or `Markdown` and use the editor instead.
- Per-page styles go in the **Custom CSS** tab (tick *Insert Style*). The site-wide look is the Website Theme, chosen in Website Settings.
- To get a shipped page back to its original look, copy the template from [`churchit/patches/after_install/templates/`](churchit/patches/after_install/templates/) into **Main Section (HTML)**. Those files are also a good starting point for a new page.
- Menu entries live in **Website Settings → Top Bar**; removing one offers to un-publish the page it pointed at.

## 🗺️ Feature Roadmap

Hopefully this roadmap will help avoid too much scope creep and provide a sense of where this project is headed. The items below are listed in order of current priority.

- AI features, such as building a smart list from a sentence
- Reading STOP and START replies to text messages
- Read-only access for AI assistants (MCP)

# 🆘 Support
If you need help setting up the app or configuring it, you can reach out in our [Discord server](https://discord.gg/YxpdU6qM5w) or [Matrix Chat](https://matrix.to/#/#the-church-app:matrix.org).


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

See `AGENTS.md` for the cross-cutting rules that are easy to miss, especially church scoping.

## Steps for adding a new doctype:
  - Add a doctype description on the settings tab
  - Add fields for the doctype (if necessary add field descriptions).
  - Add permissions to the doctype for `Church Manager` and for the desk role that owns its area, and read for `Church Staff` if staff look it up. Give `Church User` only `if_owner` rights, for records a member makes on the portal. See "Roles" in `AGENTS.md`. (Not necessary for child tables)
  - If the records belong to one church, add a `church` Link to `Church` (`hidden: 1`, `in_standard_filter: 0`; `fetch_from` the parent link with `read_only: 1` when the record hangs off another church-scoped record). `Church Features` reveals it in multi-church mode and `churchit.church_scope.ensure_church` fills it. Reports over the doctype must go through `churchit.church_scope` and spread `church.report_filters()` into their filters.
  - Read church-scoped records with `frappe.get_list`, which applies the reader's church for you. `frappe.qb`, `frappe.get_all` and `frappe.db.count` carry no permission filter, so scope those yourself with `churchit.church_scope` (`scoped()` for query builder, `church_query_filters()` for the reader's churches, `church_filters()` for one known church). `tests/test_church_scope_hygiene.py` fails on an unscoped one until it is scoped or the function holding it carries a `# church-scope:` comment with the reason it is safe. See "Reading data" in `AGENTS.md`.
  - Add the doctype to the relevant workspace and to its module's sidebar in `churchit/<module>/sidebar/`. (not necessary for child tables)
  - Document the doctype in the module's `Manual: <Module>` workspace. The manuals are the in-app documentation, so update them whenever user-facing behavior changes. Bump the workspace JSON's `modified` timestamp or `bench migrate` skips it.
  - Set the doctype's `Documentation Link` (Settings tab) to that manual, e.g. `/app/manual%3A-people`. The form's help icon opens it, and `churchit/tests/test_doctype_documentation.py` fails if it is missing.
  - Add an onboarding step and form tour if the doctype needs setting up or has fields that need
    explaining, and list the step in the module's `Module Onboarding`. `AGENTS.md` covers the four
    ways this fails without an error; `churchit/tests/test_onboarding_hygiene.py` enforces them.
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

The Property Setters that reveal the `church` field once multi-church is enabled are deliberately not fixtures: `Church Features` creates and removes them on the site, so a single-church site never carries them.

To add a new fixture, add an entry to the `fixtures` list in `hooks.py` and run:
```bash
bench export-fixtures --app churchit
```

### After-install data: user-owned starter data (applied once, on new installs only)

We use `patches/after_install/` for shipping default documents. Users can modify or delete them freely and they will not be recreated on migration or upgrade. Examples: default funds, event types, Bible translations, web pages, etc.

This data is loaded by the `after_install` hook (`churchit.patches.after_install.execute`) which runs only when the app is first installed on a new site. Existing sites are not affected.

#### Process for adding new starter data

Starter data is hand-written directly in `patches/after_install/__init__.py`. There is no Desk-export step or generated data files.

1. Write a `_create_*()` (or `_setup_*()`) function that inserts the record(s), guarded so it's safe to run more than once. Use the `_insert_if_missing()` helper for simple lookups:
   ```python
   def _create_my_lookup():
       for value in ("Foo", "Bar"):
           _insert_if_missing("My Doctype", {"some_field": value}, some_field=value)
   ```
   For anything more involved, check `frappe.db.exists(...)` yourself before inserting; see the other `_create_*`/`_setup_*` functions in the file for examples.
2. Call the function from `execute()`, ordered after anything it depends on (e.g. a parent document before its children).

Demo/sample content (fake people, families, funds, etc. used to try out the app) is a separate concern. It lives in `churchit/setup/sample_data.py` and runs from the `setup_wizard_complete` hook, not `after_install`.

#### Pushing new starter data to existing sites

The `after_install` hook does not run on existing installations. If we need to push new records to **all** sites (new and existing), write a versioned patch instead, the same mechanism as [Removing data from existing sites](#removing-data-from-existing-sites) below, just inserting instead of deleting:

```
churchit/patches/v2_0/add_livestream_attendance_type.py
```

```python
import frappe


def execute():
    if not frappe.db.exists("Function Attendance Type", "Livestream"):
        frappe.get_doc({"doctype": "Function Attendance Type", "type": "Livestream"}).insert()
```

Then append to `patches.txt` (always append, never insert above existing entries):

```
churchit.patches.v2_0.add_livestream_attendance_type
```

#### Removing data from existing sites

Removal always requires a hand-written patch. There is no automated utility script for this. Be cautious: check whether the record still exists and whether other records might be linking to it before deleting.

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

Then append to `patches.txt` (always append, never insert above existing entries):

```
churchit.patches.v2_0.remove_old_attendance_type
```

## Updating the website screenshots

The [screenshots page](https://churchit.app/screenshots.html) shows real pictures of the app. `docs/screenshots.py` takes the pictures, and `docs/build_docs.py` builds the page from the same list of shots (`SHOTS`). Take new pictures when a page in them changes.

1. Use a site that has only the sample data. The script logs in as two sample users: `mary.johnson@example.com` for the desk and `james.wilson@example.com` for the portal. Each password is the email address.
2. From this app directory, install the browser once, then take the pictures:

   ```bash
   uvx --from playwright==1.63.0 playwright install chromium
   uv run docs/screenshots.py                     # every shot
   uv run docs/screenshots.py rolodex check-in    # only these shots
   ```

   The script uses `http://churchit.localhost:8000`. Add `--url` to use a different site.
3. Look at each new image in `docs/assets/screenshots/` before you commit it. Take it again if it shows test records.
4. If you added, removed or renamed a shot, run `../../env/bin/python docs/build_docs.py`. The `build-docs` workflow also does this after a push.

To add a feature to the page, add a `Shot` to `SHOTS` and take its pictures. A shot can have a desktop picture, a phone picture, or both.


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