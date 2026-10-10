# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A Note set to show on login reaches the user who logs in.

Frappe collects it on `on_login`, before the session is the user's, so on its own it stores
the notes for Guest. Logging in through `LoginManager` checks the `on_session_creation` hook
that collects them again. A login commits, so the test deletes its note itself.
"""

import frappe
from frappe.auth import CookieManager, LoginManager
from frappe.desk.doctype.note.note import get_unseen_notes
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now, set_request

from churchit.tests.helpers import ensure_user

PASSWORD = "Login-Note-Password-1"


class TestLoginNotes(FrappeTestCase):
	def setUp(self):
		self.user = ensure_user("_test_login_note@example.com", "_Test Login", roles=("Church Staff",))
		frappe.utils.password.update_password(self.user, PASSWORD)
		self.note = frappe.get_doc(
			{
				"doctype": "Note",
				"title": "_Test Login Note",
				"public": 1,
				"notify_on_login": 1,
				"notify_on_every_login": 1,
				"expire_notification_on": add_days(now(), 7),
				"content": "<p>Welcome</p>",
			}
		).insert(ignore_permissions=True)
		frappe.cache.delete_keys("unseen_notes::")

	def tearDown(self):
		frappe.form_dict.clear()
		frappe.set_user("Administrator")
		frappe.delete_doc("Note", self.note.name, force=True)
		frappe.db.commit()

	def log_in(self):
		frappe.set_user("Guest")
		set_request(method="POST", path="/api/method/login")
		frappe.form_dict.usr = self.user
		frappe.form_dict.pwd = PASSWORD
		frappe.local.response = frappe._dict()
		frappe.local.request_ip = "127.0.0.71"
		frappe.local.cookie_manager = CookieManager()
		frappe.local.login_manager = LoginManager()

	def test_the_user_who_logs_in_gets_the_note(self):
		self.log_in()
		self.assertEqual(frappe.session.user, self.user)
		self.assertIn(self.note.name, [note.name for note in get_unseen_notes()])
