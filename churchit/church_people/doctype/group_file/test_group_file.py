# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.web_form.web_form import accept

from churchit.church_people.member_access import make_group_files_private
from churchit.church_people.web_form.group_files import group_files as group_files_form
from churchit.patches.v1_0 import add_group_files_menu_item
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
)


def make_member(email, first_name):
	user = ensure_user(email, first_name)
	return user, make_person(first_name, "File Tester", user=user).name


def make_group(group_name, members=(), **values):
	group = frappe.get_doc({"doctype": "Group", "group_name": group_name, **values})
	for person, role in members:
		group.append("members", {"person": person, "group_role": role})
	return group.insert(ignore_permissions=True).name


def upload(case, file_name):
	"""A private file uploaded with no document yet, the way the web form uploads one."""
	file = frappe.get_doc(
		{"doctype": "File", "file_name": file_name, "content": file_name.encode(), "is_private": 1}
	).insert()
	add_cleanup = case.addClassCleanup if isinstance(case, type) else case.addCleanup
	add_cleanup(frappe.delete_doc, "File", file.name, force=True, ignore_permissions=True)
	return file


class TestGroupFile(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		leader_role = ensure(
			"Group Role", {"role": "_Test File Leader"}, {"role": "_Test File Leader", "is_leader": 1}
		)
		member_role = ensure(
			"Group Role", {"role": "_Test File Member"}, {"role": "_Test File Member", "is_leader": 0}
		)
		cls.leader, leader_person = make_member("_test_file_leader@example.com", "_Test Leader")
		cls.member, member_person = make_member("_test_file_member@example.com", "_Test Member")
		cls.outsider, outsider_person = make_member("_test_file_outsider@example.com", "_Test Outsider")
		cls.staff = ensure_user("_test_file_staff@example.com", "_Test Staff", roles=("Church Staff",))
		cls.group = make_group(
			"_Test File Group", members=[(leader_person, leader_role), (member_person, member_role)]
		)
		cls.other_group = make_group("_Test File Other Group", members=[(outsider_person, member_role)])

		file = upload(cls, "_test_group_notes.txt")
		cls.group_file = cls.make_group_file(cls.group, file.file_url)
		cls.file = frappe.db.get_value(
			"File", {"attached_to_doctype": "Group File", "attached_to_name": cls.group_file}, "name"
		)
		cls.other_file = cls.make_group_file(cls.other_group, "https://example.com/_test_other.pdf")

	@staticmethod
	def make_group_file(group, url):
		return (
			frappe.get_doc(
				{"doctype": "Group File", "group": group, "title": "_Test Notes", "attached_file": url}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def is_downloadable(self, user):
		frappe.set_user(user)
		return frappe.get_doc("File", self.file).is_downloadable()

	def test_the_upload_is_attached_and_private(self):
		self.assertTrue(self.file)
		self.assertEqual(frappe.db.get_value("File", self.file, "is_private"), 1)

	def test_a_member_of_the_group_can_download_the_file(self):
		self.assertTrue(self.is_downloadable(self.member))

	def test_a_signed_in_non_member_cannot_download_the_file(self):
		self.assertFalse(self.is_downloadable(self.outsider))

	def test_a_member_lists_only_the_files_of_their_groups(self):
		frappe.set_user(self.member)
		listed = frappe.get_list("Group File", pluck="name")
		self.assertIn(self.group_file, listed)
		self.assertNotIn(self.other_file, listed)
		self.assertFalse(frappe.has_permission("Group File", "read", doc=self.other_file))

		frappe.set_user(self.outsider)
		self.assertEqual(frappe.get_list("Group File", pluck="name"), [self.other_file])

	def test_staff_read_every_group_file(self):
		frappe.set_user(self.staff)
		self.assertTrue(
			{self.group_file, self.other_file} <= set(frappe.get_list("Group File", pluck="name"))
		)
		self.assertTrue(self.is_downloadable(self.staff))

	def form_data(self, file_url, group=None, title="_Test Upload"):
		return json.dumps(
			{"doctype": "Group File", "group": group or self.group, "title": title, "attached_file": file_url}
		)

	def test_a_member_who_does_not_lead_the_group_cannot_add_a_file(self):
		frappe.set_user(self.member)
		file = upload(self, "_test_member_upload.txt")

		with self.assertRaises(frappe.PermissionError):
			accept("group-files", self.form_data(file.file_url))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(json.loads(self.form_data(file.file_url))).insert()
		self.assertFalse(frappe.db.exists("Group File", {"title": "_Test Upload"}))

	def test_a_member_cannot_add_a_file_to_a_group_they_are_not_in(self):
		frappe.set_user(self.leader)
		file = upload(self, "_test_other_upload.txt")

		with self.assertRaises(frappe.PermissionError):
			accept("group-files", self.form_data(file.file_url, group=self.other_group))

	def test_a_leader_cannot_attach_a_private_file_they_cannot_open(self):
		staff_file = upload(self, "_test_staff_only.txt")
		frappe.set_user(self.leader)

		with self.assertRaises(frappe.PermissionError):
			accept("group-files", self.form_data(staff_file.file_url, title="_Test Taken"))

		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Group File", {"title": "_Test Taken"}))
		self.assertIsNone(frappe.db.get_value("File", staff_file.name, "attached_to_name"))

	def test_a_leader_adds_a_file_through_the_web_form(self):
		frappe.set_user(self.leader)
		file = upload(self, "_test_leader_upload.txt")

		group_file = accept("group-files", self.form_data(file.file_url, title="_Test Leader Upload"))
		self.addCleanup(frappe.delete_doc, "Group File", group_file.name, force=True, ignore_permissions=True)

		frappe.set_user("Administrator")
		attached = frappe.get_doc("File", file.name)
		self.assertEqual(
			(attached.attached_to_doctype, attached.attached_to_name), ("Group File", group_file.name)
		)
		self.assertTrue(attached.is_private)
		frappe.set_user(self.member)
		self.assertTrue(attached.is_downloadable())

	def test_a_public_file_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "private"):
			frappe.get_doc(
				{
					"doctype": "Group File",
					"group": self.group,
					"title": "_Test Public",
					"attached_file": "/files/x.txt",
				}
			).insert(ignore_permissions=True)

	def test_a_public_attachment_to_a_group_file_is_refused(self):
		public = frappe.get_doc({"doctype": "File", "attached_to_doctype": "Group File", "is_private": 0})
		with self.assertRaisesRegex(frappe.ValidationError, "private"):
			make_group_files_private(public)

		make_group_files_private(
			frappe.get_doc({"doctype": "File", "attached_to_doctype": "Group File", "is_private": 1})
		)
		make_group_files_private(
			frappe.get_doc({"doctype": "File", "attached_to_doctype": "Group", "is_private": 0})
		)

	def form_context(self, user, reference_doc=None):
		frappe.set_user(user)
		field = frappe._dict(fieldname="group", fieldtype="Link", options="")
		context = frappe._dict(
			web_form_doc=frappe._dict(web_form_fields=[field]), reference_doc=reference_doc
		)
		group_files_form.get_context(context)
		return context, field

	def group_options(self, user):
		_context, field = self.form_context(user)
		return [option["value"] for option in json.loads(field.options)]

	def test_the_form_offers_a_new_file_only_the_groups_the_member_leads(self):
		self.assertEqual(self.group_options(self.leader), [self.group])
		self.assertEqual(self.group_options(self.member), [])
		self.assertEqual(self.group_options("Guest"), [])

	def test_the_list_offers_new_only_to_a_leader(self):
		self.assertTrue(self.form_context(self.leader)[0].allow_multiple)
		self.assertFalse(self.form_context(self.member)[0].allow_multiple)

	def test_a_saved_file_shows_the_group_name(self):
		_context, field = self.form_context(self.member, reference_doc={"name": self.group_file})
		self.assertEqual((field.fieldname, field.fieldtype), ("group_name", "Data"))


class TestGroupFileChurches(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch_a, branch_b = make_two_churches()
		cls.manager_a = ensure_user(
			"_test_file_manager_a@example.com", "_Test File A", roles=("Church Manager",)
		)
		make_person("_Test File A", "Manager", church=branch_a, user=cls.manager_a)
		cls.group_a = make_group("_Test File Group A", church=branch_a)
		cls.group_b = make_group("_Test File Group B", church=branch_b)
		cls.file_a = TestGroupFile.make_group_file(cls.group_a, "https://example.com/_test_a.pdf")
		cls.file_b = TestGroupFile.make_group_file(cls.group_b, "https://example.com/_test_b.pdf")
		cls.addClassCleanup(frappe.clear_cache)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_manager_sees_only_their_churchs_group_files(self):
		assert_scoped(self, "Group File", self.manager_a, self.file_a, self.file_b)

	def test_the_file_takes_its_groups_church(self):
		self.assertEqual(
			frappe.db.get_value("Group File", self.file_a, "church"),
			frappe.db.get_value("Group", self.group_a, "church"),
		)

	def test_a_manager_cannot_add_a_file_to_another_churchs_group(self):
		frappe.set_user(self.manager_a)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Group File",
					"group": self.group_b,
					"title": "_Test Cross",
					"attached_file": "https://example.com/_test_cross.pdf",
				}
			).insert()


class TestGroupFilesMenu(RollbackEachTest):
	def test_the_menu_row_patch_adds_group_files_once(self):
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != add_group_files_menu_item.ROUTE]
		settings.save(ignore_permissions=True)

		add_group_files_menu_item.execute()
		add_group_files_menu_item.execute()

		rows = [
			row
			for row in frappe.get_doc("Portal Settings").menu
			if row.route == add_group_files_menu_item.ROUTE
		]
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].title, rows[0].role), ("Group Files", "Church User"))
