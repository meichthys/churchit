# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import socket

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_ministries.doctype.function_check_in.function_check_in import VOLUNTEER
from churchit.church_ministries.page.check_in.team import get_position

ZPL_METHODS = ("Zebra Browser Print", "QZ Tray", "Network Printer")
# What a per-church row may override. The print formats stay site-wide: they are
# the tag's design, not the hardware it comes out of.
PRINTER_FIELDS = (
	"name_tag_printing",
	"printer_name",
	"printer_host",
	"printer_port",
	"label_width",
	"label_height",
	"label_dpi",
)
VOLUNTEER_NAME_TAG = "Volunteer Name Tag"


class CheckInSettings(Document):
	"""Name tag rendering and delivery for the Check-In Station."""

	def validate(self):
		if (self.label_width or 0) <= 0 or (self.label_height or 0) <= 0:
			frappe.throw(_("Label width and height must be greater than zero."))
		for formats in [self, *self.tag_formats]:
			self.validate_print_format(formats.name_tag_format, raw=False)
			self.validate_print_format(formats.zpl_format, raw=True)
		kinds = [row.check_in_kind for row in self.tag_formats]
		if len(kinds) != len(set(kinds)):
			frappe.throw(_("Add one Tag Formats by Kind row for each kind."))

	def for_church(self, church=None):
		"""These settings with *church*'s printer row applied, or unchanged when it has none.

		Each campus has its own label printer, so one host and one printer name
		cannot serve them all. Resolved into a copy rather than threaded through
		every caller, so the print format template and the network path read one
		consistent set.
		"""
		row = next((row for row in self.printers if row.church == church), None) if church else None
		if not row:
			return self

		settings = frappe.get_doc({"doctype": self.doctype, **self.as_dict()})
		settings.update({field: row.get(field) for field in PRINTER_FIELDS if row.get(field)})
		return settings

	def validate_print_format(self, name, raw):
		if not name:
			return
		print_format = frappe.get_doc("Print Format", name)
		if print_format.doc_type != "Function Check-In":
			frappe.throw(_("Print Format {0} must be for Function Check-In.").format(frappe.bold(name)))
		if bool(print_format.raw_printing) != raw:
			expected = _("a raw (ZPL) format") if raw else _("an HTML format")
			frappe.throw(_("Print Format {0} must be {1}.").format(frappe.bold(name), expected))

	@property
	def is_zpl(self):
		return self.name_tag_printing in ZPL_METHODS

	@property
	def template(self):
		"""Jinja source of the default print format the current printing method needs."""
		return self.get_template()

	def get_template(self, kind: str | None = None) -> str:
		"""Jinja source of *kind*'s print format for the current printing method, else the default one."""
		field = "zpl_format" if self.is_zpl else "name_tag_format"
		row = next((row for row in self.tag_formats if row.check_in_kind == kind and row.get(field)), None)
		name = (row or self).get(field)
		if not name:
			frappe.throw(_("Choose a name tag Print Format in Check-In Settings."))
		print_format = frappe.get_doc("Print Format", name)
		return print_format.raw_commands if self.is_zpl else print_format.html

	def print_name_tags(self, check_ins):
		"""Render a tag per check-in (plus pickup tags) and hand them to the printer path."""
		content = self.render_name_tags(check_ins)
		result = {"method": self.name_tag_printing, "count": len(check_ins)}
		if self.name_tag_printing == "Network Printer":
			self.send_to_network_printer(content)
			result["printed"] = True
		else:
			result.update(content=content, printer_name=self.printer_name)
		return result

	def render_name_tags(self, check_ins):
		"""One tag per check-in in the format of its kind, then the pickup tags in the default format.

		A volunteer's tag gets their position here, so the template reads no assignment.
		"""
		templates = {kind: self.get_template(kind) for kind in {doc.check_in_kind for doc in check_ins}}
		labels = []
		for doc in check_ins:
			context = {"settings": self, "doc": doc}
			if doc.check_in_kind == VOLUNTEER:
				context["position"] = get_position(doc.person, doc.function)
			# The template is a Print Format, rendered in Frappe's sandbox as Frappe renders print formats.
			# nosemgrep: frappe-ssti
			labels.append(frappe.render_template(templates[doc.check_in_kind], context))
		for doc, names in self.pickup_groups(check_ins):
			context = {"settings": self, "doc": doc, "pickup_names": names}
			# nosemgrep: frappe-ssti
			labels.append(frappe.render_template(self.template, context))
		if self.is_zpl:
			return "\n".join(labels)
		return (
			'<!doctype html><html><head><meta charset="utf-8"><style>body { margin: 0; }</style></head>'
			f'<body>{"".join(labels)}</body></html>'
		)

	def pickup_groups(self, check_ins):
		"""One (first check-in, names the people go by) pair per security code in the batch."""
		if not self.security_codes:
			return []
		groups = {}
		for doc in check_ins:
			if doc.security_code:
				groups.setdefault(doc.security_code, []).append(doc)
		return [(docs[0], [name_gone_by(doc.person) for doc in docs]) for docs in groups.values()]

	def send_to_network_printer(self, zpl):
		host, port = self.printer_host, self.printer_port or 9100
		try:
			with socket.create_connection((host, port), timeout=5) as connection:
				connection.sendall(zpl.encode("utf-8"))
		except OSError as error:
			frappe.throw(_("Could not reach printer {0}:{1} ({2}).").format(host, port, str(error)))


def add_volunteer_tag_format() -> None:
	"""Print Volunteer check-ins with the Volunteer Name Tag, unless a Volunteer row is already there."""
	settings = frappe.get_single("Check-In Settings")
	if any(row.check_in_kind == VOLUNTEER for row in settings.tag_formats):
		return
	settings.append("tag_formats", {"check_in_kind": VOLUNTEER, "name_tag_format": VOLUNTEER_NAME_TAG})
	settings.save(ignore_permissions=True)


def name_gone_by(person: str) -> str:
	"""*person*'s nickname, else their first name, as their name tag prints it."""
	first_name, nickname = frappe.db.get_value("Person", person, ["first_name", "nickname"])
	return nickname or first_name
