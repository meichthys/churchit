# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Whitelisted functions and Document methods that change data refuse GET, and none takes every verb."""

import ast
import os

from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_doc_method_hygiene import (
	APP_DIR,
	Function,
	app_index,
	is_whitelisted,
	keyword,
	last_name,
)

VERBS = {"GET", "POST", "PUT", "DELETE"}

PUBLIC_BIBLE_TEXT = (
	"a public guest API for Bible text; its only write is the first-read download of a Free Use "
	"Bible API text, which any guest starts with GET or POST and no CSRF token, so a GET from another "
	"site adds nothing"
)

# Whitelisted callables that change data and take GET on purpose, and why another site gains nothing
# by starting one.
GET_BY_DESIGN = {
	"churchit.church_communications.consent.renew_consent": (
		"the signed link of the Consent Renewal email, which a mail client opens with GET; the "
		"signature is the check, not the session"
	),
	"churchit.church_communications.newsletter.unsubscribe": (
		"the signed link at the foot of every Church Email, which a mail client opens with GET; the "
		"signature is the check, not the session"
	),
	"churchit.church_people.ai.get_group_briefing": (
		"an AI app reads a briefing with GET, so MCP runs it with read permission; it writes only the "
		"Access Log entry of the read"
	),
	"churchit.church_people.ai.get_person_briefing": (
		"an AI app reads a briefing with GET, so MCP runs it with read permission; it writes only the "
		"Access Log entry of the read"
	),
	"churchit.church_people.report.church_directory_report.church_directory_report.download_directory_pdf": (
		"Print Directory opens it in a new tab with GET; it writes only the Access Log entry of the "
		"download and, for the church verse, the Bible text download of get_books, and the PDF goes "
		"to the browser that asked"
	),
	"churchit.exports.download_template": (
		"stands in for Frappe's own Data Import export, which takes GET; it writes only the Access Log "
		"entry of the download, and the file goes to the browser that asked"
	),
	"churchit.scripture.get_books": PUBLIC_BIBLE_TEXT,
	"churchit.scripture.get_chapter": PUBLIC_BIBLE_TEXT,
	"churchit.scripture.get_passage": PUBLIC_BIBLE_TEXT,
}

# Functions that take all four verbs on purpose. A read takes GET, so an AI app can tell it from a
# write and MCP runs it with read permission and a rollback.
ALL_VERBS = {
	"churchit.exports.download_template": (
		"replaces Frappe's own method of that name (override_whitelisted_methods), which takes every "
		"verb, so a caller of Frappe's method keeps working"
	),
	"churchit.church_communications.doctype.church_email.church_email.ChurchEmail.get_recipient_count": (
		"Document method that frm.call runs with POST and the form's unsaved copy; it only counts"
	),
	"churchit.church_communications.doctype.church_email.church_email.ChurchEmail.get_preview": (
		"Document method that frm.call runs with POST and the form's unsaved copy; it only renders"
	),
	"churchit.church_finances.doctype.church_budget.church_budget.ChurchBudget.get_progress": (
		"Document method that frm.call runs with POST and the form's unsaved copy; it only totals"
	),
	"churchit.church_finances.doctype.church_budget.church_budget.ChurchBudget.add_all_expense_types": (
		"Document method that frm.call runs with POST and the form's unsaved copy; it adds rows to "
		"that copy and stores nothing"
	),
}

NUMBER_CARD = "Frappe's number card widget calls it with frappe.xcall, which posts"
CHART_SOURCE = "Frappe's dashboard chart widget calls it with frappe.xcall, which posts"
DASHBOARD_COUNT = "a number card method that Frappe's number card widget calls with frappe.xcall, which posts"

# Reads that take GET and POST because a script that Frappe owns posts, so churchit cannot drop POST.
# A read with a caller under public/js takes POST too, for one release (see the next test).
CORE_SCRIPT_POSTS = {
	"churchit.church_website.pages.get_list_data": (
		"overrides frappe.www.list.get_list_data, which Frappe's web form list script calls with POST"
	),
	"churchit.dashboard.count_families": DASHBOARD_COUNT,
	"churchit.dashboard.count_people": DASHBOARD_COUNT,
	"churchit.dashboard.count_weekly_attendance": DASHBOARD_COUNT,
	"churchit.church_finances.dashboard_chart_source.finance_summary.finance_summary.get": CHART_SOURCE,
	"churchit.church_finances.dashboard_chart_source.fund_goal_progress.fund_goal_progress.get": CHART_SOURCE,
	"churchit.church_finances.dashboard_chart_source.giving_by_fund.giving_by_fund.get": CHART_SOURCE,
	"churchit.church_people.dashboard_chart_source.life_events.life_events.get": CHART_SOURCE,
	"churchit.church_people.dashboard_chart_source.people_added.people_added.get": CHART_SOURCE,
}
for _card in (
	"church_people.number_card.anniversaries_this_week.anniversaries_this_week.get_count",
	"church_people.number_card.birthdays_this_week.birthdays_this_week.get_count",
	"church_people.number_card.first_time_visitors.first_time_visitors.get_count",
	"church_people.number_card.inactivity_candidates.inactivity_candidates.get_count",
	"church_people.number_card.new_members_30_days.new_members_30_days.get_count",
	"church_prayers.number_card.active_prayer_requests.active_prayer_requests.get_value",
	"church_prayers.number_card.prayer_request_comments.prayer_request_comments.get_count",
	"church_setup.number_card.total_answered_prayers_this_month.total_answered_prayers_this_month.get_value",
	"church_setup.number_card.total_collection_this_month.total_collection_this_month.get_value",
	"church_setup.number_card.total_expenses_this_month.total_expenses_this_month.get_value",
):
	CORE_SCRIPT_POSTS[f"churchit.{_card}"] = NUMBER_CARD

LONG_LIST = "a list view posts the names of every selected record, which can pass a URL's length limit"

# Reads that take GET and POST because their desk caller sends a list too long for a URL. An AI app
# reads them with GET.
LONG_LIST_POSTS = {
	"churchit.contacts.get_emails_for": LONG_LIST,
	"churchit.church_people.list_actions.get_household_adult_emails": LONG_LIST,
	"churchit.church_people.list_actions.get_household_emails": LONG_LIST,
	"churchit.church_people.list_actions.get_people_emails": LONG_LIST,
}

PUBLIC_SCRIPTS = os.path.join(APP_DIR, "public", "js")


def accepted_verbs(function: Function) -> set[str]:
	"""The verbs the function's whitelist takes: all four when it names no methods."""
	for decorator in function.node.decorator_list:
		if isinstance(decorator, ast.Call) and last_name(decorator.func) == "whitelist":
			methods = ast.literal_eval(keyword(decorator, "methods") or ast.Constant(None))
			return set(methods) if methods else set(VERBS)
	return set()


def takes_get(function: Function) -> bool:
	return "GET" in accepted_verbs(function)


def public_script_text() -> str:
	"""The text of every script under public/js, which browsers keep for up to 12 hours."""
	texts = []
	for root, _dirs, files in os.walk(PUBLIC_SCRIPTS):
		for name in files:
			if name.endswith(".js"):
				with open(os.path.join(root, name)) as script:
					texts.append(script.read())
	return "\n".join(texts)


class TestWhitelistedCallablesRefuseGet(FrappeTestCase):
	"""A whitelisted function or Document method that changes data takes `methods=["POST"]`.

	Frappe checks the CSRF token only on POST, PUT and DELETE (`frappe/auth.py`), and the session
	cookie travels with a link or a redirect that another site starts. Frappe rolls the database
	back at the end of a GET, but not a commit the code makes, a queued job, a cache entry or a sent
	message, and a write that a GET quietly loses is a bug of its own. `@frappe.whitelist()` takes
	every method unless `methods` names them, and `run_doc_method` applies a Document method's own
	list.

	A change is what test_doc_method_hygiene.py finds as a write, the `save`, `insert` and `delete`
	that Frappe checks itself included: a user's right to write does not make the request theirs.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.index = app_index()
		cls.taking_get = {
			f"{function.module.name}.{function.name}": function
			for function in cls.index.functions()
			if is_whitelisted(function.node) and takes_get(function)
		}

	def test_a_callable_that_changes_data_refuses_get(self):
		changing = sorted(
			f"{function.location} {name}"
			for name, function in self.taking_get.items()
			if name not in GET_BY_DESIGN and self.index.summary(function).writes
		)
		assert not changing, (
			"These whitelisted callables change data and take GET, so another site can start them as "
			'the signed-in user. Add methods=["POST"] to the whitelist (frappe.call, frappe.xcall and '
			"frm.call send POST), or add them to GET_BY_DESIGN with the reason: " + ", ".join(changing)
		)

	def test_every_get_by_design_entry_still_changes_data_on_get(self):
		stale = [
			name
			for name in GET_BY_DESIGN
			if name not in self.taking_get or not self.index.summary(self.taking_get[name]).writes
		]
		self.assertEqual(
			stale, [], "GET_BY_DESIGN lists callables that are gone, refuse GET or write nothing"
		)


class TestWhitelistedFunctionsTakeTheVerbsTheyNeed(FrappeTestCase):
	"""A read takes GET, so an AI app tells it from a write, and MCP runs it with read permission.

	A function that names no `methods` takes GET, POST, PUT and DELETE. A read that a script under
	public/js calls also takes POST for one release, because a browser keeps the old script for up
	to 12 hours and it still posts; once no such script calls it, it takes GET only.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.verbs = {
			f"{function.module.name}.{function.name}": accepted_verbs(function)
			for function in app_index().functions()
			if is_whitelisted(function.node)
		}

	def test_a_function_that_takes_every_verb_is_listed_with_a_reason(self):
		unlisted = sorted(
			name for name, verbs in self.verbs.items() if verbs >= VERBS and name not in ALL_VERBS
		)
		assert not unlisted, (
			'These whitelisted functions take every verb. Name the verbs with methods=["GET"] for a '
			'read and methods=["POST"] for a write, or add them to ALL_VERBS with the reason: '
			+ ", ".join(unlisted)
		)

	def test_a_function_that_takes_get_and_post_has_a_reason(self):
		scripts = public_script_text()
		unexplained = sorted(
			name
			for name, verbs in self.verbs.items()
			if {"GET", "POST"} <= verbs < VERBS
			and name not in CORE_SCRIPT_POSTS
			and name not in LONG_LIST_POSTS
			and name not in scripts
		)
		assert not unexplained, (
			"These whitelisted functions take GET and POST, and no script under public/js calls them. "
			'Make them methods=["GET"] and send GET from every caller, or add them to '
			"CORE_SCRIPT_POSTS when a script of Frappe's own posts, or to LONG_LIST_POSTS when the "
			"caller sends a list too long for a URL: " + ", ".join(unexplained)
		)

	def test_every_listed_verb_exception_still_applies(self):
		stale = [name for name in ALL_VERBS if not self.verbs.get(name, set()) >= VERBS]
		stale += [
			name
			for name in (*CORE_SCRIPT_POSTS, *LONG_LIST_POSTS)
			if not {"GET", "POST"} <= self.verbs.get(name, set())
		]
		self.assertEqual(
			stale,
			[],
			"ALL_VERBS, CORE_SCRIPT_POSTS or LONG_LIST_POSTS lists functions that are gone or take fewer verbs",
		)
