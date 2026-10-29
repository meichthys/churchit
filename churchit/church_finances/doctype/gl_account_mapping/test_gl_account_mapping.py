# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_user,
	force_single_church,
	make_two_churches,
)


def map_account(mapping_for, record, account, church=None):
	return frappe.get_doc(
		{
			"doctype": "GL Account Mapping",
			"mapping_for": mapping_for,
			"record": record,
			"account": account,
			"church": church,
		}
	).insert(ignore_permissions=True)


class TestGLAccountMapping(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.payment_type = ensure("Payment Type", {"type": "_Test GL Mapping Card"})
		cls.fund_a, cls.fund_b = (
			frappe.get_doc({"doctype": "Fund", "fund": f"_Test GL Mapping Fund {church}", "church": church})
			.insert(ignore_permissions=True)
			.name
			for church in (cls.branch_a, cls.branch_b)
		)
		cls.finance_a = ensure_user("_test_gl_finance_a@example.com", "GL A", roles=("Church Finance",))
		cls.finance_b = ensure_user("_test_gl_finance_b@example.com", "GL B", roles=("Church Finance",))
		set_user_church(cls.finance_a, cls.branch_a)
		set_user_church(cls.finance_b, cls.branch_b)

	def test_mappings_are_scoped(self):
		mine = map_account("Payment Type", self.payment_type, "1010 Bank", self.branch_a).name
		theirs = map_account("Payment Type", self.payment_type, "1020 Bank", self.branch_b).name

		assert_scoped(self, "GL Account Mapping", self.finance_a, mine, theirs)

	def test_a_church_maps_a_record_once(self):
		map_account("Payment Type", self.payment_type, "1010 Bank", self.branch_a)
		map_account("Payment Type", self.payment_type, "1020 Bank", self.branch_b)

		with self.assertRaises(frappe.DuplicateEntryError):
			map_account("Payment Type", self.payment_type, "1030 Bank", self.branch_a)

	def test_a_mapping_takes_the_church_of_whoever_adds_it(self):
		frappe.set_user(self.finance_b)
		mapping = map_account("Payment Type", self.payment_type, "1020 Bank")

		self.assertEqual(mapping.church, self.branch_b)

	def test_a_fund_mapping_cannot_name_another_churchs_fund(self):
		map_account("Fund", self.fund_a, "3010 General", self.branch_a)

		with self.assertRaises(frappe.PermissionError):
			map_account("Fund", self.fund_b, "3010 General", self.branch_a)

	def test_a_church_mapping_names_its_own_church(self):
		map_account("Church", self.branch_a, "1010 Bank", self.branch_a)

		with self.assertRaises(frappe.ValidationError):
			map_account("Church", self.branch_b, "1010 Bank", self.branch_a)


class TestGLAccountMappingSingleChurch(RollbackEachTest):
	def setUp(self):
		super().setUp()
		force_single_church()

	def test_a_single_church_site_maps_a_record_once(self):
		payment_type = ensure("Payment Type", {"type": "_Test GL Mapping Card"})
		mapping = map_account("Payment Type", payment_type, "1010 Bank")

		self.assertFalse(mapping.church)
		with self.assertRaises(frappe.DuplicateEntryError):
			map_account("Payment Type", payment_type, "1030 Bank")
