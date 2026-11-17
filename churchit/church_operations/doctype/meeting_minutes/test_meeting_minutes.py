# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person


class TestMeetingMinutes(FrappeTestCase):
	def minutes(self, audio_recording=None):
		return frappe.get_doc(
			{
				"doctype": "Meeting Minutes",
				"title": "_Test Meeting",
				"meeting_date": "2026-01-01",
				"audio_recording": audio_recording,
			}
		)

	def test_audio_recording_accepts_audio_files(self):
		doc = self.minutes("/private/files/board-meeting.MP3").insert()
		self.addCleanup(doc.delete)
		self.assertEqual(doc.audio_recording, "/private/files/board-meeting.MP3")

	def test_audio_recording_rejects_non_audio_files(self):
		with self.assertRaises(frappe.ValidationError):
			self.minutes("/private/files/board-meeting.pdf").insert()

	def test_audio_recording_is_optional(self):
		doc = self.minutes().insert()
		self.addCleanup(doc.delete)
		self.assertFalse(doc.audio_recording)

	def test_minutes_are_numbered_from_mm_and_not_the_month(self):
		doc = self.minutes().insert()
		self.addCleanup(doc.delete)
		self.assertRegex(doc.name, r"^MM-\d{4}$")

	def test_approving_fills_approved_on_with_today(self):
		for status in ("Approved", "Published"):
			with self.subTest(status=status):
				doc = self.minutes()
				doc.status = status
				doc.insert()
				self.addCleanup(doc.delete)
				self.assertEqual(str(doc.approved_on), nowdate())

	def test_a_typed_approved_on_is_kept_and_a_draft_has_none(self):
		draft = self.minutes().insert()
		self.addCleanup(draft.delete)
		self.assertIsNone(draft.approved_on)

		draft.update({"status": "Approved", "approved_on": "2026-01-02"})
		draft.save()
		self.assertEqual(str(draft.approved_on), "2026-01-02")


class TestMeetingMinutesRules(FrappeTestCase):
	def minutes(self, **values):
		return frappe.get_doc(
			{"doctype": "Meeting Minutes", "title": "_Test Rules", "meeting_date": "2026-01-10", **values}
		)

	def test_approval_before_the_meeting_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.minutes(approved_on="2026-01-09").insert()

	def test_approval_on_the_meeting_day_passes(self):
		doc = self.minutes(approved_on="2026-01-10").insert()
		self.addCleanup(doc.delete)

	def test_a_stored_reversed_pair_can_still_be_saved(self):
		doc = self.minutes().insert()
		self.addCleanup(doc.delete)
		frappe.db.set_value("Meeting Minutes", doc.name, "approved_on", "2026-01-01")

		doc = frappe.get_doc("Meeting Minutes", doc.name)
		doc.title = "_Test Rules Edited"
		doc.save()

	def test_an_attendee_on_two_rows_is_refused(self):
		person = make_person("_Test Minutes", "Twice").name
		doc = self.minutes(attendees=[{"person": person}, {"person": person}])
		with self.assertRaises(frappe.ValidationError) as caught:
			doc.insert()
		self.assertIn("already in row 1", str(caught.exception))


class TestWhoReadsMinutes(RollbackEachTest):
	"""Church Staff read Published minutes; Church Managers read them at every status."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.staff = ensure_user("_test_minutes_staff@example.com", "MinutesStaff", ["Church Staff"])
		cls.office = ensure_user(
			"_test_minutes_office@example.com", "MinutesOffice", ["Church Staff", "Church People Editor"]
		)
		cls.manager = ensure_user("_test_minutes_manager@example.com", "MinutesManager", ["Church Manager"])

	def setUp(self):
		super().setUp()
		self.minutes = {
			status: frappe.get_doc(
				{
					"doctype": "Meeting Minutes",
					"title": f"_Test {status} Minutes",
					"meeting_date": "2026-01-01",
					"status": status,
				}
			).insert()
			for status in ("Draft", "Reviewed", "Approved", "Published")
		}

	def readable(self, user):
		return {
			status
			for status, doc in self.minutes.items()
			if frappe.has_permission("Meeting Minutes", "read", doc, user=user)
		}

	def listed(self, user):
		frappe.set_user(user)
		names = set(frappe.get_list("Meeting Minutes", pluck="name"))
		frappe.set_user("Administrator")
		return {status for status, doc in self.minutes.items() if doc.name in names}

	def test_staff_read_and_list_only_published_minutes(self):
		for user in (self.staff, self.office):
			with self.subTest(user):
				self.assertEqual(self.readable(user), {"Published"})
				self.assertEqual(self.listed(user), {"Published"})

	def test_staff_cannot_change_published_minutes(self):
		self.assertFalse(
			frappe.has_permission("Meeting Minutes", "write", self.minutes["Published"], user=self.staff)
		)

	def test_a_manager_reads_and_lists_minutes_at_every_status(self):
		self.assertEqual(self.readable(self.manager), set(self.minutes))
		self.assertEqual(self.listed(self.manager), set(self.minutes))
