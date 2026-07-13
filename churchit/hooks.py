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

fixtures = [
	{"dt": "Custom DocPerm", "filters": [["Role", "like", "Church%"]]},
	{
		"dt": "Property Setter",
		"filters": [["doc_type", "in", ["About Us Settings", "Help Article", "Help Category", "Newsletter"]]],
	},
	{"dt": "Role", "filters": [["Name", "like", "Church%"]]},
	{"dt": "Role Profile", "filters": [["Name", "like", "Church%"]]},
	# These attendance types are fixtures since they are referenced in code (attendance total calculation, sign-up, and check-in).
	{
		"dt": "Function Attendance Type",
		"filters": [["type", "in", ["Confirmed", "Assumed", "Signed-Up", "Checked-In"]]],
	},
	{"dt": "Notification", "filters": [["module", "like", "Church%"]]},
	{
		"dt": "Email Template",
		"filters": [
			[
				"name",
				"in",
				["Donation Acknowledgment", "Birthday Greeting", "New Member Welcome", "Visitor Follow-Up"],
			]
		],
	},
	{"dt": "Letter Head", "filters": [["name", "=", "Church Letter Head"]]},
]
# Apps
# ------------------

required_apps = ["payments"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "churchit",
# 		"logo": "/assets/churchit/logo.png",
# 		"title": "Churchit",
# 		"route": "/churchit",
# 		"has_permission": "churchit.api.permission.has_app_permission",
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/churchit/css/church.css"
app_include_js = [
	"/assets/churchit/js/help_icon_on_form.js",
	"/assets/churchit/js/church_utils.js",
	"/assets/churchit/js/published_fields_indicator.js",
]

# include js, css files in header of web template
# Skins the public website (Web Pages, portal pages) in the same glassy style
# as the marketing site in docs/.
web_include_css = ["/assets/churchit/css/website.css"]
web_include_js = ["/assets/churchit/js/portal_groups.js"]

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "church/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
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
	# Newsletters are member-only — managed via the portal (/newsletter-subscription)
	# and delivered by email. Keep the public Frappe newsletter web view off the site.
	{"source": r"/newsletters.*", "target": "/home"},
]

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

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "churchit.utils.jinja_methods",
# 	"filters": "churchit.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "churchit.patches.after_install.execute"
after_sync = "churchit.patches.after_install.after_sync"

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

# before_app_install = "churchit.utils.before_app_install"
# after_app_install = "churchit.utils.after_app_install"

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

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"churchit.church_ministries.doctype.function.function.create_scheduled_functions",
		"churchit.church_communications.newsletter.sync_member_email_group",
		"churchit.church_missions.doctype.missionary.missionary.create_missionary_expenses",
	],
}


# Testing
# -------

# before_tests = "churchit.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "churchit.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {"User": "churchit.church_people.doctype.person.person.get_user_dashboard_data"}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

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

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

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
