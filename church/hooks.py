app_name = "church"
app_title = "Church"
app_publisher = "meichthys"
app_description = "A church management app."
app_email = "church@meichthys.com"
app_license = "mit"
app_logo_url = "/assets/church/media/church_logo.png"
develop_version = "develop"

website_context = {
	"favicon": "/assets/church/icons/favicon.ico",
	"splash_image": "/assets/church/media/church_logo.png",
}

fixtures = [
	{"dt": "Property Setter", "filters": [["doc_type", "=", "About Us Settings"]]},
	{"dt": "Role", "filters": [["Name", "like", "Church%"]]},
	{"dt": "Role Profile", "filters": [["Name", "like", "Church%"]]},
	# "Assumed" attendance type is a fixture since it is used in the Function Sign Up doctype's after_insert method.
	{"dt": "Function Attendance Type", "filters": [["name", "=", "Assumed"]]},
]
# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "church",
# 		"logo": "/assets/church/logo.png",
# 		"title": "Church",
# 		"route": "/church",
# 		"has_permission": "church.api.permission.has_app_permission",
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/church/css/church.css"
app_include_js = [
	"/assets/church/js/help_icon_on_form.js",
	"/assets/church/js/church_utils.js",
	"/assets/church/js/published_fields_indicator.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/church/css/church.css"
# web_include_js = "/assets/church/js/church.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "church/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"User": "public/js/user.js"}
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
app_include_icons = ["church/icons/church.svg"]

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

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
# 	"methods": "church.utils.jinja_methods",
# 	"filters": "church.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "install.before_install"
after_install = "church.patches.after_install.execute"

setup_wizard_requires = "/assets/church/js/setup_wizard.js"

setup_wizard_complete = [
	"church.setup.sample_data.setup_wizard_complete",
]

# Uninstallation
# ------------

# before_uninstall = "church.uninstall.before_uninstall"
# after_uninstall = "church.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "church.utils.before_app_install"
# after_app_install = "church.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "church.utils.before_app_uninstall"
# after_app_uninstall = "church.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "church.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Person": "church.church_people.doctype.person.person.get_permission_query_conditions",
}

has_permission = {
	"Person": "church.church_people.doctype.person.person.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"User": {
		"after_insert": "church.church_customizations.user_permissions.sync_user_permission",
		"on_update": "church.church_customizations.user_permissions.sync_user_permission",
		"validate": "church.church_customizations.user_permissions.validate_church_manager_edits",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"church.tasks.all"
# 	],
# 	"daily": [
# 		"church.tasks.daily"
# 	],
# 	"hourly": [
# 		"church.tasks.hourly"
# 	],
# 	"weekly": [
# 		"church.tasks.weekly"
# 	],
# 	"monthly": [
# 		"church.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "church.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "church.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "church.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["church.utils.before_request"]
# after_request = ["church.utils.after_request"]

# Job Events
# ----------
# before_job = ["church.utils.before_job"]
# after_job = ["church.utils.after_job"]

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
# 	"church.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
