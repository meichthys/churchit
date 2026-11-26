# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.address_states import get_state_names
from churchit.patches.v1_0 import name_address_states_in_full
from churchit.tests.helpers import RollbackEachTest, make_address


class TestAddressStates(RollbackEachTest):
	"""An address in a country with a state list names a state of that list, by its full name."""

	def test_state_field_is_a_pick_list(self):
		self.assertEqual(frappe.get_meta("Address").get_field("state").fieldtype, "Autocomplete")

	def test_a_code_or_name_in_any_case_is_stored_as_the_full_name(self):
		for typed, country, stored in (
			("IL", "United States", "Illinois"),
			(" illinois ", "United States", "Illinois"),
			("on", "Canada", "Ontario"),
			("NSW", "Australia", "New South Wales"),
			("Québec", "Canada", "Quebec"),
			("AE", "United States", "Armed Forces Europe"),
		):
			with self.subTest(typed=typed):
				address = make_address(f"_Test State {typed}", state=typed, country=country)

				self.assertEqual(address.state, stored)

	def test_a_state_that_the_country_does_not_have_is_refused(self):
		with self.assertRaisesRegex(
			frappe.ValidationError, "Ontario is not a state or province of United States"
		):
			make_address("_Test Wrong State", state="Ontario")

	def test_moving_an_address_to_another_country_checks_its_state(self):
		address = make_address("_Test Moving State", state="IL")
		address.country = "Canada"

		self.assertRaises(frappe.ValidationError, address.save)

	def test_a_country_without_a_list_takes_any_state(self):
		address = make_address("_Test Free State", state="Greater London", country="United Kingdom")

		self.assertEqual(address.state, "Greater London")
		self.assertEqual(get_state_names("United Kingdom"), [])

	def test_an_old_state_stays_until_someone_changes_it(self):
		address = make_address("_Test Old State")
		address.db_set("state", "Ill.")
		address.reload()

		address.city = "Shelbyville"
		address.save()

		self.assertEqual(address.state, "Ill.")

	def test_the_desk_lists_the_full_names(self):
		states = get_state_names("United States")

		self.assertIn("Illinois", states)
		self.assertNotIn("IL", states)
		self.assertEqual(states, sorted(states))

	def test_patch_names_each_listed_state_in_full_and_leaves_the_rest(self):
		listed = make_address("_Test Patch Listed")
		unknown = make_address("_Test Patch Unknown")
		elsewhere = make_address("_Test Patch Elsewhere", country="United Kingdom")
		for address, state in ((listed, "il"), (unknown, "Ill."), (elsewhere, "IL")):
			address.db_set("state", state)

		name_address_states_in_full.execute()

		self.assertEqual(
			[
				frappe.db.get_value("Address", address.name, "state")
				for address in (listed, unknown, elsewhere)
			],
			["Illinois", "Ill.", "IL"],
		)

	def test_patch_names_erpnext_tax_rule_states_in_full(self):
		if not frappe.db.table_exists("Tax Rule"):
			self.skipTest("ERPNext is not installed.")
		rule = frappe.get_doc(
			{
				"doctype": "Tax Rule",
				"name": "_Test State Tax Rule",
				"billing_country": "United States",
				"billing_state": "IL",
				"shipping_country": "Canada",
				"shipping_state": "Somewhere",
			}
		)
		rule.db_insert()

		name_address_states_in_full.execute()

		self.assertEqual(
			frappe.db.get_value("Tax Rule", rule.name, ["billing_state", "shipping_state"]),
			("Illinois", "Somewhere"),
		)
