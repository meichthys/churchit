# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.translate import clear_cache as clear_translation_cache
from frappe.utils import fmt_money, formatdate, nowdate
from frappe.utils.pdf import read_options_from_html

from churchit.church_ministries.doctype.function.function import get_schedule_rows
from churchit.church_people.test_household import make_household, set_adult_age
from churchit.patches.v1_0 import retire_church_directory_print_format
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	make_address,
	make_function,
	make_person,
)
from churchit.utils import LONG_DATE_FORMAT


class TestPrintFormats(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_root_church()
		ensure("Life Event Type", {"type": "Baptism"})
		ensure("Life Event Type", {"type": "Membership"})

	def make_person_with_address(self, last_name, **values):
		address = make_address(f"{last_name} Home", address_line1="42 Elm Road")
		person = make_person("Pat", last_name, **values)
		person.append("addresses", {"address": address.name, "is_primary": 1})
		person.save(ignore_permissions=True)
		return person

	def test_letter_of_transfer_makes_no_standing_claim_for_a_visitor(self):
		person = make_person("Vera", "_Test Visitor", membership="Visitor")

		html = frappe.get_print("Person", person.name, "Letter of Transfer")

		self.assertNotIn("good standing", html)
		self.assertIn("is known to our church", html)
		self.assertIn(frappe.db.get_value("Church", ensure_root_church(), "church_name"), html)

	def test_letter_of_transfer_names_the_membership_date_of_an_active_member(self):
		person = make_person("Mel", "_Test Member", membership="Member", membership_status="Active")
		person.append("life_events", {"event_type": "Membership", "date": "2011-03-04"})
		person.save(ignore_permissions=True)

		html = frappe.get_print("Person", person.name, "Letter of Transfer")

		self.assertIn("received into membership of our church on Friday, March 4, 2011", html)
		self.assertIn("active member in good standing", html)

	def test_certificates_print_landscape_with_an_ordinal_day(self):
		person = make_person("Bea", "_Test Baptized")
		person.append("life_events", {"event_type": "Baptism", "date": "2031-04-12"})
		person.append("life_events", {"event_type": "Membership", "date": "2031-04-23"})
		person.save(ignore_permissions=True)

		for name, day in (("Baptism Certificate", "12th"), ("Membership Certificate", "23rd")):
			html = frappe.get_print("Person", person.name, name)
			self.assertEqual(read_options_from_html(html)[1].get("orientation"), "Landscape")
			self.assertIn(f"<strong>{day}</strong>", html)

	def test_badge_and_card_set_their_own_page_size(self):
		person = make_person("Robert", "_Test Badge", nickname="Bobby")

		badge = frappe.get_print("Person", person.name, "Name Badge")
		card = frappe.get_print("Person", person.name, "Member Profile Card")

		self.assertEqual(read_options_from_html(badge)[1].get("page-width"), "4in")
		self.assertEqual(read_options_from_html(card)[1].get("page-height"), "148mm")
		self.assertIn("Bobby", badge)
		self.assertNotIn('class="badge"', badge)

	def test_count_sheet_splits_each_fund_by_payment_type(self):
		fund = ensure("Fund", {"fund": "_Test Count Fund"})
		collection = frappe.get_doc({"doctype": "Collection", "date": nowdate(), "expected_total": 100})
		for payment_type, amount in (("Cash", 30), ("Check", 70)):
			collection.append(
				"donations",
				{
					"payment_type": ensure("Payment Type", {"type": payment_type}),
					"fund": fund,
					"amount": amount,
				},
			)
		collection.insert(ignore_permissions=True)

		html = frappe.get_print("Collection", collection.name, "Collection Count Sheet")

		self.assertIn(f'<td class="num">{fmt_money(30)}</td>', html)
		self.assertIn(f'<td class="num">{fmt_money(70)}</td>', html)

	def test_sermon_outline_prints_the_scripture_and_date(self):
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Outline",
				"scripture": "John 3:16",
				"sermon_date": "2031-06-01",
			}
		).insert(ignore_permissions=True)

		html = frappe.get_print("Sermon", sermon.name, "Sermon Outline")

		self.assertIn('<div class="scripture">John 3:16</div>', html)
		self.assertIn("Sunday, June 1, 2031", html)

	def test_expense_voucher_prints_the_payment_only_once_it_is_paid(self):
		expense = frappe.get_doc({"doctype": "Expense", "name": "_Test Voucher", "amount": 40})
		unpaid = frappe.get_print("Expense", print_format="Expense Voucher", doc=expense)

		expense.update({"paid_on": "2031-06-02", "payment_reference": "Check <1042>"})
		paid = frappe.get_print("Expense", print_format="Expense Voucher", doc=expense)

		self.assertNotIn("Paid On", unpaid)
		self.assertIn("Monday, June 2, 2031", paid)
		self.assertIn("Check &lt;1042&gt;", paid)

	def test_print_dates_take_the_long_form_whatever_the_system_date_format(self):
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Preached Outline",
				"presentation_history": [{"date": "2031-06-08", "location": "Main Hall"}],
			}
		).insert(ignore_permissions=True)

		self.addCleanup(setattr, frappe.local, "user_date_format", None)
		frappe.local.user_date_format = "dd-mm-yyyy"

		html = frappe.get_print("Sermon", sermon.name, "Sermon Outline")

		self.assertIn("Most recently preached: Sunday, June 8, 2031", html)

	def test_prayer_list_prints_an_unspoken_request_with_no_body(self):
		request = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Unspoken Request",
				"type": ensure("Prayer Request Type", {"type": "Health"}),
			}
		).insert(ignore_permissions=True)

		html = frappe.get_print("Prayer Request", request.name, "Prayer List")

		self.assertIn('<div class="body"></div>', html)
		self.assertNotIn("no such element", html)

	def test_print_text_is_translated(self):
		ensure(
			"Translation",
			{"language": "de", "source_text": "Prepared by {0}", "translated_text": "Vorbereitet von {0}"},
		)
		preacher = make_person("Paula", "_Test Preacher")
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Translated Outline", "prepared_by": preacher.name}
		).insert(ignore_permissions=True)
		self.addCleanup(clear_translation_cache)
		self.addCleanup(setattr, frappe.local, "lang", frappe.local.lang)
		frappe.local.lang = "de"

		html = frappe.get_print("Sermon", sermon.name, "Sermon Outline")

		self.assertIn("Vorbereitet von Paula _Test Preacher", html)

	def test_a_collection_schedule_item_is_titled_offering(self):
		function = frappe._dict(
			schedule=[
				frappe._dict(item_type="Collection", item="COLL-X", description=None, start=None, is_header=0)
			]
		)

		self.assertEqual(get_schedule_rows(function)[0].title, "Offering")

	def test_sign_in_sheet_prints_the_time_households_visitors_and_guests(self):
		set_adult_age(18)
		_family, father, _mother, son, _grandmother = make_household("_Test Sign-In - John", "Signin")
		visitor = make_person("Ben", "_Test Signin Visitor", membership="Visitor").name
		function = make_function("_Test Sign-In Service", start_time="10:30:00", allow_sign_ups=1)
		checked_in = ensure("Function Attendance Type", {"type": "Checked-In"})
		for person in (son, visitor):
			function.append("attendance", {"person": person, "attendance_type": checked_in})
		function.save(ignore_permissions=True)
		sign_up = frappe.get_doc(
			{
				"doctype": "Function Sign-Up",
				"function": function.name,
				"person": father,
				"attendees": [{"person": father}, {"attendee_name": "Tim _Test Guest"}],
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Function Sign-Up", sign_up.name, "status", "Confirmed")

		html = frappe.get_print("Function", function.name, "Attendance Sign-In Sheet")

		self.assertIn("10:30 AM", html)
		self.assertIn("<td>John &amp; Jane Signin</td>", html)
		self.assertNotIn("_Test Sign-In - John", html)
		self.assertIn("<td>_Test Signin Visitor</td>", html)
		self.assertEqual(html.count("<td>Yes</td>"), 1)
		self.assertIn("<td>Tim _Test Guest</td>", html)

	def test_household_statement_names_the_household_and_prints_the_address(self):
		donor = self.make_person_with_address("_Test Donor")
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Donor Household"}).insert(
			ignore_permissions=True
		)
		doc = frappe._dict(
			church=None,
			person=donor.name,
			family=family.name,
			lines=[],
			total_amount=0,
			from_date=nowdate(),
			to_date=nowdate(),
		)

		html = frappe.render_template("churchit/templates/includes/giving_statement_body.html", {"doc": doc})

		self.assertIn("_Test Donor Household", html)
		self.assertIn("42 Elm Road", html)
		self.assertIn(formatdate(nowdate(), LONG_DATE_FORMAT), html)


class TestRetireChurchDirectoryPrintFormat(RollbackEachTest):
	"""The Church Directory report prints the directory; the Person print format of that name goes."""

	def make_directory_format(self, standard):
		frappe.delete_doc_if_exists("Print Format", retire_church_directory_print_format.CHURCH_DIRECTORY)
		frappe.get_doc(
			{
				"doctype": "Print Format",
				"name": retire_church_directory_print_format.CHURCH_DIRECTORY,
				"doc_type": "Person",
				"module": "Church People",
				"standard": standard,
				"custom_format": 1,
				"print_format_type": "Jinja",
				"html": "<div>{{ doc.full_name }}</div>",
			}
		).db_insert()

	def test_the_shipped_format_and_a_default_naming_it_are_removed(self):
		self.make_directory_format("Yes")
		make_property_setter(
			"Person", None, "default_print_format", "Church Directory", "Data", for_doctype=True
		)

		retire_church_directory_print_format.execute()
		retire_church_directory_print_format.execute()

		self.assertFalse(frappe.db.exists("Print Format", "Church Directory"))
		self.assertFalse(
			frappe.db.exists("Property Setter", {"doc_type": "Person", "value": "Church Directory"})
		)

	def test_a_format_the_church_made_stays(self):
		self.make_directory_format("No")
		make_property_setter(
			"Person", None, "default_print_format", "Church Directory", "Data", for_doctype=True
		)

		retire_church_directory_print_format.execute()

		self.assertTrue(frappe.db.exists("Print Format", "Church Directory"))
		self.assertTrue(
			frappe.db.exists("Property Setter", {"doc_type": "Person", "value": "Church Directory"})
		)
