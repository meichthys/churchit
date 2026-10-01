# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fixture helpers shared by the app's tests.

Tests run inside one transaction per test class, so records made by one test
are visible to the next. Helpers here either look up an existing record first
(``ensure``) or take names the caller keeps unique (``make_person``). A setUp
that saves the same email or phone every time needs ``RollbackEachTest``, since
an email or phone may be on one Person only.
"""

import csv
import io

import frappe
from frappe.tests.utils import FrappeTestCase


class RollbackEachTest(FrappeTestCase):
	"""Undoes each test's writes, so the next setUp starts from the same state."""

	def setUp(self):
		frappe.db.savepoint("rollback_each_test")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="rollback_each_test")


def ensure(doctype, filters, values=None):
	"""Return the name of the record matching *filters*, inserting it if missing."""
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	doc = frappe.get_doc({"doctype": doctype, **(values or filters)})
	return doc.insert(ignore_permissions=True).name


def ensure_user(email, first_name, roles=("Church User",)):
	"""Return *email* after making sure a User with the given roles exists."""
	if frappe.db.exists("User", email):
		return email
	user = frappe.new_doc("User")
	user.update({"email": email, "first_name": first_name})
	user.flags.no_welcome_mail = True
	for role in roles:
		user.append("roles", {"role": role})
	user.insert(ignore_permissions=True)
	return email


def make_person(first_name, last_name=None, **values):
	return frappe.get_doc(
		{"doctype": "Person", "first_name": first_name, "last_name": last_name, **values}
	).insert(ignore_permissions=True)


def make_function(function_name, **values):
	function_type = ensure("Function Type", {"type": "_Test Function Type"})
	return frappe.get_doc(
		{
			"doctype": "Function",
			"function_name": function_name,
			"type": function_type,
			"start_date": "2031-05-01",
			**values,
		}
	).insert(ignore_permissions=True)


def make_translation(case, abbreviation, rows, free=False):
	"""A Bible Translation ready to read, whose text is *rows* of (book, chapter, verse, text).

	The text is a real private CSV file, read by the same code as a church's own import. A free
	one is marked free straight in the database, so no download is queued. The file on disk and
	the cached text are removed when *case* finishes.
	"""
	from churchit import scripture

	content = io.StringIO()
	csv.writer(content).writerows([scripture.CSV_COLUMNS, *rows])
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.scrub(abbreviation)}.csv",
			"content": content.getvalue(),
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	case.addCleanup(frappe.delete_doc, "File", file.name, force=True, ignore_permissions=True)
	case.addCleanup(scripture.clear_cache, abbreviation)
	if frappe.db.exists("Bible Translation", abbreviation):
		frappe.delete_doc("Bible Translation", abbreviation, force=True, ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "Bible Translation",
			"abbreviation": abbreviation,
			"translation": f"{abbreviation} Test Version",
			"source": "User Import",
			"text_file": file.file_url,
		}
	).insert(ignore_permissions=True)
	if free:
		frappe.db.set_value(
			"Bible Translation", abbreviation, {"source": scripture.FREE_USE_BIBLE_API, "source_id": "_TEST"}
		)
	return abbreviation


def make_address(title, **values):
	return frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Personal",
			"address_line1": "1 Main St",
			"city": "Springfield",
			"country": "United States",
			**values,
		}
	).insert(ignore_permissions=True)


def ensure_root_church():
	"""Return the root Church, inserting a test one when the site has none."""
	from churchit.church_scope import root_church

	return root_church() or ensure(
		"Church", {"church_name": "_Test Church"}, {"church_name": "_Test Church", "abbreviation": "TC"}
	)


def set_multi_church(enabled):
	"""Flip the Church Features switch through a real save so its hooks run.

	Saving clears every cache, so a switch already in place is left unsaved.
	"""
	features = frappe.get_single("Church Features")
	if frappe.utils.cint(features.enable_multi_church) == int(bool(enabled)):
		return
	features.enable_multi_church = int(bool(enabled))
	features.save()
	frappe.clear_cache()


def set_private_people(private):
	"""Flip Keep People and Families Private through a real save so its setters follow."""
	features = frappe.get_single("Church Features")
	if frappe.utils.cint(features.private_people) == int(bool(private)):
		return
	features.private_people = int(bool(private))
	features.save()
	frappe.clear_cache()


def force_single_church():
	"""Switch multi-church off for a test whatever the site holds; rolled back with the transaction."""
	features = frappe.get_single("Church Features")
	if not frappe.utils.cint(features.enable_multi_church):
		return
	features.enable_multi_church = 0
	features.flags.ignore_validate = True
	features.save()
	frappe.clear_cache()


def make_branch(church_name, abbreviation, parent=None, **values):
	"""Return a branch Church under *parent* (the root by default), marking the parent a group."""
	parent = parent or ensure_root_church()
	if not frappe.db.get_value("Church", parent, "is_group"):
		frappe.db.set_value("Church", parent, "is_group", 1)
	return ensure(
		"Church",
		{"church_name": church_name},
		{"church_name": church_name, "abbreviation": abbreviation, "parent_church": parent, **values},
	)


def make_two_churches():
	"""Turn multi-church on and return (root, branch_a, branch_b) for a scoping test."""
	root = ensure_root_church()
	set_multi_church(True)
	return root, make_branch("_Test Scope A", "TSA"), make_branch("_Test Scope B", "TSB")


def assert_scoped(case, doctype, reader, mine, theirs, **list_args):
	"""Assert *reader* sees the record *mine* and never *theirs*, in lists and one by one.

	The one-line way to prove a new church-scoped doctype really is scoped::

	    root, a, b = make_two_churches()
	    assert_scoped(self, "Prayer Request", user_in_a, request_in_a, request_in_b)
	"""
	frappe.set_user(reader)
	try:
		visible = frappe.get_list(doctype, pluck="name", **list_args)
		case.assertIn(mine, visible, f"{reader} cannot see their own {doctype}")
		case.assertNotIn(theirs, visible, f"{doctype} from another church is listed for {reader}")
		case.assertTrue(frappe.has_permission(doctype, "read", doc=mine))
		case.assertFalse(
			frappe.has_permission(doctype, "read", doc=theirs),
			f"{reader} can open another church's {doctype}",
		)
	finally:
		frappe.set_user("Administrator")
