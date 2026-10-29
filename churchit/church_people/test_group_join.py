# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.handler import execute_cmd
from frappe.utils import add_days, today

from churchit.church_people.group_api import (
	decide_join_request,
	get_open_join_requests,
	join_group,
	joinable_public_groups,
)
from churchit.church_people.privacy import anonymize_person
from churchit.patches.v1_0 import add_group_join_request_templates
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
)

LEADER_ROLE = "_Test Join Leader"


class TestGroupJoin(RollbackEachTest):
	"""A group that requires approval takes requests to join, and its leaders decide them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		add_group_join_request_templates.execute()
		ensure("Group Role", {"role": "Member"})
		ensure("Group Role", {"role": LEADER_ROLE}, {"role": LEADER_ROLE, "is_leader": 1})
		cls.joiner, cls.joiner_user = cls.member("Joiner")
		cls.leader, cls.leader_user = cls.member("Leader")
		cls.co_leader, _co_leader_user = cls.member("Coleader")
		cls.outsider, cls.outsider_user = cls.member("Outsider")
		cls.editor = ensure_user(
			"_test_join_editor@example.com", "_Test Join Editor", roles=("Church People Editor",)
		)
		make_person("_Test Join", "Editor", church=cls.church, user=cls.editor)

	@classmethod
	def member(cls, first_name):
		email = f"_test_join_{first_name.lower()}@example.com"
		user = ensure_user(email, f"_Test Join {first_name}")
		person = make_person(
			first_name, "_Test Join", church=cls.church, user=user, emails=[{"email_address": email}]
		)
		return person.name, user

	def setUp(self):
		super().setUp()
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.can_send_email = mock.patch(
			"churchit.church_people.group_api.can_send_email", return_value=True
		).start()
		self.addCleanup(mock.patch.stopall)
		self.group = self.make_group("_Test Join Group", requires_approval=1)
		frappe.set_user(self.joiner_user)

	def make_group(self, name, **values):
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": name,
				"church": self.church,
				"public": 1,
				"show_in_portal": 1,
				**values,
			}
		)
		for person in (self.leader, self.co_leader):
			group.append("members", {"person": person, "group_role": LEADER_ROLE})
		return group.insert(ignore_permissions=True)

	def members(self, group):
		return frappe.get_all("Group Member", filters={"parent": group}, pluck="person")

	def copies(self, request):
		"""(person, send key) of each email about *request*."""
		names = frappe.get_all(
			"Communication Link",
			filters={
				"link_doctype": "Group Join Request",
				"link_name": request,
				"parenttype": "Communication",
			},
			pluck="parent",
		)
		rows = frappe.get_all(
			"Communication", filters={"name": ("in", names)}, fields=["reference_name", "send_key"]
		)
		return sorted((row.reference_name, row.send_key) for row in rows)

	def request(self):
		return join_group(self.group.name, "I would like to come.")["request"]

	def test_a_request_waits_for_a_leader_and_emails_each_leader_once(self):
		result = join_group(self.group.name, "I would like to come.")

		self.assertEqual(result["requested"], True)
		self.assertEqual(result["group_name"], "_Test Join Group")
		request = frappe.get_doc("Group Join Request", result["request"])
		self.assertEqual(
			(request.person, request.status, request.church), (self.joiner, "Requested", self.church)
		)
		self.assertNotIn(self.joiner, self.members(self.group.name))
		self.assertEqual(
			self.copies(request.name), sorted([(self.leader, "request"), (self.co_leader, "request")])
		)

	def test_a_group_with_no_leader_still_takes_a_request(self):
		frappe.set_user("Administrator")
		leaderless = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Join Leaderless",
				"church": self.church,
				"public": 1,
				"show_in_portal": 1,
				"requires_approval": 1,
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self.joiner_user)
		request = join_group(leaderless.name)["request"]
		self.assertEqual(frappe.db.get_value("Group Join Request", request, "status"), "Requested")
		self.assertEqual(self.copies(request), [])

	def test_a_repeat_call_returns_the_open_request(self):
		first = self.request()
		second = join_group(self.group.name)

		self.assertEqual(second, {"requested": True, "request": first, "group_name": "_Test Join Group"})
		self.assertEqual(
			frappe.db.count("Group Join Request", {"group": self.group.name, "person": self.joiner}), 1
		)
		self.assertEqual(len(self.copies(first)), 2)

	def test_a_leaders_approval_adds_the_member_and_emails_the_person_once(self):
		request = self.request()
		frappe.set_user(self.leader_user)

		self.assertEqual(decide_join_request(request, "1"), {"status": "Approved"})

		self.assertIn(self.joiner, self.members(self.group.name))
		self.assertEqual(
			frappe.db.get_value("Group Join Request", request, ["status", "decided_by"]),
			("Approved", self.leader_user),
		)
		self.assertEqual(self.copies(request).count((self.joiner, "decision")), 1)
		self.assertTrue(
			frappe.db.exists(
				"Communication", {"reference_name": self.joiner, "subject": "Welcome to _Test Join Group"}
			)
		)

	def test_a_denial_adds_no_member(self):
		request = self.request()
		frappe.set_user(self.leader_user)

		self.assertEqual(decide_join_request(request, "0"), {"status": "Denied"})
		self.assertNotIn(self.joiner, self.members(self.group.name))
		self.assertEqual(self.copies(request).count((self.joiner, "decision")), 1)

	def test_a_site_that_cannot_send_email_still_takes_and_decides_a_request(self):
		self.can_send_email.return_value = False
		request = self.request()
		frappe.set_user(self.leader_user)

		self.assertEqual(decide_join_request(request, "1"), {"status": "Approved"})
		self.assertIn(self.joiner, self.members(self.group.name))
		self.assertEqual(self.copies(request), [])
		self.sendmail.assert_not_called()

	def test_a_second_decision_throws(self):
		request = self.request()
		frappe.set_user(self.leader_user)
		decide_join_request(request, "0")

		with self.assertRaises(frappe.ValidationError):
			decide_join_request(request, "1")
		self.assertNotIn(self.joiner, self.members(self.group.name))

	def test_only_a_leader_or_a_group_editor_decides(self):
		request = self.request()
		for user in (self.joiner_user, self.outsider_user, "Guest"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				decide_join_request(request, "1")
		frappe.set_user(self.outsider_user)
		with self.assertRaises(frappe.PermissionError):
			decide_join_request("GJR-DOES-NOT-EXIST", "1")

		frappe.set_user(self.editor)
		self.assertEqual(decide_join_request(request, "1"), {"status": "Approved"})

	def test_a_decision_refuses_a_get_request(self):
		"""Frappe checks the CSRF token only on POST, and the session cookie rides on a GET another site starts."""
		request = self.request()
		frappe.set_user(self.leader_user)
		frappe.local.request = frappe._dict(method="GET")
		frappe.local.form_dict = frappe._dict(request=request, approve="1")
		try:
			with self.assertRaises(frappe.PermissionError):
				execute_cmd("churchit.church_people.group_api.decide_join_request")
		finally:
			del frappe.local.request
			frappe.local.form_dict = frappe._dict()

		self.assertEqual(frappe.db.get_value("Group Join Request", request, "status"), "Requested")

	def test_a_full_group_refuses_a_join_and_an_approval(self):
		request = self.request()
		frappe.db.set_value("Group", self.group.name, "capacity", 2)

		frappe.set_user(self.leader_user)
		with self.assertRaises(frappe.ValidationError):
			decide_join_request(request, "1")

		frappe.set_user(self.outsider_user)
		with self.assertRaisesRegex(frappe.ValidationError, "full"):
			join_group(self.group.name)
		instant = self.make_group("_Test Join Full Group", capacity=2)
		with self.assertRaisesRegex(frappe.ValidationError, "full"):
			join_group(instant.name)
		self.assertNotIn(self.outsider, self.members(instant.name))

	def test_a_group_that_blocks_uncleared_members_refuses_the_approval(self):
		request = self.request()
		frappe.set_user("Administrator")
		check_type = ensure("Background Check Type", {"type": "_Test Join Safety Training"})
		group = frappe.get_doc("Group", self.group.name)
		group.update({"needs_background_check": 1, "checks_apply_to": "Everyone", "block_without_checks": 1})
		group.append("required_checks", {"check_type": check_type})
		group.save(ignore_permissions=True)

		frappe.set_user(self.leader_user)
		with self.assertRaisesRegex(frappe.ValidationError, "is missing _Test Join Safety Training"):
			decide_join_request(request, "1")

		self.assertNotIn(self.joiner, self.members(self.group.name))
		self.assertEqual(frappe.db.get_value("Group Join Request", request, "status"), "Requested")

	def test_a_group_past_its_close_date_refuses_a_join(self):
		closed = self.make_group("_Test Join Closed Group", close_enrollment_on=add_days(today(), -1))
		with self.assertRaisesRegex(frappe.ValidationError, "closed"):
			join_group(closed.name)
		with self.assertRaisesRegex(frappe.ValidationError, "closed"):
			join_group(
				self.make_group("_Test Join Closed Approval", requires_approval=1, status="Inactive").name
			)
		self.assertFalse(frappe.db.exists("Group Join Request", {"person": self.joiner}))

	def test_a_group_without_approval_still_joins_at_once(self):
		instant = self.make_group("_Test Join Instant Group")
		self.assertEqual(join_group(instant.name), {"joined": True, "group_name": "_Test Join Instant Group"})
		self.assertIn(self.joiner, self.members(instant.name))

	def test_the_picker_leaves_out_closed_groups_and_marks_a_request(self):
		full = self.make_group("_Test Join Picker Full", capacity=2)
		instant = self.make_group("_Test Join Picker Open")
		self.request()

		groups = {row.name: row for row in joinable_public_groups()}
		self.assertNotIn(full.name, groups)
		self.assertEqual(groups[instant.name].requested, False)
		self.assertEqual(groups[self.group.name].requested, True)
		self.assertEqual(groups[self.group.name].requires_approval, 1)

	def test_the_leader_page_gets_the_open_requests_of_each_group(self):
		request = self.request()
		quiet = self.make_group("_Test Join Quiet Group", requires_approval=1)

		requests = get_open_join_requests([self.group.name, quiet.name])
		self.assertEqual([row.name for row in requests[self.group.name]], [request])
		self.assertEqual(requests[self.group.name][0].person_name, "Joiner _Test Join")
		self.assertEqual(requests[quiet.name], [])

		html = frappe.render_template(
			"churchit/templates/includes/group_join_requests.html",
			{"group": self.group.name, "join_requests": requests},
		)
		self.assertIn("Joiner _Test Join", html)
		self.assertIn("I would like to come.", html)
		self.assertIn(f'data-request="{request}"', html)
		self.assertIn("decide_join_request", html)

	def test_a_member_cannot_read_a_request_even_their_own(self):
		request = self.request()
		self.assertFalse(frappe.has_permission("Group Join Request", "read", doc=request))
		frappe.set_user(self.outsider_user)
		self.assertFalse(frappe.has_permission("Group Join Request", "read", doc=request))

	def test_staff_cannot_make_a_request_in_the_desk(self):
		for role in ("Church Manager", "Church People Editor"):
			user = ensure_user(
				f"_test_join_{role.lower().replace(' ', '_')}@example.com", role, roles=(role,)
			)
			self.assertFalse(frappe.has_permission("Group Join Request", "create", user=user), role)

	def test_requests_are_scoped_to_their_church(self):
		request = self.request()
		frappe.set_user("Administrator")
		other_group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Join Other Church", "church": self.other_church}
		).insert(ignore_permissions=True)
		theirs = frappe.get_doc(
			{"doctype": "Group Join Request", "group": other_group.name, "person": self.outsider}
		).insert(ignore_permissions=True)
		manager = ensure_user(
			"_test_join_manager@example.com", "_Test Join Manager", roles=("Church Manager",)
		)
		make_person("_Test Join", "Manager", church=self.church, user=manager)

		self.assertEqual(theirs.church, self.other_church)
		assert_scoped(self, "Group Join Request", manager, request, theirs.name)

	def test_the_templates_patch_adds_a_missing_template_and_keeps_an_edited_one(self):
		frappe.set_user("Administrator")
		frappe.delete_doc("Email Template", "Group Join Decision", ignore_permissions=True)
		frappe.db.set_value("Email Template", "Group Join Request", "subject", "Ours")

		add_group_join_request_templates.execute()
		add_group_join_request_templates.execute()

		self.assertTrue(frappe.db.exists("Email Template", "Group Join Decision"))
		self.assertEqual(frappe.db.get_value("Email Template", "Group Join Request", "subject"), "Ours")

	def test_anonymizing_the_person_deletes_their_requests(self):
		request = self.request()
		frappe.set_user("Administrator")
		anonymize_person(self.joiner)
		self.assertFalse(frappe.db.exists("Group Join Request", request))
