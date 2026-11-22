# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the member app's page gives the browser as it loads: window.csrf_token and window.churchit.

Every value must be plain JSON (no dates or Decimals): the page writes each one with Jinja's tojson.
"""

import frappe
from frappe import _
from frappe.locale import get_date_format, get_first_day_of_the_week, get_time_format
from frappe.translate import get_all_translations
from frappe.utils import get_fullname, strip_html
from frappe.utils.html_utils import sanitize_html
from frappe.utils.jinja_globals import is_rtl

from churchit.church_communications.push import get_public_key
from churchit.church_finances.doctype.giving_settings.giving_settings import get_currency
from churchit.church_ministries.pre_check_in import get_functions
from churchit.church_scope import is_feature_enabled, root_church, session_church, session_person
from churchit.church_website.pages import is_page_off, is_public_website_on
from churchit.portal.accent import get_accent
from churchit.portal.nav import get_menu


def get_boot() -> dict:
	"""The page's boot: the CSRF token frappe-ui sends with each change, and the app's own data."""
	return {"csrf_token": frappe.sessions.get_csrf_token(), "churchit": get_app_boot()}


def get_app_boot() -> dict:
	"""The member, their church, the menu and the settings the app formats with."""
	lang = frappe.local.lang or "en"
	person = session_person()
	menu = get_menu()
	return {
		"site_name": frappe.local.site,
		"socketio_port": get_socketio_port(),
		"realtime": not frappe.conf.disable_async,
		"user": get_user(),
		"person": person,
		"household": get_household_title(person),
		"church": get_church_summary(),
		"lang": lang,
		"rtl": is_rtl(),
		"translations": get_all_translations(lang) if lang != "en" else {},
		"date_format": get_date_format(),
		"time_format": get_time_format(),
		"first_day_of_the_week": get_first_day_of_the_week(),
		"currency": get_currency(),
		"accent": get_accent(),
		"check_in": get_check_in(person, set(menu["hidden_pages"])),
		"push_public_key": get_public_key(),
		"offer_app_install": is_feature_enabled("offer_app_install"),
		"website_home": get_website_home(),
		"intros": get_web_form_intros(),
		**menu,
	}


def get_socketio_port() -> int | None:
	"""The socket.io port on a development server, where it differs from the web port. None in production,
	where the proxy serves /socket.io on the page's own origin."""
	return frappe.conf.socketio_port if frappe._dev_server else None


def get_user() -> dict:
	"""The signed-in user: name, full name, photo, and whether they work in the desk."""
	user = frappe.session.user
	values = frappe.get_cached_value("User", user, ("user_image", "user_type"), as_dict=True) or {}
	return {
		"name": user,
		"full_name": get_fullname(user),
		"image": values.get("user_image"),
		"is_staff": values.get("user_type") == "System User",
	}


def get_church_summary() -> dict | None:
	"""The member's church (the main church for a login with no Person): name, short name and logo."""
	name = session_church() or root_church()
	if not name:
		return None
	church = frappe.get_cached_doc("Church", name)
	return {
		"name": church.name,
		"title": church.church_name,
		"abbreviation": church.abbreviation,
		"logo": church.image,
	}


def get_household_title(person: str | None) -> str | None:
	""" "The Wilson Family" for a member in a Family, as the household page names it."""
	family = person and frappe.db.get_value("Person", person, "family")
	if not family:
		return None
	family_name = frappe.db.get_value("Family", family, "family_name") or ""
	return _("The {0} Family").format(family_name.rpartition(" - ")[0] or family_name)


def get_check_in(person: str | None, hidden: set[str]) -> dict:
	"""Whether the app offers check-in to this member (their church uses self check-in), and whether
	a Function is open for it now. The first is a steady rule, so the app's tabs do not change by the day."""
	enabled = bool(
		person
		and not is_page_off("household", hidden)
		and frappe.db.exists("Function Type", {"allow_self_check_in": 1})
	)
	return {"enabled": enabled, "open": enabled and bool(get_functions())}


# The member web forms the app replaced, by route.
WEB_FORM_PAGES = (
	"function-sign-up",
	"room-request",
	"groups",
	"group-files",
	"personal-details",
	"prayer-request",
	"community-prayer-requests",
	"care-request",
	"alms-request",
	"pledge",
)


def get_web_form_intros() -> dict[str, str]:
	"""Each replaced web form's Introduction, by route: the church's own words above the page, which the
	app shows in the same place (its page component PageIntro)."""
	forms = frappe.get_all(
		"Web Form",
		filters={"published": 1, "route": ("in", WEB_FORM_PAGES)},
		fields=["route", "introduction_text"],
	)
	return {
		form.route: sanitize_html(form.introduction_text)
		for form in forms
		if strip_html(form.introduction_text or "").strip()
	}


def get_website_home() -> str | None:
	"""The church website's home page, while the public website is on. Not "/", which opens the app."""
	if not is_public_website_on():
		return None
	return "/" + (frappe.get_cached_value("Website Settings", None, "home_page") or "home").strip("/")
