# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate, getdate
from frappe.utils.print_format import download_pdf as download_print_pdf

from churchit.church_communications.doctype.bulletin.sections import BulletinSections
from churchit.church_missions.doctype.missionary_status.missionary_status import INACTIVE
from churchit.church_prayers.prayer_access import WHOLE_CHURCH, get_open_request_filters
from churchit.church_scope import church_filters, has_church_access, refuse_another_churches_parent
from churchit.scripture import format_reference

PRINT_FORMAT = "Bulletin"

SECTION_FIELDS = (
	"show_contact_information",
	"show_order_of_worship",
	"show_church_roles",
	"show_upcoming_functions",
	"show_ministries",
	"show_church_verse",
	"show_church_image",
	"show_missionary",
	"show_prayer_requests",
	"show_birthdays",
	"show_anniversaries",
	"show_sermon_handout",
)


class Bulletin(BulletinSections, Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "function", _("{0} belongs to another church, so only that church can make its bulletin.")
		)
		self.title = f"{self.function_name} ({formatdate(self.function_date)})"
		self.verse = format_reference(self.verse)
		self.validate_missionary_is_printable()
		self.validate_prayer_requests_are_printable()
		self.validate_shared_announcements()

	def validate_missionary_is_printable(self):
		if not self.missionary or self.settings.include_sensitive_missionaries:
			return
		if frappe.db.get_value("Missionary", self.missionary, "sensitive"):
			frappe.throw(
				_(
					"{0} is marked sensitive. Turn on Include Sensitive Missionaries in "
					"Bulletin Settings to feature them in a bulletin."
				).format(frappe.bold(self.featured_missionary.title))
			)

	def validate_prayer_requests_are_printable(self):
		for row in self.prayer_requests:
			visibility, approved = frappe.db.get_value(
				"Prayer Request", row.prayer_request, ["visibility", "approved_for_list"]
			)
			if visibility != WHOLE_CHURCH:
				frappe.throw(
					_("{0} is not shared with the whole church and cannot be printed.").format(
						frappe.bold(row.title)
					)
				)
			if not approved:
				frappe.throw(
					_("{0} is not approved for the prayer list and cannot be printed.").format(
						frappe.bold(row.title)
					)
				)

	def validate_shared_announcements(self):
		"""Keep shared announcements public: a link to a private file is refused."""
		if self.share_announcements and "/private/files/" in (self.announcements or ""):
			frappe.throw(
				_(
					"The announcements link to a private file, which visitors to the website cannot open. "
					"Remove it and add the image again, or untick Show Announcements on the Website."
				)
			)

	def has_website_permission(self, ptype, user, verbose=False):
		"""Signed-in portal users may read, and so download, the published bulletins of their own church."""
		return (
			ptype == "read"
			and bool(self.publish)
			and user != "Guest"
			and has_church_access(user, self.church)
		)

	def apply_defaults(self):
		"""Switch on the sections Bulletin Settings prefers, and pick this week's missionary and prayer requests."""
		for field in SECTION_FIELDS:
			self.set(field, self.settings.get(field))
		if not self.function:
			return
		self.function_date, church = frappe.db.get_value("Function", self.function, ["start_date", "church"])
		self.missionary = missionary_of_the_week(
			self.function_date, self.settings.include_sensitive_missionaries, church
		)
		self.set("prayer_requests", open_prayer_requests(church))


def missionary_of_the_week(on_date, include_sensitive=False, church=None):
	"""Rotate week by week, in title order, through the missionaries supported on *on_date*."""
	supported = supported_missionaries(on_date, include_sensitive, church)
	if not supported:
		return None
	return supported[getdate(on_date).toordinal() // 7 % len(supported)]


def supported_missionaries(on_date, include_sensitive=False, church=None):
	"""Names of the missionaries who are not Inactive and whose support has not ended by *on_date*, in title order."""
	filters = church_filters(church, status=["!=", INACTIVE])
	if not include_sensitive:
		filters["sensitive"] = 0
	return frappe.get_all(
		"Missionary",
		filters=filters,
		or_filters=[["support_end_date", "is", "not set"], ["support_end_date", ">=", on_date]],
		order_by="title asc",
		pluck="name",
	)


def open_prayer_requests(church=None):
	"""Rows for every open Whole Church request approved for the list, urgent ones first."""
	filters, or_filters = get_open_request_filters()
	return frappe.get_all(
		"Prayer Request",
		filters=church_filters(church, visibility=WHOLE_CHURCH, **filters),
		or_filters=or_filters,
		fields=["name as prayer_request", "title", "recipient_name"],
		order_by="urgent desc, creation desc",
	)


@frappe.whitelist()
def get_defaults(function: str | None = None):
	"""A new bulletin's sections, missionary and prayer requests, for the form to fill in before the first save."""
	frappe.has_permission("Bulletin", "write", throw=True)
	if function:
		# The defaults are read from the function's church, so the caller must be able to see it.
		frappe.has_permission("Function", doc=function, throw=True)
	bulletin = frappe.new_doc("Bulletin")
	bulletin.function = function
	bulletin.apply_defaults()
	values = {field: bulletin.get(field) for field in (*SECTION_FIELDS, "missionary")}
	values["prayer_requests"] = [
		{"prayer_request": row.prayer_request, "title": row.title, "recipient_name": row.recipient_name}
		for row in bulletin.prayer_requests
	]
	return values


@frappe.whitelist()
def download_pdf(name: str):
	"""The bulletin as a PDF named after its date, for the portal."""
	download_print_pdf("Bulletin", name, format=PRINT_FORMAT, no_letterhead=1)
	function_date = frappe.db.get_value("Bulletin", name, "function_date")
	frappe.local.response.filename = f"Bulletin {formatdate(function_date, 'yyyy-MM-dd')}.pdf"
