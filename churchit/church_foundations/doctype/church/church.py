# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet, NestedSetMultipleRootsError, get_ancestors_of

from churchit.church_foundations import church_access
from churchit.church_scope import (
	document_church,
	is_multi_church,
	requested_church,
	root_church,
	session_church,
)

ADDRESS_FIELDS = ["address_title", "address_line1", "address_line2", "city", "state", "pincode", "country"]


class Church(NestedSet):
	nsm_parent_field = "parent_church"
	allow_root_deletion = False

	def validate(self):
		if not is_multi_church():
			self.validate_single_church()
			return
		self.validate_single_root()
		self.validate_parent_is_group()

	def validate_single_church(self):
		"""Refuse a second church while the switch is off; existing records stay editable."""
		existing = frappe.db.get_value("Church", {"name": ("!=", self.name)}, "name")
		if self.is_new() and existing:
			frappe.throw(
				_(
					"Only one Church record is allowed. "
					"Enable Multi-Church in Church Features to add branches."
				)
			)

	def validate_single_root(self):
		other_root = frappe.db.exists(
			"Church", {"parent_church": ("is", "not set"), "name": ("!=", self.name)}
		)
		if not self.parent_church and other_root:
			frappe.throw(
				_("{0} is already the main church; give this one a parent church.").format(other_root),
				NestedSetMultipleRootsError,
			)

	def on_trash(self):
		"""Move everyone scoped to this church up to its parent as the tree forgets it.

		The parent is read first: ``NestedSet.on_trash`` refuses the root and a
		church that still has branches, and clears ``parent_church`` as it goes.
		"""
		parent = self.parent_church
		super().on_trash()
		church_access.move_church_permissions(self.name, parent)

	def validate_parent_is_group(self):
		if self.parent_church and not frappe.db.get_value("Church", self.parent_church, "is_group"):
			frappe.throw(
				_("Check Is Group on {0} before adding branches under it.").format(self.parent_church)
			)


def get_church():
	"""The church a page is about: the ?church= selection, else the visitor's own, else the root."""
	name = selected_church_name()
	return frappe.get_cached_doc("Church", name) if name else None


def selected_church_name():
	"""Resolve the church name for the current request; None before setup creates one.

	An unknown or unpublished ``?church=`` falls back to the main church rather
	than failing, since the navbar and footer resolve it on every page.
	"""
	if not is_multi_church():
		return root_church()
	return requested_church() or session_church() or root_church()


def get_church_address(church=None):
	"""Return the Church's linked Address as a dict of its postal fields, or None when none is linked."""
	church = church or get_church()
	if not church or not church.address:
		return None
	return frappe.db.get_value("Address", church.address, ADDRESS_FIELDS, as_dict=True)


def address_line(address):
	"""Join the street, city, state and postal code into one comma-separated line."""
	if not address:
		return None
	region = " ".join(filter(None, [address.state, address.pincode]))
	return ", ".join(filter(None, [address.address_line1, address.address_line2, address.city, region]))


def church_of(doc=None):
	"""The church a document belongs to, for printing it or writing to its people.

	The document's own church, a child row's through its parent, and for a
	doctype that carries none, or a record shared with every church, the church
	the reader is in.
	"""
	return (doc and document_church(doc)) or selected_church_name()


def church_name(doc=None):
	"""The name of the church a document belongs to, as a notification signs itself.

	Exposed to templates through the ``jinja`` hook: a greeting to a branch's
	member is signed by that branch, not by the main church.
	"""
	church = church_of(doc)
	return frappe.db.get_value("Church", church, "church_name") if church else None


def get_letterhead_church(doc=None):
	"""Name and one-line contact details for a printed letterhead, or None before setup.

	Takes the church of the document being printed, so a branch's statement
	carries its own name; print rendering passes that document in.
	"""
	name = church_of(doc)
	church = frappe.get_cached_doc("Church", name) if name else None
	if not church:
		return None
	details = church_contact_details(church)
	contact = [address_line(get_church_address(church)), details.phone, details.email]
	return frappe._dict(name=church.church_name, contact=" · ".join(filter(None, contact)))


def church_contact_details(church=None):
	"""A church's phone and email, falling back to the site-wide Contact Us Settings.

	Contact Us Settings holds one number for the whole site, so a branch that
	fills in its own is the one the website and its letterhead should show.
	"""
	church = church or get_church()
	return frappe._dict(
		phone=(church and church.get("phone")) or frappe.db.get_single_value("Contact Us Settings", "phone"),
		email=(church and church.get("email"))
		or frappe.db.get_single_value("Contact Us Settings", "email_id"),
	)


def inherited_value(church, fieldname):
	"""The church's own value for `fieldname`, else the nearest ancestor's."""
	value = frappe.db.get_value("Church", church, fieldname)
	if value:
		return value
	for ancestor in get_ancestors_of("Church", church):
		value = frappe.db.get_value("Church", ancestor, fieldname)
		if value:
			return value
	return None


@frappe.whitelist()
def get_default_bible_translation():
	"""The default Bible translation of the caller's church, inherited from its ancestors."""
	church = get_church()
	return inherited_value(church.name, "default_bible_translation") if church else None
