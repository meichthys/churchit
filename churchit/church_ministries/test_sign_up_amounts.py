# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import create_doc, update_doc
from frappe.desk.form.save import savedocs
from frappe.utils import add_days, nowdate

from churchit.church_ministries.sign_up_amounts import get_amount_due, get_discount
from churchit.church_ministries.web_form.function_sign_up.function_sign_up import (
	get_function_sign_up_items,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	make_function,
	make_person,
)

SIGN_UP = "Function Sign-Up"


class TestSignUpAmounts(RollbackEachTest):
	"""Adult 20 and Child 10 a seat, Shirt 15 each: two adults, a child and two shirts make 80."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.church = ensure_root_church()
		cls.shirt = ensure("Sign-Up Item", {"item": "_Test Priced Shirt"})
		fund = ensure(
			"Fund", {"fund": "_Test Sign-Up Fees"}, {"fund": "_Test Sign-Up Fees", "church": cls.church}
		)
		function = make_function(
			"_Test Priced Function", church=cls.church, allow_sign_ups=1, sign_up_fund=fund
		)
		function.append("selections", {"selection": "Adult", "price": 20})
		function.append("selections", {"selection": "Child", "price": 10})
		function.append("table_cxhh", {"item": cls.shirt, "quantity_needed": 10, "price": 15})
		function.save(ignore_permissions=True)
		cls.function = function.name

		cls.member = ensure_user("_test_priced_member@example.com", "Priced")
		cls.member_person = make_person("_Test Priced", "Member", church=cls.church, user=cls.member).name
		cls.editor = ensure_user("_test_priced_editor@example.com", "Editor", roles=("Church People Editor",))
		make_person("_Test Priced", "Editor", church=cls.church, user=cls.editor)
		cls.person = make_person("_Test Priced", "Registrant", church=cls.church).name

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def add_discount(self, **values):
		function = frappe.get_doc("Function", self.function)
		function.append("discounts", values)
		function.save(ignore_permissions=True)

	def make_sign_up_values(self, person=None, **values):
		return {
			"doctype": SIGN_UP,
			"function": self.function,
			"person": person or self.person,
			"attending": 0,
			"attendees": [
				{"attendee_name": "_Test Adult One", "selection": "Adult"},
				{"attendee_name": "_Test Adult Two", "selection": "Adult"},
				{"attendee_name": "_Test Child", "selection": "Child"},
			],
			"table_iprj": [{"item": self.shirt, "my_quantity": 2}],
			**values,
		}

	def sign_up(self, **values):
		return frappe.get_doc(self.make_sign_up_values(**values)).insert(ignore_permissions=True)

	def test_amount_due_adds_selection_and_item_prices(self):
		sign_up = self.sign_up()
		self.assertEqual(sign_up.amount_due, 80)
		self.assertEqual(sign_up.discount, 0)
		self.assertEqual(sign_up.table_iprj[0].price, 15)

	def test_items_only_sign_up_pays_for_its_items(self):
		sign_up = frappe.get_doc(self.make_sign_up_values(attendees=[]))
		self.assertEqual(get_amount_due(sign_up), 30)

	def test_desk_save_overwrites_browser_amounts_and_prices(self):
		frappe.set_user(self.editor)
		values = self.make_sign_up_values(amount_due=1, discount=79)
		values["table_iprj"][0]["price"] = 0
		savedocs(json.dumps(values), "Save")

		sign_up = frappe.get_doc(SIGN_UP, {"function": self.function, "person": self.person})
		self.assertEqual((sign_up.amount_due, sign_up.discount), (80, 0))
		self.assertEqual(sign_up.table_iprj[0].price, 15)

	def test_rest_insert_and_update_overwrite_browser_amounts_and_prices(self):
		frappe.set_user(self.member)
		values = self.make_sign_up_values(amount_due=0, discount=80)
		values["table_iprj"][0]["price"] = 0
		frappe.local.form_dict = frappe._dict(data=json.dumps(values))
		sign_up = create_doc(SIGN_UP)
		self.assertEqual(sign_up.person, self.member_person)
		self.assertEqual((sign_up.amount_due, sign_up.discount), (80, 0))

		frappe.local.form_dict = frappe._dict(
			data=json.dumps(
				{
					"amount_due": 0,
					"discount": 80,
					"table_iprj": [{"item": self.shirt, "my_quantity": 3, "price": 0}],
				}
			)
		)
		update_doc(SIGN_UP, sign_up.name)
		stored = frappe.get_doc(SIGN_UP, sign_up.name)
		self.assertEqual((stored.amount_due, stored.discount), (95, 0))
		self.assertEqual(stored.table_iprj[0].price, 15)

	def test_negative_quantity_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(table_iprj=[{"item": self.shirt, "my_quantity": -6}])

	def test_amount_due_never_goes_below_zero(self):
		self.add_discount(kind="Group", min_attendees=2, amount=500)
		sign_up = self.sign_up()
		self.assertEqual((sign_up.amount_due, sign_up.discount), (0, 80))

	def test_only_the_largest_discount_applies(self):
		self.add_discount(kind="Group", min_attendees=3, amount=5)
		self.add_discount(kind="Code", code="FAMILY", percent=25)
		self.add_discount(kind="Early Bird", valid_until=add_days(nowdate(), 7), amount=12)
		sign_up = self.sign_up(discount_code="FAMILY")
		self.assertEqual((sign_up.amount_due, sign_up.discount), (60, 20))

	def test_code_matches_without_case(self):
		self.add_discount(kind="Code", code="Family", amount=10)
		self.assertEqual(get_discount(frappe.get_doc(self.make_sign_up_values(discount_code=" fAMILY "))), 10)
		self.assertEqual(get_discount(frappe.get_doc(self.make_sign_up_values(discount_code="FAMILIES"))), 0)
		self.assertEqual(get_discount(frappe.get_doc(self.make_sign_up_values())), 0)

	def test_expired_code_gives_no_discount(self):
		self.add_discount(kind="Code", code="FAMILY", amount=10, valid_until=add_days(nowdate(), -1))
		sign_up = self.sign_up(discount_code="FAMILY")
		self.assertEqual((sign_up.amount_due, sign_up.discount), (80, 0))

	def test_code_added_after_it_ends_gives_no_discount(self):
		sign_up = self.sign_up()
		frappe.db.set_value(SIGN_UP, sign_up.name, "creation", f"{add_days(nowdate(), -10)} 09:00:00")
		self.add_discount(kind="Code", code="FAMILY", amount=10, valid_until=add_days(nowdate(), -3))

		sign_up.reload()
		sign_up.discount_code = "FAMILY"
		sign_up.save(ignore_permissions=True)
		self.assertEqual((sign_up.amount_due, sign_up.discount), (80, 0))

	def test_code_entered_before_it_ends_stays_after_an_edit(self):
		self.add_discount(kind="Code", code="FAMILY", amount=10, valid_until=nowdate())
		sign_up = self.sign_up(discount_code="FAMILY")
		frappe.db.set_value(SIGN_UP, sign_up.name, "creation", f"{add_days(nowdate(), -10)} 09:00:00")
		frappe.db.set_value(
			"Function Sign-Up Discount", {"parent": self.function}, "valid_until", add_days(nowdate(), -3)
		)

		sign_up.reload()
		sign_up.discount_code = "family"
		sign_up.table_iprj[0].my_quantity = 3
		sign_up.save(ignore_permissions=True)
		self.assertEqual((sign_up.amount_due, sign_up.discount), (85, 10))

	def test_attendee_without_a_selection_is_never_free(self):
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(attendees=[{"attendee_name": "_Test No Selection"}])
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(attending=1, attendees=[])

	def test_group_discount_needs_its_attendees(self):
		self.add_discount(kind="Group", min_attendees=4, amount=10)
		self.assertEqual(self.sign_up().discount, 0)

		four = self.make_sign_up_values(person=self.member_person)
		four["attendees"].append({"attendee_name": "_Test Adult Three", "selection": "Adult"})
		self.assertEqual(get_discount(frappe.get_doc(four)), 10)

	def test_early_bird_counts_the_day_of_sign_up_not_a_sent_creation(self):
		self.add_discount(kind="Early Bird", valid_until=add_days(nowdate(), -5), amount=10)
		late = self.sign_up()
		self.assertEqual(late.discount, 0)

		frappe.local.form_dict = frappe._dict(
			data=json.dumps({"creation": f"{add_days(nowdate(), -10)} 09:00:00"})
		)
		with self.assertRaises(frappe.CannotChangeConstantError):
			update_doc(SIGN_UP, late.name)

		early = self.sign_up(person=self.member_person)
		frappe.db.set_value(SIGN_UP, early.name, "creation", f"{add_days(nowdate(), -10)} 09:00:00")
		early.reload()
		early.save(ignore_permissions=True)
		self.assertEqual((early.amount_due, early.discount), (70, 10))

	def test_early_bird_without_a_date_gives_no_discount(self):
		self.add_discount(kind="Early Bird", amount=10)
		self.assertEqual(self.sign_up().discount, 0)

	def test_members_never_read_the_discount_codes(self):
		self.add_discount(kind="Code", code="FAMILY", amount=10)
		frappe.set_user(self.member)
		self.assertFalse(frappe.has_permission("Function", "read", doc=self.function))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Function Sign-Up Discount", parent_doctype="Function", fields=["code"])
		self.assertNotIn("FAMILY", json.dumps(get_function_sign_up_items(self.function)))
