"""
after_install patch — runs once when the Church app is installed on a new site.

Creates all default reference data, configuration, and website content so the
app is usable out of the box.  Existing sites are not affected (this hook only
fires on ``bench install-app churchit``).
"""

from pathlib import Path

import frappe

# We define this here so we can import it from sample_data
DEFAULT_CHURCH_NAME = "My Church"


def execute():
	# Default church — must exist before lookup types that reference it.
	_create_default_church()

	# Simple lookup types (no inter-dependencies)
	_create_contact_types()
	_create_member_statuses()
	_create_function_types()
	_create_function_attendance_types()
	_create_position_types()
	_create_payment_types()
	_create_person_relation_types()
	_create_prayer_request_statuses()
	_create_prayer_request_types()
	_create_missionary_support_frequencies()
	_create_group_roles()
	_create_group_statuses()
	_create_default_ministry()

	# Bible reference data
	_create_bible_books()
	_create_bible_translations()

	# Module access control
	_create_module_profile()

	# Dashboard charts
	_create_dashboard_charts()

	# Custom HTML blocks
	_create_custom_html_blocks()

	# Website content
	_create_web_pages()
	_setup_about_us_settings()
	_setup_contact_us_settings()
	_setup_website_settings()
	_setup_portal_settings()

	# Visit Type lookups (referenced by Visitation Log)
	_create_default_visit_types()

	# Life Event Type lookups (referenced by Life Event)
	_create_default_life_event_types()

	# Counseling Case Type lookups (referenced by Counseling Case)
	_create_default_case_types()

	# Care Request Type lookups (referenced by Care Request)
	_create_default_care_request_types()

	# Cleanup
	_clean_gender_options()
	_hide_default_workspaces()

	# Newsletter recipients — Email Group seeded from Person emails
	_create_member_email_group()


def after_sync():
	"""Runs after frappe's ``after_app_install`` hook, which auto-generates the
	"Tools" desktop icon from the Tools workspace. That icon does not exist yet
	when ``execute()`` (``after_install``) runs, so reordering has to happen
	here instead — otherwise Tools keeps its default idx of 0 and lands first.
	"""
	_reorder_default_desktop_icons()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_if_missing(doctype, filters, **fields):
	"""Insert a record only if one matching *filters* does not already exist."""
	if not frappe.db.exists(doctype, filters):
		frappe.get_doc({"doctype": doctype, **fields}).insert(ignore_permissions=True)


_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _read_template(filename):
	"""Read an HTML template from the templates/ subdirectory next to this file.

	Called only from this module with hardcoded ``template_file`` literals
	(home.html, beliefs.html, etc.); no caller passes user input.
	"""
	return (_TEMPLATES_DIR / filename).read_text()


# ---------------------------------------------------------------------------
# Default Church
# ---------------------------------------------------------------------------


def _create_default_church():
	"""Create a default Church so the app has a church record at install time.

	The user is expected to rename this church via the onboarding wizard.
	If a church already exists (e.g. on a dev site being re-run), do nothing.
	"""
	if frappe.db.exists("Church", {"parent_church": ("is", "not set")}):
		return

	frappe.get_doc(
		{
			"doctype": "Church",
			"church_name": DEFAULT_CHURCH_NAME,
			"abbreviation": "MC",
			"legal_name": "My Church",
			"founding_date": "1990-03-15",
			"publish": 1,
			"mission_statement": "To glorify God by making disciples, and serving our neighbors with the love of Christ.",
			"about": "<p>Welcome to My Church. We are a community of believers committed to worship, fellowship, and service. We are a congregation rooted in Scripture and passionate about sharing the grace of God with all people.</p><p>Founded in 1990, we have grown from a small gathering into a vibrant church family. Whether you are a lifelong believer or simply curious about faith, you are welcome here.</p>",
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Simple lookup types
# ---------------------------------------------------------------------------


def _create_member_statuses():
	for status in ("Active", "Inactive"):
		_insert_if_missing("Member Status", {"status": status}, status=status)


def _create_function_types():
	for function_type in (
		"Sunday Morning Service",
		"Sunday Evening Service",
		"Prayer Meeting",
		"Business Meeting",
		"Communion",
		"Baptism",
	):
		_insert_if_missing("Function Type", {"type": function_type}, type=function_type)


def _create_function_attendance_types():
	types = {
		"Unknown": "Attendance was not tracked for this function.",
		"Absent": "The person was not present at this function.",
		"Assumed": "The person was assumed to be present at this function (e.g. their family was present).",
		"Confirmed": "The person's attendance was confirmed at this function.",
		"Signed-Up": "The person (or someone on their behalf) signed up for this function.",
		"Checked-In": "The person was checked in at this function.",
	}
	for name, description in types.items():
		_insert_if_missing(
			"Function Attendance Type",
			{"type": name},
			type=name,
			description=description,
		)


def _create_position_types():
	for position in ("Pastor", "Elder", "Deacon", "Secretary", "Treasurer"):
		_insert_if_missing("Position Type", {"position": position}, position=position)


def _create_payment_types():
	for payment_type in ("Cash", "Check", "Online"):
		_insert_if_missing("Payment Type", {"type": payment_type}, type=payment_type)


def _create_person_relation_types():
	for relation in (
		"Uncle",
		"Aunt",
		"Brother",
		"Sister",
		"Husband",
		"Wife",
		"Father",
		"Mother",
		"Son",
		"Daughter",
		"Grandson",
		"Granddaughter",
		"Grandfather",
		"Grandmother",
		"Nephew",
		"Niece",
		"Brother-in-law",
		"Sister-in-law",
		"Father-in-law",
		"Mother-in-law",
		"Stepfather",
		"Stepmother",
		"Stepbrother",
		"Stepsister",
	):
		_insert_if_missing("Person Relation Type", {"type": relation}, type=relation)


def _create_prayer_request_statuses():
	statuses = {
		"Requested": "This prayer request has been submitted and is awaiting prayer.",
		"Being Prayed For": "This prayer request is currently being prayed for.",
		"Answered": "This prayer has been answered.",
	}
	for name, description in statuses.items():
		_insert_if_missing(
			"Prayer Request Status",
			{"status": name},
			status=name,
			description=description,
		)


def _create_prayer_request_types():
	types = {
		"Praise": "A prayer of praise and thanksgiving to God.",
		"Health": "A prayer request related to health or healing.",
		"Salvation": "A prayer request for the salvation of a person.",
		"Unspoken": "A prayer request that the person does not wish to share details about.",
	}
	for name, description in types.items():
		_insert_if_missing(
			"Prayer Request Type",
			{"type": name},
			type=name,
			description=description,
		)


def _create_missionary_support_frequencies():
	frequencies = {
		"Weekly": "Support is sent once per week.",
		"Bi-Weekly": "Support is sent every two weeks.",
		"Monthly": "Support is sent once per month.",
		"Bi-Monthly": "Support is sent every two months.",
		"Quarterly": "Support is sent four times per year.",
		"Yearly": "Support is sent once per year.",
	}
	for name, description in frequencies.items():
		_insert_if_missing(
			"Missionary Support Frequency",
			{"frequency": name},
			frequency=name,
			description=description,
		)


def _create_group_roles():
	for role in ("Leader", "Member"):
		_insert_if_missing("Group Role", {"role": role}, role=role)


def _create_group_statuses():
	for status in ("Active", "Inactive"):
		_insert_if_missing("Group Status", {"status": status}, status=status)


def _create_default_ministry():
	_insert_if_missing(
		"Ministry",
		{"ministry_name": "General"},
		ministry_name="General",
		status="Active",
		mission_statement="The default ministry for general church functions.",
	)


# ---------------------------------------------------------------------------
# Bible reference data
# ---------------------------------------------------------------------------


def _create_bible_books():
	"""Insert all 66 canonical Bible books with their standard abbreviations.

	The record ``name`` is the full book name (e.g. "Genesis") and
	``abbreviation`` is the short code used by bible-api.com (e.g. "GEN").
	"""
	books = [
		# Old Testament
		("Genesis", "GEN"),
		("Exodus", "EXO"),
		("Leviticus", "LEV"),
		("Numbers", "NUM"),
		("Deuteronomy", "DEU"),
		("Joshua", "JOS"),
		("Judges", "JDG"),
		("Ruth", "RUT"),
		("1 Samuel", "1SA"),
		("2 Samuel", "2SA"),
		("1 Kings", "1KI"),
		("2 Kings", "2KI"),
		("1 Chronicles", "1CH"),
		("2 Chronicles", "2CH"),
		("Ezra", "EZR"),
		("Nehemiah", "NEH"),
		("Esther", "EST"),
		("Job", "JOB"),
		("Psalms", "PSA"),
		("Proverbs", "PRO"),
		("Ecclesiastes", "ECC"),
		("Song of Solomon", "SNG"),
		("Isaiah", "ISA"),
		("Jeremiah", "JER"),
		("Lamentations", "LAM"),
		("Ezekiel", "EZK"),
		("Daniel", "DAN"),
		("Hosea", "HOS"),
		("Joel", "JOL"),
		("Amos", "AMO"),
		("Obadiah", "OBA"),
		("Jonah", "JON"),
		("Micah", "MIC"),
		("Nahum", "NAM"),
		("Habakkuk", "HAB"),
		("Zephaniah", "ZEP"),
		("Haggai", "HAG"),
		("Zechariah", "ZEC"),
		("Malachi", "MAL"),
		# New Testament
		("Matthew", "MAT"),
		("Mark", "MRK"),
		("Luke", "LUK"),
		("John", "JHN"),
		("Acts", "ACT"),
		("Romans", "ROM"),
		("1 Corinthians", "1CO"),
		("2 Corinthians", "2CO"),
		("Galatians", "GAL"),
		("Ephesians", "EPH"),
		("Philippians", "PHP"),
		("Colossians", "COL"),
		("1 Thessalonians", "1TH"),
		("2 Thessalonians", "2TH"),
		("1 Timothy", "1TI"),
		("2 Timothy", "2TI"),
		("Titus", "TIT"),
		("Philemon", "PHM"),
		("Hebrews", "HEB"),
		("James", "JAS"),
		("1 Peter", "1PE"),
		("2 Peter", "2PE"),
		("1 John", "1JN"),
		("2 John", "2JN"),
		("3 John", "3JN"),
		("Jude", "JUD"),
		("Revelation", "REV"),
	]
	for book_name, abbreviation in books:
		_insert_if_missing(
			"Bible Book",
			{"book": book_name},
			book=book_name,
			abbreviation=abbreviation,
		)


def _create_bible_translations():
	"""Insert common English Bible translations used by bible-api.com."""
	translations = [
		("King James Version", "KJV"),
		("New International Version", "NIV"),
		("English Standard Version", "ESV"),
		("New Living Translation", "NLT"),
		("Christian Standard Bible", "CSB"),
		("New King James Version", "NKJV"),
		("New American Standard Bible", "NASB"),
		("New American Bible Revised Edition", "NABRE"),
		("The Message", "MSG"),
		("Amplified Bible", "AMP"),
		("New Revised Standard Version", "NRSV"),
		("American Standard Version", "ASV"),
		("Douay-Rheims Bible", "DRB"),
		("Revised Standard Version", "RSV"),
		("Jerusalem Bible", "JB"),
		("New Jerusalem Bible", "NJB"),
		("Common English Bible", "CEB"),
		("Good News Translation", "GNT"),
		("Contemporary English Version", "CEV"),
		("New English Translation", "NET"),
		("New International Reader's Version", "NIrV"),
		("Complete Jewish Bible", "CJB"),
		("The Passion Translation", "TPT"),
		("The Living Bible", "LIVING"),
		("Modern English Version", "MEV"),
		("New Century Version", "NCV"),
		("The Voice", "VOICE"),
		("World English Bible", "WEB"),
		("Berean Standard Bible", "BSB"),
		("Bible in Basic English", "BBE"),
	]
	for translation_name, abbreviation in translations:
		_insert_if_missing(
			"Bible Translation",
			{"translation": translation_name},
			translation=translation_name,
			abbreviation=abbreviation,
		)


# ---------------------------------------------------------------------------
# Module Profile — controls which Frappe modules Church users can see
# ---------------------------------------------------------------------------


def _create_module_profile():
	"""Create the 'Church' Module Profile, blocking all non-church modules.

	Users assigned this profile will only see Church app modules in the desk,
	hiding unrelated ERPNext/Frappe modules that would otherwise be confusing.
	"""
	if frappe.db.exists("Module Profile", "Church"):
		return

	blocked_modules = [
		"Manufacturing",
		"Quality Management",
		"Selling",
		"EDI",
		"Stock",
		"Accounts",
		"Assets",
		"Automation",
		"Bulk Transaction",
		"Buying",
		"Contacts",
		"CRM",
		"Custom",
		"Email",
		"ERPNext Integrations",
		"Integrations",
		"Maintenance",
		"Geo",
		"Projects",
		"Regional",
		"Setup",
		"Social",
		"Subcontracting",
		"Support",
		"Telephony",
		"Utilities",
		"Workflow",
		"Communication",
		"Printing",
		"Portal",
		"Desk",
		"Core",
	]
	frappe.get_doc(
		{
			"doctype": "Module Profile",
			"module_profile_name": "Church",
			"block_modules": [{"module": m} for m in blocked_modules],
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Dashboard Charts
# ---------------------------------------------------------------------------


def _create_dashboard_charts():
	"""Create People and Members line charts shown on the Church workspace."""
	if not frappe.db.exists("Dashboard Chart", "People"):
		frappe.get_doc(
			{
				"doctype": "Dashboard Chart",
				"chart_name": "People",
				"module": "Church People",
				"document_type": "Person",
				"based_on": "creation",
				"type": "Line",
				"time_interval": "Weekly",
				"timespan": "Last Year",
				"timeseries": 1,
				"is_standard": 0,
				"show_values_over_chart": 1,
				"filters_json": "[]",
				"dynamic_filters_json": "[]",
			}
		).insert(ignore_permissions=True)

	if not frappe.db.exists("Dashboard Chart", "Members"):
		frappe.get_doc(
			{
				"doctype": "Dashboard Chart",
				"chart_name": "Members",
				"module": "Church People",
				"document_type": "Life Event",
				"parent_document_type": "Person",
				"based_on": "date",
				"type": "Line",
				"time_interval": "Monthly",
				"timespan": "Last Year",
				"timeseries": 1,
				"is_standard": 0,
				"show_values_over_chart": 1,
				"filters_json": '[["Life Event","event_type","=","Membership",false]]',
				"dynamic_filters_json": "[]",
			}
		).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Custom HTML Blocks
# ---------------------------------------------------------------------------


def _create_custom_html_blocks():
	"""Create a cover photo block shown on the Church workspace."""
	if frappe.db.exists("Custom HTML Block", "Church Cover Photo"):
		return

	frappe.get_doc(
		{
			"doctype": "Custom HTML Block",
			"name": "Church Cover Photo",
			"html": (
				'<div style="text-align: center;">\n'
				'  <img src="/assets/churchit/media/church_photo.jpg"'
				' alt="Church Photo" style="max-width: 100%; border-radius: 8px;">\n'
				"</div>\n"
			),
			"private": 0,
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Web Pages — dynamic Jinja templates stored in templates/*.html
# ---------------------------------------------------------------------------


def _create_web_pages():
	"""Create the four default church website pages.

	HTML content is stored in separate template files under templates/ so it
	can be edited without touching this Python script.
	"""
	pages = [
		{
			"name": "home",
			"title": "Home",
			"route": "home",
			"template_file": "home.html",
		},
		{
			"name": "beliefs",
			"title": "Beliefs",
			"route": "beliefs",
			"template_file": "beliefs.html",
		},
		{
			"name": "missions",
			"title": "Missions",
			"route": "missions",
			"template_file": "missions.html",
		},
		{
			"name": "sermons",
			"title": "Sermons",
			"route": "sermons",
			"template_file": "sermons.html",
		},
		{
			"name": "ministries",
			"title": "Ministries",
			"route": "ministries",
			"template_file": "ministries.html",
		},
		{
			"name": "locations",
			"title": "Locations",
			"route": "locations",
			"template_file": "locations.html",
		},
	]
	for page in pages:
		if frappe.db.exists("Web Page", page["name"]):
			continue
		frappe.get_doc(
			{
				"doctype": "Web Page",
				"name": page["name"],
				"title": page["title"],
				"route": page["route"],
				"published": 1,
				"dynamic_template": 1,
				"content_type": "HTML",
				"module": "Church Website",
				"full_width": 0,
				"show_title": 1,
				"text_align": "Center",
				"css": ".page-header { text-align: center; }",
				"main_section_html": _read_template(page["template_file"]),
			}
		).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Single DocType setup
# Only set the specific fields we own; leave all other fields untouched so
# we do not overwrite anything the user may have configured.
# ---------------------------------------------------------------------------


def _setup_about_us_settings():
	"""Populate the About Us page with default church-oriented content."""
	doc = frappe.get_doc("About Us Settings")
	# frappe ships the /about page disabled; the navbar links to it, so enable it
	doc.is_disabled = 0
	doc.page_title = "About Our Church"
	doc.company_introduction = (
		"<p>We are a congregation of believers committed to worshipping God, growing"
		" in His Word, and serving one another and our community in love.</p>"
		'<p>To learn more about what we believe, visit our <a href="/beliefs">Beliefs</a>'
		" page. To see how we support missionaries around the world, visit our"
		' <a href="/missions">Missions</a> page.</p>'
	)
	doc.company_history_heading = "Church History"
	doc.team_members_heading = "Our Team"
	doc.save(ignore_permissions=True)


def _setup_contact_us_settings():
	"""Enable and populate the Contact Us page (shipped disabled by frappe)."""
	doc = frappe.get_doc("Contact Us Settings")
	# frappe ships the /contact page disabled; the navbar links to it, so enable it
	doc.is_disabled = 0
	doc.heading = "Get in Touch"
	doc.introduction = (
		"<p>We would love to hear from you. Send us a message and someone from"
		" our church will get back to you soon.</p>"
	)
	doc.query_options = "General\nPrayer Request\nPlanning a Visit\nGiving"
	doc.save(ignore_permissions=True)


def _setup_website_settings():
	"""Configure default website settings for a church site.

	Sets the app name, login visibility, home page, theme, and navigation bar.
	Only the fields listed here are written; any other Website Settings fields
	that the user has configured are left untouched.
	"""
	doc = frappe.get_doc("Website Settings")
	doc.app_name = "Church"
	doc.disable_signup = 1
	doc.hide_footer_signup = 1
	doc.hide_login = 0
	doc.navbar_search = 0
	doc.home_page = "home"
	doc.website_theme = "Standard"
	doc.top_bar_items = []
	for item in [
		{"label": "Home", "url": "/home", "right": 1},
		{"label": "Beliefs", "url": "/beliefs", "right": 1},
		{"label": "Sermons", "url": "/sermons", "right": 1},
		{"label": "Missions", "url": "/missions", "right": 1},
		{"label": "Ministries", "url": "/ministries", "right": 1},
		{"label": "Locations", "url": "/locations", "right": 1},
		{"label": "About Us", "url": "/about", "right": 1},
		{"label": "Contact Us", "url": "/contact", "right": 1},
		{"label": "Give", "url": "/give", "right": 1},
	]:
		doc.append("top_bar_items", item)
	doc.footer_powered = " "
	doc.footer_items = []
	for item in [
		{"label": "Submit a Prayer Request", "url": "/prayer-request-anonymous"},
		{"label": "My Account", "url": "/me", "right": 1},
	]:
		doc.append("footer_items", item)
	doc.save(ignore_permissions=True)


def _setup_portal_settings():
	"""Seed the member portal menu (Portal Settings) with Church defaults.

	Seeds frappe's standard menu table — the one get_portal_roles() reads, so
	the "Church User" role on the items is what makes members portal users and
	shows the Portal link on /me. Runs once at install; from then on the menu
	belongs to the site admin (Desk > Portal Settings). reference_doctype must
	resolve to a real DocType even for route-only items, or Portal Settings
	prunes the row on the next migrate.
	"""
	items = [
		("Function Sign-Ups", "function-sign-up", "Function Sign-Up", "Church User"),
		("Bible Memory", "memorize", "Bible Memory Item", "Church User"),
		("Prayer Requests", "prayer-request", "Prayer Request", "Church User"),
		("Community Prayer Requests", "community-prayer-requests", "Prayer Request", "Church User"),
		("Alms Requests", "alms-request", "Alms Request", "Church User"),
		("Groups", "groups", "Group", "Church User"),
		("Newsletter Subscription", "newsletter-subscription", "Email Group Member", "Church User"),
		# no role: visible to any logged-in user
		("Help Articles", "Help Article", "Help Article", None),
	]
	doc = frappe.get_doc("Portal Settings")
	doc.default_portal_home = "/me"
	titles = {title for title, _route, _ref, _role in items}
	doc.custom_menu = [row for row in doc.custom_menu if row.title not in titles]
	for title, route, ref, role in items:
		doc.add_item({"title": title, "route": route, "reference_doctype": ref, "role": role})
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Workspace visibility
# ---------------------------------------------------------------------------


def _hide_default_workspaces():
	"""Hide built-in Frappe workspaces that are irrelevant to church users.

	The is_hidden field is preserved through bench migrate / Frappe updates, so
	this only needs to run once at install time.
	"""
	for workspace in ("Tools", "Build", "Users", "Integrations", "Website"):
		if frappe.db.exists("Workspace", workspace):
			frappe.db.set_value("Workspace", workspace, "is_hidden", 1)


# ---------------------------------------------------------------------------
# Gender cleanup
# ---------------------------------------------------------------------------


def _clean_gender_options():
	"""Remove non-biblical genders from Frappe's default gender list.

	Keeps only Male, Female, and Unknown.
	"""
	for gender in frappe.db.get_all("Gender"):
		if gender.name not in ("Male", "Female", "Unknown"):
			frappe.delete_doc("Gender", gender.name, force=True)


def _create_default_visit_types():
	"""Seed the standard Visit Type lookup values.

	These were previously hardcoded as a Select on Visitation Log; promoted
	to a Link doctype so churches can add their own types.
	"""
	if not frappe.db.exists("DocType", "Visit Type"):
		return
	for visit_type in (
		"First Time Guest",
		"Hospital",
		"Homebound",
		"Bereavement",
		"Inactive Member",
		"New Member",
		"Evangelistic",
		"Other",
	):
		_insert_if_missing("Visit Type", {"type": visit_type}, type=visit_type)


def _create_default_case_types():
	"""Seed the standard Case Type lookup values.

	Previously hardcoded as a Select on Counseling Case; promoted to a Link
	doctype so churches can add their own.
	"""
	if not frappe.db.exists("DocType", "Case Type"):
		return
	for case_type in ("Marriage", "Premarital", "Grief", "Financial", "Spiritual", "Family", "Other"):
		_insert_if_missing("Case Type", {"type": case_type}, type=case_type)


def _create_default_care_request_types():
	"""Seed the standard Care Request Type lookup values.

	Previously hardcoded as a Select on Care Request; promoted to a Link
	doctype so churches can add their own.
	"""
	if not frappe.db.exists("DocType", "Care Request Type"):
		return
	for care_type in (
		"General Need",
		"Meal Help",
		"Hospital",
		"Grief",
		"Financial",
		"Spiritual",
		"Counseling",
		"Other",
	):
		_insert_if_missing("Care Request Type", {"type": care_type}, type=care_type)


def _create_default_budgets():
	"""Seed a zero-amount Budget for every existing Fund for the current year."""
	if not frappe.db.exists("DocType", "Budget"):
		return
	year = frappe.utils.now_datetime().year
	for fund in frappe.db.get_all("Fund", fields=["name"]):
		_insert_if_missing(
			"Budget",
			{"fund": fund.name, "fiscal_year": year},
			fund=fund.name,
			fiscal_year=year,
			budgeted_amount=0,
			period="Annual",
			is_active=1,
		)


def _create_member_email_group():
	"""Create the church newsletter Email Group and seed it from Person emails.

	The list is kept current automatically by the daily
	``churchit.church_communications.newsletter.sync_member_email_group`` job, so
	the recipient list is never maintained by hand.
	"""
	from churchit.church_communications.newsletter import (
		MEMBER_EMAIL_GROUP,
		sync_member_email_group,
	)

	if not frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
		frappe.get_doc({"doctype": "Email Group", "title": MEMBER_EMAIL_GROUP}).insert(
			ignore_permissions=True
		)
	sync_member_email_group()


def _create_contact_types():
	"""Seed the Email Type / Phone Type / Address Type lookups used by the
	emails, phones and addresses tables on Person, Family and Missionary."""
	from churchit.contacts import create_default_contact_types

	create_default_contact_types()


def _create_default_life_event_types():
	"""Seed the standard Life Event Type lookup values."""
	if not frappe.db.exists("DocType", "Life Event Type"):
		return
	for event_type in (
		"Birth",
		"Death",
		"Baptism",
		"Membership",
		"Wedding",
		"Anniversary",
		"Confirmation",
		"Graduation",
		"Dedication",
		"Conversion",
	):
		_insert_if_missing("Life Event Type", {"type": event_type}, type=event_type)


def _reorder_default_desktop_icons():
	"""Push frappe's default desktop icons (Framework, Tools, ...) behind the
	church icons on the desk grid, ending with Settings, Tools, then Framework.

	Icons sort by idx; churchit ships its icons with idx 1-12 (Welcome first),
	but frappe's icons default to idx 0 and would land in front. frappe installs
	(and creates its icons) before churchit, so they all exist by the time this
	patch runs. Tools has no app set (it's auto-generated from the workspace,
	not a fixture), so app must be checked in Python — an "app != churchit"
	filter in SQL silently drops NULL rows instead of matching them.
	"""
	pinned_last = ["Settings", "Tools", "Framework"]

	icons = frappe.get_all(
		"Desktop Icon",
		filters={"parent_icon": ("is", "not set"), "idx": ("<", 90)},
		fields=["name", "app"],
		order_by="label asc",
	)
	pos = 90
	for icon in icons:
		if icon.app == "churchit" or icon.name in pinned_last:
			continue
		frappe.db.set_value("Desktop Icon", icon.name, "idx", pos, update_modified=False)
		pos += 1

	for name in pinned_last:
		if frappe.db.exists("Desktop Icon", name):
			frappe.db.set_value("Desktop Icon", name, "idx", pos, update_modified=False)
			pos += 1
