# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Server-side hooks behind the portal web forms."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.web_form.web_form import accept

from churchit.church_ministries.web_form.function_sign_up import function_sign_up as sign_up_form
from churchit.church_people.web_form.groups import groups as groups_form
from churchit.church_prayers.web_form.community_prayer_requests import (
	community_prayer_requests as prayer_form,
)
from churchit.tests.helpers import ensure, ensure_user, make_function, make_person


class TestFunctionSignUpWebForm(FrappeTestCase):
	def setUp(self):
		self.user = ensure_user("_test_form_signer@example.com", "_Test Form Signer")
		self.person = make_person("_Test Form", "Signer", user=self.user).name
		self.open_function = make_function("_Test Open Sign-Up", allow_sign_ups=1)
		self.closed_function = make_function("_Test Closed Sign-Up", allow_sign_ups=0)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_user_context_reports_person_and_manager_flag(self):
		self.assertTrue(sign_up_form.get_user_context()["is_manager"])

		frappe.set_user(self.user)
		self.assertEqual(sign_up_form.get_user_context(), {"person": self.person, "is_manager": False})

		frappe.set_user("Guest")
		self.assertIsNone(sign_up_form.get_user_context())

	def test_function_options_are_filtered_to_sign_up_functions(self):
		options = json.dumps(
			[
				{"value": self.open_function.name, "label": "Open"},
				{"value": self.closed_function.name, "label": "Closed"},
			]
		)
		field = frappe._dict(fieldname="function", options=options)
		context = frappe._dict(web_form_doc={"web_form_fields": [field]})
		sign_up_form.get_context(context)

		self.assertEqual([o["value"] for o in json.loads(field.options)], [self.open_function.name])
		self.assertTrue(context.has_sign_up_functions)

	def test_newline_separated_options_are_filtered_too(self):
		field = frappe._dict(
			fieldname="function", options=f"{self.open_function.name}\n{self.closed_function.name}"
		)
		sign_up_form.get_context(frappe._dict(web_form_doc={"web_form_fields": [field]}))
		self.assertEqual(field.options, self.open_function.name)

	def test_reference_doc_titles_are_resolved_separately(self):
		context = frappe._dict(reference_doc={"function": self.open_function.name, "person": self.person})
		sign_up_form.get_context(context)
		self.assertEqual(
			context.link_titles, {"function": self.open_function.title, "person": "_Test Form Signer"}
		)
		# The raw names stay on reference_doc for the client script.
		self.assertEqual(context.reference_doc["function"], self.open_function.name)

	def test_sign_up_items_include_live_totals(self):
		item = ensure("Sign-Up Item", {"item": "_Test Form Dish"})
		self.open_function.append("table_cxhh", {"item": item, "quantity_needed": 3})
		self.open_function.save(ignore_permissions=True)

		self.assertEqual(
			sign_up_form.get_function_sign_up_items(self.open_function.name),
			[{"item": item, "quantity_needed": 3, "quantity_signed_up": 0}],
		)


class TestGroupsWebForm(FrappeTestCase):
	def setUp(self):
		self.user = ensure_user("_test_form_member@example.com", "_Test Form Member")
		self.person = make_person("_Test Form", "Member", user=self.user).name
		self.mine = self._group("_Test My Portal Group", show_in_portal=1, members=[self.person])
		self.hidden = self._group("_Test My Hidden Group", show_in_portal=0, members=[self.person])
		self.theirs = self._group("_Test Their Group", show_in_portal=1)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _group(self, name, members=(), **values):
		group = frappe.get_doc({"doctype": "Group", "group_name": name, **values})
		for person in members:
			group.append("members", {"person": person})
		return group.insert(ignore_permissions=True)

	def _listing(self):
		context = groups_form.get_list_context(frappe._dict())
		return [row.name for row in context.get_list("Group", "", [], 0, 100)]

	def test_listing_shows_only_the_users_portal_groups(self):
		frappe.set_user(self.user)
		names = self._listing()
		self.assertIn(self.mine.name, names)
		self.assertNotIn(self.hidden.name, names)
		self.assertNotIn(self.theirs.name, names)

	def test_listing_is_empty_for_users_without_a_person(self):
		frappe.set_user("Guest")
		self.assertEqual(self._listing(), [])


class TestCommunityPrayerRequestsWebForm(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		cls.public = cls._request("_Test Community Public", request_type, visibility="Whole Church")
		cls.team = cls._request("_Test Community Team", request_type, visibility="Prayer Team")
		cls.private = cls._request("_Test Community Private", request_type, visibility="Private")
		cls.member = ensure_user("_test_community_member@example.com", "_Test Community Member")
		cls.praying = ensure_user(
			"_test_community_team@example.com",
			"_Test Community Team",
			roles=("Church User", "Church Prayer Team"),
		)
		for user in (cls.member, cls.praying):
			if not frappe.db.exists("Person", {"user": user}):
				make_person(user, "_Test Community", user=user)

	@classmethod
	def _request(cls, title, request_type, **values):
		return frappe.get_doc(
			{"doctype": "Prayer Request", "title": title, "type": request_type, **values}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def listed(self, user, filters=None):
		frappe.set_user(user)
		context = prayer_form.get_list_context(frappe._dict(filters={"owner": "Administrator"}))
		self.assertIsNone(context.filters)
		return [row.name for row in context.get_list("Prayer Request", "", filters or [], 0, 500)]

	def test_every_member_sees_whole_church_requests_from_everyone(self):
		names = self.listed(self.member)

		self.assertIn(self.public.name, names)
		self.assertNotIn(self.team.name, names)
		self.assertNotIn(self.private.name, names)

	def test_the_prayer_team_also_sees_prayer_team_requests(self):
		names = self.listed(self.praying)

		self.assertIn(self.public.name, names)
		self.assertIn(self.team.name, names)
		self.assertNotIn(self.private.name, names)

	def test_asking_for_private_requests_yields_nothing(self):
		self.assertEqual(self.listed(self.praying, {"visibility": "Private"}), [])

	def test_the_forms_condition_arrives_as_an_operator_filter(self):
		names = self.listed(self.praying, {"visibility": ["!=", "Private"]})

		self.assertIn(self.public.name, names)
		self.assertIn(self.team.name, names)

	def test_a_member_opens_only_the_requests_the_page_lists_them(self):
		frappe.set_user(self.member)
		self.assertTrue(self.public.has_webform_permission())
		self.assertFalse(self.team.has_webform_permission())

		frappe.set_user(self.praying)
		self.assertTrue(self.team.has_webform_permission())
		self.assertFalse(self.private.has_webform_permission())

		frappe.set_user("Guest")
		self.assertFalse(self.public.has_webform_permission())

	def test_portal_submission_keeps_the_chosen_recipient(self):
		"""The form's script picks a recipient by search; the id only survives
		``accept`` when ``recipient`` is a (hidden) field of the web form."""
		person = make_person("_Test Community", "Recipient")
		data = json.dumps(
			{
				"title": "_Test Community Submitted",
				# The form's defaults; Frappe checks mandatory fields before it fills defaults.
				"status": "Requested",
				"visibility": "Whole Church",
				"type": self.public.type,
				"request": "Please pray.",
				"requestor": person.name,
				"recipient_type": "Person",
				"recipient": person.name,
			}
		)
		saved = accept("prayer-request", data)
		self.assertEqual(saved.recipient, person.name)
		self.assertEqual(saved.recipient_name, "_Test Community Recipient")

	def test_reference_doc_links_are_resolved_to_titles(self):
		person = make_person("_Test Community", "Requestor")
		context = frappe._dict(
			reference_doc=frappe._dict(requestor=person.name, recipient_type="Person", recipient=person.name)
		)
		prayer_form.get_context(context)
		self.assertEqual(context.reference_doc.requestor, "_Test Community Requestor")
