app_name = "churchit"
app_title = "Churchit"
app_publisher = "meichthys"
app_description = "A church management app."
app_email = "church@meichthys.com"
app_license = "mit"
app_logo_url = "/assets/churchit/media/church_logo.png"
develop_version = "develop"

website_context = {
	"favicon": "/assets/churchit/icons/favicon.ico",
	"splash_image": "/assets/churchit/media/church_logo.png",
}

update_website_context = "churchit.church_website.context.update_website_context"
before_request = ["churchit.church_website.context.before_request"]

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", ["Communication", "Contact Us Settings", "Portal Settings"]]],
	},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"doc_type",
				"in",
				[
					"About Us Settings",
					"Contact Us Settings",
					"Website Settings",
				],
			]
		],
	},
	{"dt": "Role", "filters": [["Name", "like", "Church%"]]},
	{"dt": "Role Profile", "filters": [["Name", "like", "Church%"]]},
	# These attendance types are fixtures since they are referenced in code (attendance total calculation, sign-up, check-in, and the portal Attendance page).
	{
		"dt": "Function Attendance Type",
		"filters": [["type", "in", ["Confirmed", "Assumed", "Signed-Up", "Checked-In", "Absent"]]],
	},
	{"dt": "Notification", "filters": [["module", "like", "Church%"]]},
	# The map block on the Missions workspace and the preview on Web Site.
	# App-owned: the workspace JSON references each by name and is re-synced on
	# every migrate, so they have to be re-applied alongside it.
	{"dt": "Custom HTML Block", "filters": [["name", "in", ["MissionaryMap", "WebsitePreview"]]]},
]
# Apps
# ------------------

required_apps = ["payments"]

# The Churchit tile on the Apps screen, which opens on Summary.
add_to_apps_screen = [
	{
		"name": "churchit",
		"logo": app_logo_url,
		"title": app_title,
		"route": "/desk/summary",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = ["/assets/churchit/css/desk.css"]
app_include_js = [
	"/assets/churchit/js/help_icon_on_form.js",
	"/assets/churchit/js/church_utils.js",
	"/assets/churchit/js/published_fields_indicator.js",
	"/assets/churchit/js/contact_tables.js",
	"/assets/churchit/js/name_tags.js",
	"/assets/churchit/js/bible_reference.js",
	"/assets/churchit/js/questions.js",
	"/assets/churchit/js/merge_choices.js",
]

# include js, css files in header of web template
# Page layout shared by every website theme. The Churchit theme's own look is
# public/scss/website.scss, which frappe compiles into each Website Theme.
web_include_css = ["/assets/churchit/css/website.css"]
web_include_js = [
	"/assets/churchit/js/site_church.js",
	"/assets/churchit/js/portal_groups.js",
	"/assets/churchit/js/missions_map.js",
	"/assets/churchit/js/nav_active_state.js",
	"/assets/churchit/js/pwa.js",
	"/assets/churchit/js/questions.js",
]

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	# Filters the payments app's unfiltered "Gateway Settings" doctype picker.
	"Payment Gateway": "public/js/payment_gateway.js",
	# Offers to un-publish the Web Page behind a removed navbar/footer link.
	"Website Settings": "public/js/website_settings.js",
	# A QR code of a web form's address, to print on a bulletin or a welcome card.
	"Web Form": "public/js/web_form_qr.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
app_include_icons = ["/assets/churchit/icons/church.svg"]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

website_redirects = [
	{"source": "/index", "target": "/home"},
	# Newsletters are member-only, managed via the portal (/preferences)
	# and delivered by email. Keep the public Frappe newsletter web view off the site.
	{"source": r"/newsletters.*", "target": "/home"},
	# The preferences page replaced the newsletter subscription page.
	{"source": "/newsletter-subscription", "target": "/preferences"},
]

# One page per published sermon. A sermon name can hold a slash.
website_route_rules = [{"from_route": "/sermon/<path:name>", "to_route": "sermon"}]

# Shipped pages a church switched off answer 404 before Frappe's own renderers or its page
# cache run, and members-only Web Pages send guests to the login page.
page_renderer = [
	"churchit.church_website.pages.SwitchedOffPage",
	"churchit.church_website.pages.MembersOnlyPage",
]

# A members-only Web Page stays out of guest search, and a switched-off web form takes no submission.
extend_doctype_class = {
	"Web Page": ["churchit.church_website.pages.MembersOnlyWebPage"],
	"Web Form": ["churchit.church_website.pages.SwitchedOffWebForm"],
}

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

jinja = {
	"methods": [
		"churchit.church_communications.consent.consent_renewal_link",
		"churchit.church_finances.doctype.giving_statement.giving_statement.statement_header",
		"churchit.church_foundations.doctype.church.church.church_name",
		"churchit.church_foundations.doctype.church.church.get_church",
		"churchit.church_foundations.doctype.church.church.get_letterhead_church",
		"churchit.church_people.household.salutation",
		"churchit.church_scope.church_filters",
		"churchit.church_scope.selected_church_filters",
		"churchit.church_website.pages.get_switched_off_pages",
		"churchit.scripture.get_passage_text",
		"churchit.www.podcast.get_feed_url",
		# The Member QR Card print format draws its code with Frappe's own QR function.
		"frappe.utils.print_format_generator.get_qr_code",
	]
}

# Installation
# ------------

# Frappe keeps one doctype per name, so refuse a site where another app shares one of ours.
before_install = "churchit.church_setup.app_clashes.refuse_clashing_installed_apps"
after_install = "churchit.patches.after_install.execute"

# Workspaces ship as standard records, so migrate re-imports them and resets the
# visibility Church Features set. Re-apply it, and add newly shipped dock entries.
after_migrate = ["churchit.church_setup.doctype.church_features.church_features.apply_on_migrate"]

# Frappe collects the login notes on `on_login`, which runs before the session
# is the user's, so it stores them for Guest and the desk shows none. Collect
# them again once the session belongs to the user. A Website User's first login
# also links the account to their Person.
on_session_creation = [
	"frappe.desk.doctype.note.note._get_unseen_notes",
	"churchit.church_people.accounts.link_portal_user",
]

setup_wizard_requires = "/assets/churchit/js/setup_wizard.js"

setup_wizard_complete = [
	"churchit.setup.sample_data.setup_wizard_complete",
]

# Uninstallation
# ------------

# before_uninstall = "churchit.uninstall.before_uninstall"
# after_uninstall = "churchit.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

before_app_install = "churchit.church_setup.app_clashes.refuse_clashing_app"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "churchit.utils.before_app_uninstall"
# after_app_uninstall = "churchit.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "churchit.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# DocType Class
# ---------------
# Override standard doctype classes

# Role-based notification recipients stay inside the document's church.
override_doctype_class = {
	"Notification": "churchit.church_communications.scoped_notification.ScopedNotification",
}

# Document Events
# ---------------
# Hook on document methods and events

has_permission = {
	"Person": [
		"churchit.church_scope.refuse_changing_another_churches_people",
		"churchit.church_people.member_access.refuse_other_people_to_members",
	],
	"Family": [
		"churchit.church_scope.refuse_changing_another_churches_people",
		"churchit.church_people.member_access.refuse_other_families_to_members",
	],
	"Person Note": "churchit.church_people.notes.has_note_permission",
	"Prayer Request": "churchit.church_prayers.prayer_access.has_prayer_permission",
	"Follow-up Card": "churchit.church_people.followup.has_card_permission",
	"Group File": "churchit.church_people.member_access.has_group_file_permission",
	"Push Subscription": "churchit.church_communications.push.has_subscription_permission",
}

# A portal member lists only their own Person, a Note Category limits who reads its
# notes, the follow-up role lists only the cards assigned to it, and a portal member
# lists only the files of their own groups, and a user lists only their own push
# subscriptions. Church scoping never uses this.
permission_query_conditions = {
	"Person": "churchit.church_people.member_access.person_query_conditions",
	"Family": "churchit.church_people.member_access.family_query_conditions",
	"Prayer Request": "churchit.church_prayers.prayer_access.prayer_query_conditions",
	"Person Note": "churchit.church_people.notes.note_query_conditions",
	"Follow-up Card": "churchit.church_people.followup.card_query_conditions",
	"Group File": "churchit.church_people.member_access.group_file_query_conditions",
	"Push Subscription": "churchit.church_communications.push.subscription_query_conditions",
}

# A person's notes show on their timeline, to the users who may read them.
additional_timeline_content = {"Person": ["churchit.church_people.notes.get_timeline_notes"]}

# Follow-up workflows that start when a person's membership changes or a life event is added.
churchit_people_events = {
	"membership_changed": ["churchit.church_people.followup.on_membership_changed"],
	"life_event_added": ["churchit.church_people.followup.on_life_event_added"],
}

# Every doctype with a `church` Link gets it defaulted (or refused) on save, and
# only a user who can see a record's stored church saves, cancels or updates it, a
# new login is scoped to the church it was created in rather than seeing them all,
# a desk user opens Summary after login, publishing, un-publishing or deleting
# a Web Page adds it to or removes it from the menu, a saved or deleted record
# queues a refresh of the person summary fields it changes, a deleted person
# takes their Possible Duplicate pairs along, an approved data deletion request
# anonymizes the member's Person, a church's record is never shared (or assigned,
# which shares it) with a user outside that church, and a bounce report that reaches
# the inbox marks the address it names.
doc_events = {
	"*": {
		"validate": "churchit.church_scope.ensure_church",
		"before_cancel": "churchit.church_scope.refuse_changing_another_churches_record",
		"before_update_after_submit": "churchit.church_scope.refuse_changing_another_churches_record",
		"on_update": "churchit.church_people.summaries.on_change",
		"on_cancel": "churchit.church_people.summaries.on_change",
		"on_trash": [
			"churchit.church_scope.refuse_deleting_another_churches_record",
			"churchit.church_people.summaries.on_change",
		],
	},
	"Address": {
		"on_update": "churchit.church_people.geocoding.queue_geocode",
	},
	"Communication": {
		"after_insert": "churchit.church_communications.bounces.record_bounce",
	},
	"DocShare": {
		"validate": "churchit.church_foundations.church_access.refuse_sharing_outside_the_church",
	},
	"Email Unsubscribe": {
		"after_insert": "churchit.church_communications.consent.record_unsubscribe",
	},
	"File": {
		"before_insert": "churchit.church_people.member_access.make_group_files_private",
	},
	"Function Check-In": {
		"after_insert": "churchit.church_people.followup.on_check_in",
	},
	"Function Sign-Up": {
		"on_update": "churchit.church_people.followup.on_sign_up",
	},
	"Group": {
		"on_trash": "churchit.church_study.doctype.bible_memory_item.bible_memory_item.clear_group",
	},
	"Person": {
		"on_trash": "churchit.church_people.duplicates.drop_pairs",
	},
	"ToDo": {
		"after_insert": "churchit.church_operations.doctype.church_task.church_task.on_assignment",
		"validate": "churchit.church_operations.doctype.church_task.church_task.refuse_moved_assignment",
	},
	"Web Form Request": {
		"validate": "churchit.church_people.details_link.close_details_request",
	},
	"Personal Data Deletion Request": {
		"on_change": "churchit.church_people.privacy.anonymize_on_data_deletion",
	},
	"User": {
		"validate": "churchit.church_summary.home.land_on_summary",
		"after_insert": "churchit.church_foundations.church_access.scope_new_user",
		"on_update": "churchit.church_communications.push.delete_user_subscriptions",
		"on_trash": "churchit.church_communications.push.delete_user_subscriptions",
	},
	"Web Page": {
		"on_update": "churchit.church_website.menu.sync_web_page",
		"on_trash": "churchit.church_website.menu.remove_from_menu",
	},
}

# Desk: whether multi-church is on and whether the user may include branches.
extend_bootinfo = [
	"churchit.church_scope.extend_bootinfo",
	"churchit.scripture.extend_bootinfo",
	"churchit.church_communications.staff_chat.extend_bootinfo",
]

# User menu switch for parent-church users; hidden for everyone else. One
# item per state, since a Navbar Item's label is fixed.
standard_navbar_items = [
	{
		"item_label": "Include Branch Churches",
		"item_type": "Action",
		"action": "church.toggle_branch_churches()",
		"condition": "frappe.boot.churchit && frappe.boot.churchit.include_branches === false",
		"is_standard": 1,
	},
	{
		"item_label": "Hide Branch Churches",
		"item_type": "Action",
		"action": "church.toggle_branch_churches()",
		"condition": "frappe.boot.churchit && frappe.boot.churchit.include_branches === true",
		"is_standard": 1,
	},
]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"churchit.church_ministries.recurrence.create_scheduled_functions",
		"churchit.church_ministries.attendance.refresh_started_totals",
		"churchit.church_finances.doctype.online_donation.online_donation.alert_unrecorded_gifts",
		"churchit.church_missions.doctype.missionary.missionary.create_missionary_expenses",
		"churchit.church_people.doctype.background_check.background_check.expire_background_checks",
		"churchit.church_people.derived.refresh_daily",
		"churchit.church_people.summaries.refresh_daily",
		"churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment.send_team_emails",
		"churchit.church_people.followup.wake_snoozed_cards",
		"churchit.church_people.followup.start_smart_list_cards",
		"churchit.church_people.privacy.remove_due_personal_data",
		"churchit.church_people.group_meetings.send_attendance_reminders",
		"churchit.church_ministries.doctype.function_sign_up.function_sign_up.send_reminders",
		"churchit.church_summary.metrics.record_recent_weeks",
	],
	"weekly_long": ["churchit.church_people.duplicates.scan"],
	"cron": {
		"*/5 * * * *": [
			"churchit.church_communications.doctype.church_email.church_email.send_scheduled",
			"churchit.church_ministries.doctype.function_sign_up.function_sign_up.release_expired_holds",
		],
	},
}


# Testing
# -------

# before_tests = "churchit.install.before_tests"

# Overriding Methods
# ------------------------------

# Connection counts on a form cover only the records the reader may see, and Data Import's
# Export Data writes an Access Log entry like Frappe's other exports.
override_whitelisted_methods = {
	# The payments app replaces Frappe's web form save with an older copy that ignores Web Form
	# Request keys, skips the form's own checks and inserts whatever doctype the browser names.
	# The last installed app wins, so this puts Frappe's own back. No Churchit web form takes payment.
	# Remove it once frappe/payments#276 is fixed; the steps are in #272.
	"frappe.website.doctype.web_form.web_form.accept": "frappe.website.doctype.web_form.web_form.accept",
	"frappe.desk.notifications.get_open_count": "churchit.connections.get_open_count",
	"frappe.core.doctype.data_import.data_import.download_template": "churchit.exports.download_template",
	# Frappe's portal list API lists every published Web Page to any signed-in user; this one leaves
	# out members-only pages for a non-member.
	"frappe.www.list.get_list_data": "churchit.church_website.pages.get_list_data",
}

# A Person Link field also finds people by phone number or email address.
standard_queries = {"Person": "churchit.church_people.search.search_people"}

# Data Import targets that read another system's people export, or Churchit's own spreadsheet,
# and build Address, Family and Person records from each row.
data_import_providers = {
	"People Import": "churchit.church_people.imports.people.PeopleImportProvider",
	"Planning Center Import": "churchit.church_people.imports.planning_center.PlanningCenterImportProvider",
	"Rock RMS Import": "churchit.church_people.imports.rock_rms.RockRMSImportProvider",
	"Breeze Import": "churchit.church_people.imports.breeze.BreezeImportProvider",
	"Giving Import": "churchit.church_finances.imports.giving.GivingImportProvider",
}

# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {"User": "churchit.church_people.doctype.person.person.get_user_dashboard_data"}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

ignore_links_on_delete = ["Person Group", "Person Ministry Team", "Person Team Position"]

# Request Events
# ----------------
# before_request = ["churchit.utils.before_request"]
# after_request = ["churchit.utils.after_request"]

# Job Events
# ----------
# before_job = ["churchit.utils.before_job"]
# after_job = ["churchit.utils.after_job"]

# User Data Protection
# --------------------

# A member's data download includes their Person. Their email rows are left out: Frappe matches a row by the
# address alone, so it would download, and a deletion would redact, a spouse's or a family's row of a shared
# address. A deletion request anonymizes the whole Person through doc_events instead.
user_data_fields = [
	{"doctype": "Person", "filter_by": "user"},
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"churchit.auth.validate"
# ]


# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
