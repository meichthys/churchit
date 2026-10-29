# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.patches.v1_0 import count_prayers_for_requests
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches


class TestPrayer(FrappeTestCase):
	"""before_save builds the title, which is what link fields and lists show."""

	def setUp(self):
		self.person = make_person("_Test Prayer", "Intercessor")

	def _prayer(self, **values):
		return frappe.get_doc(
			{"doctype": "Prayer", "person": self.person.name, "date": "2031-05-01 09:30:00", **values}
		).insert(ignore_permissions=True)

	def test_title_joins_person_and_date(self):
		prayer = self._prayer()
		self.assertEqual(prayer.title, f"{self.person.name} - 2031-05-01 09:30:00")

	def test_title_is_rebuilt_when_the_date_changes(self):
		prayer = self._prayer()
		prayer.date = "2031-06-02 14:00:00"
		prayer.save(ignore_permissions=True)
		self.assertEqual(prayer.title, f"{self.person.name} - 2031-06-02 14:00:00")


class TestPrayerAcrossChurches(RollbackEachTest):
	"""Only the person's own church records their prayers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.care_b = ensure_user("_test_prayer_care_b@example.com", "Care B", roles=("Church Pastoral Care",))
		set_user_church(cls.care_b, cls.branch_b)
		cls.person_a = make_person("_Test Prayer", "Person A", church=cls.branch_a).name
		cls.person_b = make_person("_Test Prayer", "Person B", church=cls.branch_b).name

	def prayer(self, person):
		return frappe.get_doc(
			{"doctype": "Prayer", "person": person, "date": "2031-05-01 09:30:00", "church": self.branch_b}
		)

	def test_another_churchs_staff_cannot_record_a_persons_prayer(self):
		"""Frappe checks the create right on the church the caller sends, before it fetches the person's."""
		frappe.set_user(self.care_b)
		with self.assertRaises(frappe.PermissionError):
			self.prayer(self.person_a).insert()

		self.assertEqual(self.prayer(self.person_b).insert().church, self.branch_b)

	def test_another_church_cannot_take_a_prayer_over(self):
		"""Naming one of its own people moves the prayer to the caller's church, so the stored church counts."""
		name = self.prayer(self.person_a).insert(ignore_permissions=True).name
		frappe.set_user(self.care_b)
		prayer = frappe.get_doc("Prayer", name)
		prayer.update({"person": self.person_b, "church": self.branch_b})

		with self.assertRaises(frappe.PermissionError):
			prayer.save()

	def test_another_churchs_staff_cannot_pray_for_a_request_they_cannot_open(self):
		"""A topic is a child row, which User Permissions skip, and the prayer would change the count."""
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		theirs, own = (
			frappe.get_doc(
				{
					"doctype": "Prayer Request",
					"title": "_Test Scope Count",
					"type": request_type,
					"church": church,
				}
			)
			.insert(ignore_permissions=True)
			.name
			for church in (self.branch_a, self.branch_b)
		)
		frappe.set_user(self.care_b)
		prayer = self.prayer(self.person_b)
		prayer.append("topics", {"topic_type": "Prayer Request", "topic": theirs})

		with self.assertRaises(frappe.PermissionError):
			prayer.insert()
		self.assertEqual(frappe.db.get_value("Prayer Request", theirs, "prayer_count"), 0)

		prayer = self.prayer(self.person_b)
		prayer.append("topics", {"topic_type": "Prayer Request", "topic": own})
		prayer.insert()
		self.assertEqual(frappe.db.get_value("Prayer Request", own, "prayer_count"), 1)


class TestPrayerCount(FrappeTestCase):
	"""A Prayer Request stores how many Prayers name it, without moving its `modified`."""

	def setUp(self):
		self.person = make_person("_Test Prayer", "Counter").name
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		self.first, self.second = (
			frappe.get_doc(
				{"doctype": "Prayer Request", "title": f"_Test Count {number}", "type": request_type}
			)
			.insert(ignore_permissions=True)
			.name
			for number in (1, 2)
		)

	def prayer(self, *requests):
		topics = [{"topic_type": "Prayer Request", "topic": request} for request in requests]
		return frappe.get_doc(
			{"doctype": "Prayer", "person": self.person, "date": "2031-05-01 09:30:00", "topics": topics}
		).insert(ignore_permissions=True)

	def stored(self, request):
		return frappe.db.get_value("Prayer Request", request, ["prayer_count", "modified"])

	def test_moving_a_topic_recounts_both_requests(self):
		first_modified, second_modified = self.stored(self.first)[1], self.stored(self.second)[1]
		prayer = self.prayer(self.first)
		self.assertEqual(self.stored(self.first), (1, first_modified))

		prayer.topics[0].topic = self.second
		prayer.save(ignore_permissions=True)

		self.assertEqual(self.stored(self.first), (0, first_modified))
		self.assertEqual(self.stored(self.second), (1, second_modified))

	def test_a_prayer_that_names_a_request_twice_counts_once(self):
		self.prayer(self.first, self.first)
		self.assertEqual(self.stored(self.first)[0], 1)

	def test_the_patch_counts_the_prayers_recorded_before_the_count(self):
		self.prayer(self.first)
		self.prayer(self.first, self.second)
		frappe.db.set_value(
			"Prayer Request",
			{"name": ("in", [self.first, self.second])},
			"prayer_count",
			0,
			update_modified=False,
		)

		count_prayers_for_requests.execute()
		count_prayers_for_requests.execute()

		self.assertEqual(self.stored(self.first)[0], 2)
		self.assertEqual(self.stored(self.second)[0], 1)
