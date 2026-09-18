# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate, getdate, now_datetime
from frappe.utils.print_format import download_pdf as download_print_pdf

from churchit.church_communications.doctype.bulletin.sections import BulletinSections
from churchit.church_prayers.doctype.prayer_request.prayer_request import CLOSED_STATUSES

PRINT_FORMAT = "Bulletin"

SECTION_FIELDS = (
	"show_contact_information",
	"show_order_of_worship",
	"show_church_roles",
	"show_upcoming_functions",
	"show_ministries",
	"show_church_verse",
	"show_missionary",
	"show_prayer_requests",
	"show_birthdays",
	"show_anniversaries",
	"show_sermon_handout",
)


class Bulletin(BulletinSections, Document):
	def validate(self):
		self.title = f"{self.function_name} ({formatdate(self.function_date)})"
		self.validate_missionary_is_printable()
		self.validate_prayer_requests_are_printable()

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
			if frappe.db.get_value("Prayer Request", row.prayer_request, "is_private"):
				frappe.throw(
					_("{0} is a private prayer request and cannot be printed.").format(frappe.bold(row.title))
				)

	def has_website_permission(self, ptype, user, verbose=False):
		"""Signed-in portal users may read, and so download, published bulletins."""
		return ptype == "read" and bool(self.publish) and user != "Guest"

	def apply_defaults(self):
		"""Switch on the sections Bulletin Settings prefers, and pick this week's missionary and prayer requests."""
		for field in SECTION_FIELDS:
			self.set(field, self.settings.get(field))
		if not self.function:
			return
		self.function_date = frappe.db.get_value("Function", self.function, "start_date")
		self.missionary = missionary_of_the_week(
			self.function_date, self.settings.include_sensitive_missionaries
		)
		self.set("prayer_requests", open_prayer_requests())


def missionary_of_the_week(on_date, include_sensitive=False):
	"""Rotate week by week, in title order, through the missionaries supported on *on_date*."""
	supported = supported_missionaries(on_date, include_sensitive)
	if not supported:
		return None
	return supported[getdate(on_date).toordinal() // 7 % len(supported)]


def supported_missionaries(on_date, include_sensitive=False):
	"""Names of the missionaries whose support has not ended by *on_date*, in title order."""
	return frappe.get_all(
		"Missionary",
		filters={} if include_sensitive else {"sensitive": 0},
		or_filters=[["support_end_date", "is", "not set"], ["support_end_date", ">=", on_date]],
		order_by="title asc",
		pluck="name",
	)


def open_prayer_requests():
	"""Rows for every request that is neither private, closed, nor past its end date, urgent ones first."""
	return frappe.get_all(
		"Prayer Request",
		filters={"is_private": 0, "status": ("not in", CLOSED_STATUSES)},
		or_filters=[["end_date", "is", "not set"], ["end_date", ">=", now_datetime()]],
		fields=["name as prayer_request", "title", "recipient_name"],
		order_by="urgent desc, creation desc",
	)


@frappe.whitelist()
def get_defaults(function=None):
	"""A new bulletin's sections, missionary and prayer requests, for the form to fill in before the first save."""
	frappe.has_permission("Bulletin", "write", throw=True)
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
def download_pdf(name):
	"""The bulletin as a PDF named after its date, for the portal."""
	download_print_pdf("Bulletin", name, format=PRINT_FORMAT, no_letterhead=1)
	function_date = frappe.db.get_value("Bulletin", name, "function_date")
	frappe.local.response.filename = f"Bulletin {formatdate(function_date, 'yyyy-MM-dd')}.pdf"
