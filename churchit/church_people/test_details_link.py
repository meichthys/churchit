# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import timedelta
from unittest import mock

import frappe
from frappe.model import no_value_fields
from frappe.utils import add_days, get_datetime, now_datetime
from frappe.website.doctype.web_form.web_form import accept

from churchit.church_people.details_link import DETAILS_FORM, LINK_DAYS, send_details_link
from churchit.church_people.member_access import personal_details_fields
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

MODULE = "churchit.church_people.details_link"
HOOK = f"{MODULE}.close_details_request"
EMAIL = "_test_details_holder@example.com"


def form_data(person, **changes):
	"""What the browser sends: every field the form shows, as the page loaded it, with *changes*."""
	doc = frappe.get_doc("Person", person)
	fields = [
		field.fieldname
		for field in frappe.get_doc("Web Form", DETAILS_FORM).web_form_fields
		if field.fieldtype not in no_value_fields
	]
	return {"doctype": "Person", "name": person, **{field: doc.get(field) for field in fields}, **changes}


class DetailsLinkTestCase(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.sendmail = self.start(mock.patch("frappe.sendmail"))
		self.start(mock.patch(f"{MODULE}.can_send_email", return_value=True))
		# The rules live in the hook; test_the_hook_is_registered checks that hooks.py names it.
		self.start(mock.patch.dict(frappe.get_doc_hooks(), {"Web Form Request": {"validate": [HOOK]}}))

	def start(self, patcher):
		self.addCleanup(patcher.stop)
		return patcher.start()

	def make_holder(self, **values):
		return make_person(
			"_Test Details",
			"Holder",
			emails=[{"email_address": EMAIL}],
			medical_notes="_Test Private",
			**values,
		)

	def send_link(self, person):
		send_details_link(person)
		return frappe.get_last_doc("Web Form Request", filters={"web_form": DETAILS_FORM})

	def save_as_guest(self, request, data):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict()
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)
		try:
			return accept(DETAILS_FORM, frappe.as_json(data), web_form_request_key=request.key)
		finally:
			frappe.set_user("Administrator")


class TestSendDetailsLink(DetailsLinkTestCase):
	def test_the_link_goes_to_the_persons_primary_email(self):
		person = self.make_holder()

		self.assertEqual(send_details_link(person.name), EMAIL)

		request = frappe.get_last_doc("Web Form Request", filters={"web_form": DETAILS_FORM})
		self.assertEqual(
			[(row.link_doctype, row.link_name) for row in request.references], [("Person", person.name)]
		)
		expected_expiry = add_days(now_datetime(), LINK_DAYS)
		self.assertLess(abs(get_datetime(request.expires_on) - expected_expiry), timedelta(minutes=1))
		sent = self.sendmail.call_args.kwargs
		self.assertEqual(sent["recipients"], [EMAIL])
		self.assertIn(
			f"/{DETAILS_FORM}/{person.name}/edit?web_form_request_key={request.key}", sent["message"]
		)

	def test_only_a_user_who_may_change_the_person_sends_one(self):
		person = self.make_holder()
		reader = ensure_user("_test_details_reader@example.com", "Reader", roles=("Church Staff",))
		frappe.set_user(reader)
		with self.assertRaises(frappe.PermissionError):
			send_details_link(person.name)
		self.assertFalse(frappe.db.exists("Web Form Request", {"web_form": DETAILS_FORM}))

	def test_a_person_with_no_email_or_a_site_with_no_outgoing_email_is_refused(self):
		without_email = make_person("_Test Details", "Unreachable")
		with self.assertRaisesRegex(frappe.ValidationError, "Add an email address"):
			send_details_link(without_email.name)

		person = self.make_holder()
		with mock.patch(f"{MODULE}.can_send_email", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "outgoing Email Account"):
				send_details_link(person.name)
		self.sendmail.assert_not_called()


class TestDetailsLinkChurches(DetailsLinkTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.editor_a = ensure_user(
			"_test_details_editor_a@example.com", "EditorA", roles=("Church People Editor",)
		)
		make_person("_Test Details", "Editor A", church=cls.branch_a, user=cls.editor_a)

	def test_an_editor_sends_no_link_for_another_churchs_person(self):
		theirs = self.make_holder(church=self.branch_b)
		frappe.set_user(self.editor_a)
		with self.assertRaises(frappe.PermissionError):
			send_details_link(theirs.name)


class TestUpdateYourDetails(DetailsLinkTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_the_key_holder_changes_only_the_forms_fields_of_their_person(self):
		person = self.make_holder()
		request = self.send_link(person.name)

		self.save_as_guest(
			request,
			form_data(
				person.name,
				first_name="_Test Renamed",
				medical_notes="_Test Changed",
				membership_status="Inactive",
				user="Administrator",
			),
		)

		saved = frappe.get_doc("Person", person.name)
		self.assertEqual(saved.first_name, "_Test Renamed")
		self.assertEqual(
			(saved.medical_notes, saved.membership_status, saved.user), ("_Test Private", "Active", None)
		)

	def test_the_key_holder_corrects_their_email_phone_and_marital_status(self):
		person = self.make_holder()
		request = self.send_link(person.name)
		data = form_data(person.name, marital_status="Single")
		data["emails"] = [{"email_address": "_test_details_new@example.com", "email_type": "Home"}]
		data["phones"] = [{"phone_number": "555 010 0177", "phone_type": "Mobile"}]

		self.save_as_guest(request, data)

		saved = frappe.get_doc("Person", person.name)
		self.assertEqual([row.email_address for row in saved.emails], ["_test_details_new@example.com"])
		self.assertEqual([row.phone_number for row in saved.phones], ["555 010 0177"])
		self.assertEqual(saved.marital_status, "Single")

	def test_the_link_works_once(self):
		person = self.make_holder()
		request = self.send_link(person.name)
		self.save_as_guest(request, form_data(person.name, first_name="_Test Once"))

		with self.assertRaises(frappe.exceptions.LinkExpired):
			self.save_as_guest(request, form_data(person.name, first_name="_Test Twice"))
		self.assertEqual(frappe.db.get_value("Person", person.name, "first_name"), "_Test Once")

	def test_the_link_expires(self):
		person = self.make_holder()
		request = self.send_link(person.name)
		frappe.db.set_value("Web Form Request", request.name, "expires_on", add_days(now_datetime(), -1))

		with self.assertRaises(frappe.exceptions.LinkExpired):
			self.save_as_guest(request, form_data(person.name, first_name="_Test Late"))

	def test_the_link_opens_no_other_person(self):
		person = self.make_holder()
		other = make_person("_Test Details", "Other")
		request = self.send_link(person.name)

		with self.assertRaises(frappe.PermissionError):
			self.save_as_guest(request, form_data(other.name, first_name="_Test Hijacked"))
		self.assertEqual(frappe.db.get_value("Person", other.name, "first_name"), "_Test Details")

	def test_the_link_adds_no_person(self):
		request = self.send_link(self.make_holder().name)
		before = frappe.db.count("Person")
		frappe.db.savepoint("guest_request")

		with self.assertRaisesRegex(frappe.PermissionError, "only the person it was sent to"):
			self.save_as_guest(request, {"doctype": "Person", "first_name": "_Test Newcomer"})
		# Frappe rolls back a request that fails.
		frappe.db.rollback(save_point="guest_request")
		self.assertEqual(frappe.db.count("Person"), before)

	def test_the_page_sends_only_the_forms_fields(self):
		person = self.make_holder(life_events=[{"event_type": "Birth", "date": "1980-03-03"}])
		request = self.send_link(person.name)
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(name=person.name, is_edit=1, web_form_request_key=request.key)
		frappe.local.path = f"{DETAILS_FORM}/{person.name}/edit"

		context = frappe._dict()
		frappe.get_doc("Web Form", DETAILS_FORM).get_context(context)

		self.assertEqual(context.reference_doc["first_name"], "_Test Details")
		self.assertEqual(str(context.reference_doc["birthday"]), "1980-03-03")
		self.assertEqual([row["email_address"] for row in context.reference_doc["emails"]], [EMAIL])
		self.assertNotIn("medical_notes", context.reference_doc)
		self.assertNotIn("addresses", context.reference_doc)


class TestDetailsForm(DetailsLinkTestCase):
	def test_the_form_needs_a_key_and_offers_only_personal_details_fields(self):
		form = frappe.get_doc("Web Form", DETAILS_FORM)
		self.assertEqual((form.key_required, form.login_required, form.allow_delete), (1, 0, 0))
		offered = {
			field.fieldname for field in form.web_form_fields if field.fieldtype not in no_value_fields
		}
		self.assertTrue(offered)
		self.assertLessEqual(offered, personal_details_fields())

	def test_web_forms_save_through_frappes_own_accept(self):
		"""The payments app's copy of accept ignores the key, so a link holder could not save."""
		accept_method = "frappe.website.doctype.web_form.web_form.accept"
		self.assertEqual(frappe.override_whitelisted_method(accept_method), accept_method)

	def test_the_hook_is_registered(self):
		"""The hook is what keeps a link to one use and one person; without it Frappe allows both."""
		self.assertIn(HOOK, frappe.get_hooks("doc_events").get("Web Form Request", {}).get("validate", []))
