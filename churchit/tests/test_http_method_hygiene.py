# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Whitelisted functions and Document methods that change data refuse GET."""

import ast

from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_doc_method_hygiene import Function, app_index, is_whitelisted, keyword, last_name

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


def takes_get(function: Function) -> bool:
	"""True when the function's whitelist takes GET, as it does when it names no methods."""
	for decorator in function.node.decorator_list:
		if isinstance(decorator, ast.Call) and last_name(decorator.func) == "whitelist":
			methods = ast.literal_eval(keyword(decorator, "methods") or ast.Constant(None))
			return not methods or "GET" in methods
	return False


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
