# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading
from unittest import mock
from urllib.parse import urlencode

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, set_request
from frappe.website.serve import get_response

from churchit.church_ministries.member_ministry_team import (
	answer_by_key,
	answer_own_assignment,
	ask_for_replacement,
	ask_for_replacement_by_key,
	ask_replacement,
	get_candidates,
	get_replacement_candidates,
	get_replacement_candidates_by_key,
)
from churchit.patches.v1_0 import (
	add_ministry_team_replacement_template,
	name_the_replacement_in_ministry_team_decline,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)

ASSIGNMENT = "churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment"
MEMBER = "churchit.church_ministries.member_ministry_team"


def email(name):
	return [{"email_address": f"_test_replace_{name}@example.com"}]


def set_decline_html(html):
	frappe.db.set_value("Email Template", "Ministry Team Decline", "response_html", html)


class TestReplacementRequests(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		add_ministry_team_replacement_template.execute()
		set_decline_html(name_the_replacement_in_ministry_team_decline.SHIPPED_HTML)
		name_the_replacement_in_ministry_team_decline.execute()
		cls.user = ensure_user("_test_replace_member@example.com", "Replace")
		cls.member = make_person("_Test Replace", "Member", user=cls.user, emails=email("member"))
		cls.ruth = make_person("_Test Replace", "Ruth", emails=email("ruth"))
		cls.boaz = make_person("_Test Replace", "Boaz", emails=email("boaz"))
		cls.away = make_person("_Test Replace", "Away")
		cls.late = make_person("_Test Replace", "Late")
		frappe.db.set_value("Person", cls.late.name, "is_deceased", 1)
		cls.other = make_person("_Test Replace", "Other")
		cls.coordinator = make_person("_Test Replace", "Coordinator", emails=email("coordinator"))
		cls.position = make_team_position(
			"_Test Replace Usher",
			[p.name for p in (cls.member, cls.ruth, cls.boaz, cls.away, cls.late, cls.other)],
			ministry_name="_Test Replace Ministry",
		)
		frappe.db.set_value("Ministry", cls.position.ministry, "team_coordinator", cls.coordinator.name)
		cls.day = add_days(getdate(), 10)
		cls.sunday = make_function(
			"_Test Replace Sunday", start_date=cls.day, start_time="10:00:00", end_time="11:00:00"
		)
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": cls.away.name,
				"from_date": cls.day,
				"to_date": cls.day,
			}
		).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		saved = getattr(frappe.local, "request", None), frappe.local.request_ip
		self.addCleanup(
			lambda: (
				setattr(frappe.local, "request", saved[0]),
				setattr(frappe.local, "request_ip", saved[1]),
			)
		)
		# A fresh address for each test keeps reruns under the rate limit.
		frappe.local.request_ip = frappe.generate_hash(length=12)
		self.sendmail = self.start(mock.patch("frappe.sendmail"))
		self.start(mock.patch(f"{ASSIGNMENT}.can_send_email", return_value=True))
		self.start(mock.patch(f"{MEMBER}.can_send_email", return_value=True))
		self.mine = make_team_assignment(self.sunday.name, self.position.name, self.member.name)
		self.theirs = make_team_assignment(self.sunday.name, self.position.name, self.other.name)

	def start(self, patcher):
		self.addCleanup(patcher.stop)
		return patcher.start()

	def render(self, route, **query):
		set_request(method="GET", path=route, query_string=urlencode(query))
		frappe.local.request_ip = frappe.generate_hash(length=12)
		frappe.local.form_dict = frappe._dict(query)
		return get_response(route).get_data(as_text=True)

	def get(self, assignment):
		return frappe.get_doc("Ministry Team Assignment", assignment)

	def ask(self, replacement):
		frappe.set_user(self.user)
		ask_for_replacement(self.mine.name, replacement)
		frappe.set_user("Administrator")
		return self.get({"replaces": self.mine.name, "person": replacement})

	def emailed(self, name):
		return [
			call.kwargs
			for call in self.sendmail.call_args_list
			if f"_test_replace_{name}@example.com" in call.kwargs["recipients"]
		]

	def test_the_candidates_are_the_roster_people_free_to_serve_then(self):
		frappe.set_user(self.user)
		candidates = get_replacement_candidates(self.mine.name)

		# The member, Other (asked already), Away (blocked) and Late (deceased) are not offered.
		self.assertEqual(sorted(row.person for row in candidates), sorted([self.ruth.name, self.boaz.name]))
		self.assertEqual({row.full_name for row in candidates}, {"_Test Replace Ruth", "_Test Replace Boaz"})

	def test_someone_who_serves_at_the_function_in_another_position_is_not_offered(self):
		greeter = make_team_position(
			"_Test Replace Greeter", [self.boaz.name], ministry_name="_Test Replace Ministry"
		)
		make_team_assignment(self.sunday.name, greeter.name, self.boaz.name)

		frappe.set_user(self.user)
		candidates = get_replacement_candidates(self.mine.name)
		self.assertEqual([row.person for row in candidates], [self.ruth.name])

	def test_the_request_is_one_pending_assignment_emailed_at_once(self):
		request = self.ask(self.ruth.name)

		self.assertEqual(
			(request.status, request.position, request.function),
			("Pending", self.position.name, self.sunday.name),
		)
		self.assertIsNotNone(request.requested_on)
		[sent] = self.emailed("ruth")
		self.assertEqual(sent["reference_name"], request.name)
		self.assertIn(f"/ministry-team-response?key={request.response_key}", sent["message"])
		self.assertEqual(self.get(self.mine.name).status, "Pending")

	def test_a_request_without_an_email_waits_for_the_daily_job(self):
		with mock.patch(f"{MEMBER}.get_primary_email", return_value=None):
			request = self.ask(self.ruth.name)

		self.assertIsNone(request.requested_on)
		self.assertEqual(self.emailed("ruth"), [])

	def test_an_ask_reads_with_locks_after_the_function_lock(self):
		locks = mock.Mock()
		for method in ("get_value", "get_values"):
			locks.attach_mock(
				self.start(mock.patch.object(frappe.db, method, wraps=getattr(frappe.db, method))), method
			)

		self.ask(self.ruth.name)

		locked = [call.args for call in locks.mock_calls if call.kwargs.get("for_update")]
		self.assertEqual(locked[0][0], "Function")
		filters = [args[1] for args in locked if isinstance(args[1], dict)]
		self.assertIn({"function": self.sunday.name, "position": self.position.name}, filters)
		self.assertTrue(any(filter.get("replaces") == self.mine.name for filter in filters))

	def test_after_the_replacement_accepts_the_original_is_declined(self):
		request = self.ask(self.ruth.name)

		frappe.set_user("Guest")
		answer_by_key(request.response_key, "Accepted")

		frappe.set_user("Administrator")
		original = self.get(self.mine.name)
		self.assertEqual(
			(original.status, original.decline_reason), ("Declined", "Replaced by _Test Replace Ruth")
		)
		self.assertEqual(self.get(request.name).status, "Accepted")
		[coordinator] = self.emailed("coordinator")
		self.assertIn("_Test Replace Ruth takes the place.", coordinator["message"])
		self.assertNotIn("open again", coordinator["message"])
		[told] = self.emailed("member")
		self.assertEqual(told["reference_name"], self.mine.name)
		self.assertIn("_Test Replace Ruth", told["message"])
		self.assertIn("no longer serve", told["message"])

	def test_a_replaced_place_cannot_be_accepted_again(self):
		request = self.ask(self.ruth.name)
		frappe.set_user("Guest")
		answer_by_key(request.response_key, "Accepted")

		with self.assertRaisesRegex(frappe.ValidationError, "Your place went to _Test Replace Ruth"):
			answer_by_key(self.mine.response_key, "Accepted")
		html = self.render("ministry-team-response", key=self.mine.response_key)
		self.assertIn("Your place went to _Test Replace Ruth.", html)
		self.assertNotIn('data-status="Accepted"', html)

		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "Your place went to _Test Replace Ruth"):
			answer_own_assignment(self.mine.name, "Accepted")
		html = self.render("ministry-team")
		self.assertIn("Your place went to _Test Replace Ruth.", html)
		self.assertNotIn(f'data-assignment="{self.mine.name}" data-status="Accepted"', html)

		frappe.set_user("Administrator")
		self.assertEqual(self.get(self.mine.name).status, "Declined")

	def test_the_ministry_team_page_shows_a_pending_request(self):
		self.ask(self.ruth.name)

		frappe.set_user(self.user)
		html = self.render("ministry-team")
		self.assertIn("You asked _Test Replace Ruth to take your place.", html)
		self.assertNotIn(f'team-replace" data-assignment="{self.mine.name}"', html)

	def test_if_the_replacement_declines_the_original_keeps_its_status(self):
		frappe.set_user(self.user)
		answer_own_assignment(self.mine.name, "Accepted")
		request = self.ask(self.ruth.name)

		frappe.set_user("Guest")
		answer_by_key(request.response_key, "Declined", "Busy")

		frappe.set_user("Administrator")
		self.assertEqual(self.get(self.mine.name).status, "Accepted")
		self.assertEqual(self.emailed("coordinator"), [])
		[told] = self.emailed("member")
		self.assertIn("still serve", told["message"])
		self.assertIn(f"/ministry-team-response?key={self.mine.response_key}", told["message"])

	def test_a_second_request_while_one_is_pending_fails(self):
		request = self.ask(self.ruth.name)

		with self.assertRaisesRegex(frappe.ValidationError, "_Test Replace Ruth"):
			self.ask(self.boaz.name)
		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "_Test Replace Ruth"):
			get_replacement_candidates(self.mine.name)

		frappe.set_user("Administrator")
		request.respond("Declined")
		request.save(ignore_permissions=True)
		self.assertEqual(self.ask(self.boaz.name).status, "Pending")

	def test_the_replacement_must_be_a_candidate(self):
		for person in (self.away, self.late, self.other, self.member, self.coordinator):
			with (
				self.subTest(person=person.last_name),
				self.assertRaisesRegex(frappe.ValidationError, "Choose someone"),
			):
				self.ask(person.name)
		self.assertFalse(frappe.db.exists("Ministry Team Assignment", {"replaces": self.mine.name}))

	def test_a_declined_started_or_unanswered_replacement_place_asks_no_one(self):
		request = self.ask(self.ruth.name)
		with self.assertRaisesRegex(frappe.ValidationError, "Only a place you hold"):
			get_candidates(request)

		frappe.set_user(self.user)
		answer_own_assignment(self.mine.name, "Declined")
		with self.assertRaisesRegex(frappe.ValidationError, "Only a place you hold"):
			ask_for_replacement(self.mine.name, self.boaz.name)

		frappe.set_user("Administrator")
		self.mine.db_set("status", "Pending")
		frappe.db.set_value("Function", self.sunday.name, "start_date", add_days(getdate(), -1))
		frappe.clear_document_cache("Function", self.sunday.name)
		frappe.set_user(self.user)
		with self.assertRaisesRegex(frappe.ValidationError, "Only a place you hold"):
			get_replacement_candidates(self.mine.name)

	def test_a_member_cannot_ask_for_another_persons_assignment(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			get_replacement_candidates(self.theirs.name)
		with self.assertRaises(frappe.PermissionError):
			ask_for_replacement(self.theirs.name, self.ruth.name)

		frappe.set_user("Guest")
		for key in ("", "not-a-key"):
			with self.assertRaises(frappe.PermissionError):
				get_replacement_candidates_by_key(key)
			with self.assertRaises(frappe.PermissionError):
				ask_for_replacement_by_key(key, self.ruth.name)

		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Ministry Team Assignment", {"replaces": ("is", "set")}))

	def test_the_emailed_link_asks_for_a_replacement(self):
		frappe.set_user("Guest")
		candidates = get_replacement_candidates_by_key(self.mine.response_key)
		self.assertIn(self.boaz.name, [row.person for row in candidates])

		ask_for_replacement_by_key(self.mine.response_key, self.boaz.name)

		html = self.render("ministry-team-response", key=self.mine.response_key)
		self.assertIn("You asked _Test Replace Boaz to take your place.", html)
		self.assertNotIn('id="team-replacement-find"', html)

	def test_a_replaces_link_set_by_hand_is_refused(self):
		manager = ensure_user("_test_replace_manager@example.com", "Replace", roles=("Church Manager",))
		frappe.set_user(manager)
		values = {
			"doctype": "Ministry Team Assignment",
			"function": self.sunday.name,
			"position": self.position.name,
			"person": self.ruth.name,
		}
		with self.assertRaisesRegex(frappe.ValidationError, "Ask for a replacement"):
			frappe.get_doc({**values, "replaces": self.mine.name}).insert()

		hand_made = frappe.get_doc(values).insert()
		hand_made.replaces = ""
		hand_made.save()
		hand_made.replaces = self.mine.name
		with self.assertRaisesRegex(frappe.ValidationError, "cannot change"):
			hand_made.save()

	def test_links_sent_before_replacements_still_answer(self):
		frappe.set_user("Guest")
		html = self.render("ministry-team-response", key=self.theirs.response_key)
		self.assertIn("team-answer", html)
		self.assertIn('id="team-replacement-find"', html)

		answer_by_key(self.theirs.response_key, "Declined")

		frappe.set_user("Administrator")
		self.assertEqual(self.get(self.theirs.name).status, "Declined")
		[coordinator] = self.emailed("coordinator")
		self.assertIn("The position is open again.", coordinator["message"])

	def test_the_ministry_team_page_offers_a_replacement_on_own_assignments(self):
		frappe.set_user(self.user)
		html = self.render("ministry-team")
		self.assertIn(f'class="btn btn-sm btn-default team-replace" data-assignment="{self.mine.name}"', html)
		self.assertNotIn(f'data-assignment="{self.theirs.name}"', html)

	def test_the_decline_patch_keeps_a_churchs_own_words(self):
		set_decline_html("<p>Our own words</p>")
		name_the_replacement_in_ministry_team_decline.execute()
		self.assertEqual(
			frappe.db.get_value("Email Template", "Ministry Team Decline", "response_html"),
			"<p>Our own words</p>",
		)

	def test_the_patch_adds_the_template_once(self):
		frappe.delete_doc("Email Template", "Ministry Team Replacement")
		add_ministry_team_replacement_template.execute()
		add_ministry_team_replacement_template.execute()
		self.assertEqual(frappe.db.count("Email Template", {"name": "Ministry Team Replacement"}), 1)


class TestReplacementRace(FrappeTestCase):
	"""Asks at once, each with its own connection. Commits real data, deleted at the end."""

	def setUp(self):
		people = [make_person("_Test Replace Race", name).name for name in ("Ana", "Ben", "Ruth", "Boaz")]
		self.ana, self.ben, self.ruth, self.boaz = people
		self.position = make_team_position("_Test Replace Race Usher", people).name
		self.function = make_function(
			"_Test Replace Race", start_date=add_days(getdate(), 10), start_time="10:00:00"
		).name
		self.anas = make_team_assignment(self.function, self.position, self.ana).name
		self.bens = make_team_assignment(self.function, self.position, self.ben).name
		frappe.db.commit()
		self.addCleanup(self.delete_race_data, people)

	def delete_race_data(self, people):
		frappe.db.rollback()
		assignments = frappe.get_all(
			"Ministry Team Assignment", {"function": self.function}, pluck="name", order_by="creation desc"
		)
		records = [
			*(("Ministry Team Assignment", name) for name in assignments),
			("Function", self.function),
			("Ministry Team Position", self.position),
			*(("Person", person) for person in people),
		]
		for doctype, name in records:
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True, delete_permanently=True)
		frappe.db.commit()

	def race(self, asks: list[tuple[str, str]]) -> list:
		"""Make each (assignment, replacement) ask at once. Returns each result."""
		site, sites_path = frappe.local.site, frappe.local.sites_path
		# Each request reads before either commits, so a plain read would answer from a snapshot without the other.
		barrier = threading.Barrier(len(asks), timeout=30)
		results = []

		def ask(assignment, replacement):
			frappe.init(site, sites_path=sites_path)
			frappe.connect()
			try:
				frappe.db.get_value("Ministry Team Assignment", assignment, "status")
				barrier.wait()
				ask_replacement(assignment, replacement)
				frappe.db.commit()
				results.append("asked")
			except Exception as error:
				results.append(error)
			finally:
				frappe.destroy()

		threads = [threading.Thread(target=ask, args=pair) for pair in asks]
		with mock.patch(f"{MEMBER}.can_send_email", return_value=False):
			for thread in threads:
				thread.start()
			for thread in threads:
				thread.join(timeout=60)
		return results

	def assert_one_asked(self, results):
		self.assertEqual(results.count("asked"), 1)
		self.assertIsInstance(next(result for result in results if result != "asked"), frappe.ValidationError)

	def test_two_asks_for_one_place_make_one_request(self):
		self.assert_one_asked(self.race([(self.anas, self.ruth), (self.anas, self.boaz)]))
		self.assertEqual(frappe.db.count("Ministry Team Assignment", {"replaces": self.anas}), 1)

	def test_two_places_cannot_ask_one_person_at_once(self):
		self.assert_one_asked(self.race([(self.anas, self.ruth), (self.bens, self.ruth)]))
		self.assertEqual(
			frappe.db.count("Ministry Team Assignment", {"function": self.function, "person": self.ruth}), 1
		)
