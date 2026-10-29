# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.connections import get_open_count
from churchit.tests.helpers import ensure_user, make_person, make_two_churches, set_private_people


class TestConnectionCounts(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		set_private_people(False)
		cls.addClassCleanup(frappe.clear_cache)
		cls.person = make_person("_Test Connections", "Counseled", church=cls.branch_b).name
		frappe.get_doc(
			{"doctype": "Counseling Case", "person": cls.person, "start_date": frappe.utils.today()}
		).insert(ignore_permissions=True)
		cls.pastor_a = cls.make_user("pastor_a", cls.branch_a, ("Church Staff", "Church Pastoral Care"))
		cls.pastor_b = cls.make_user("pastor_b", cls.branch_b, ("Church Staff", "Church Pastoral Care"))
		cls.staff_b = cls.make_user("staff_b", cls.branch_b, ("Church Staff",))

	@classmethod
	def make_user(cls, key, church, roles):
		user = ensure_user(f"_test_connections_{key}@example.com", key, roles=roles)
		make_person(key, "_Test Connections", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")
		# Frappe's get_open_count limits the session's statements to 1 second, meant to end with the request.
		frappe.db.set_execution_timeout(0)

	def counts_for(self, user):
		frappe.set_user(user)
		found = get_open_count("Person", self.person, ["Counseling Case"])["count"]["external_links_found"]
		return {row["doctype"]: row["count"] for row in found}

	def test_the_church_that_holds_the_records_counts_them(self):
		self.assertEqual(self.counts_for(self.pastor_b), {"Counseling Case": 1})

	def test_another_churchs_records_are_not_counted(self):
		"""Every church reads the shared directory, but a counseling case stays with the person's church."""
		self.assertEqual(self.counts_for(self.pastor_a), {"Counseling Case": 0})

	def test_a_doctype_the_reader_cannot_read_is_not_counted(self):
		"""Asked for by name, Frappe counted a person's counseling cases for anyone who could open the person."""
		self.assertEqual(self.counts_for(self.staff_b), {})
