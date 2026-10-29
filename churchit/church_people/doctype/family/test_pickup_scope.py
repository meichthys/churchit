# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import document_list

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.page.check_in.check_in import get_pickup_family
from churchit.church_people.doctype.family.test_family import make_household_of
from churchit.patches.v1_0 import make_authorized_pickups_records
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_user,
	make_person,
	make_two_churches,
)


class TestPickupScope(RollbackEachTest):
	"""No reader of church B learns who may collect a church A family's children."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.readers = {
			role: cls.user(f"_test_pickup_scope_{role.split()[-1].lower()}_b@example.com", role, cls.branch_b)
			for role in ("Church Staff", "Church Check-In", "Church People Editor")
		}

	@staticmethod
	def user(email, role, church):
		ensure_user(email, "PickupScope", roles=(role,))
		set_user_church(email, church)
		return email

	def setUp(self):
		super().setUp()
		self.parent = make_person("_Test Pickup Scope", "Parent", church=self.branch_a).name
		self.aunt = make_person("_Test Pickup Scope", "Aunt", church=self.branch_a).name
		self.family = make_household_of(self.parent, primary_contact=self.parent)
		self.pickup = make_pickup(self.family, self.aunt, notes="_Test gate code")
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def test_another_church_reads_no_pickup(self):
		for reader in self.readers.values():
			frappe.set_user(reader)
			try:
				for read in (self.list_pickups, self.rest_list):
					try:
						rows = read()
					except frappe.PermissionError:
						rows = []
					leaked = [
						row for row in rows if self.aunt in row.values() or "_Test gate code" in row.values()
					]
					self.assertFalse(leaked, f"{reader} reads church A pickups through {read.__name__}")
			finally:
				frappe.set_user("Administrator")

	def test_a_people_editor_manages_only_their_churchs_pickups(self):
		other_parent = make_person("_Test Pickup Scope", "Other", church=self.branch_b).name
		theirs = make_pickup(make_household_of(other_parent, primary_contact=other_parent), self.aunt)
		editor_a = self.user("_test_pickup_scope_editor_a@example.com", "Church People Editor", self.branch_a)

		assert_scoped(self, "Authorized Pickup", editor_a, self.pickup, theirs)

		frappe.set_user(self.readers["Church People Editor"])
		try:
			with self.assertRaises(frappe.PermissionError):
				make_pickup(self.family, other_parent, ignore_permissions=False)
		finally:
			frappe.set_user("Administrator")

	def test_the_pickups_move_with_the_family(self):
		frappe.get_doc("Person", self.parent).update({"church": self.branch_b}).save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Family", self.family, "church"), self.branch_b)
		self.assertEqual(frappe.db.get_value("Authorized Pickup", self.pickup, "church"), self.branch_b)

	def test_the_patch_points_old_rows_at_their_family(self):
		if not frappe.db.has_column("Authorized Pickup", "parent"):
			self.skipTest("This site never had Authorized Pickup as a Family table.")
		frappe.db.set_value(
			"Authorized Pickup",
			self.pickup,
			{"family": None, "church": None, "parent": self.family, "parenttype": "Family"},
			update_modified=False,
		)

		make_authorized_pickups_records.execute()
		make_authorized_pickups_records.execute()

		self.assertEqual(
			frappe.db.get_value("Authorized Pickup", self.pickup, ["family", "church"]),
			(self.family, self.branch_a),
		)
		pickups = get_pickup_family(self.family, [])["pickups"]
		self.assertEqual([pickup["person"] for pickup in pickups], [self.aunt])

	def list_pickups(self):
		return frappe.get_list("Authorized Pickup", fields=["person", "notes"])

	def rest_list(self):
		frappe.local.form_dict = frappe._dict(fields=json.dumps(["person", "notes"]), limit=500)
		return document_list("Authorized Pickup")


def make_pickup(family, person, ignore_permissions=True, **values):
	return (
		frappe.get_doc({"doctype": "Authorized Pickup", "family": family, "person": person, **values})
		.insert(ignore_permissions=ignore_permissions)
		.name
	)
