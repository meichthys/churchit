# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import socket

import frappe
from frappe import _
from frappe.model.document import Document

ZPL_METHODS = ("Zebra Browser Print", "QZ Tray", "Network Printer")


class CheckInSettings(Document):
	"""Name tag rendering and delivery for the Check-In Station."""

	def validate(self):
		if (self.label_width or 0) <= 0 or (self.label_height or 0) <= 0:
			frappe.throw(_("Label width and height must be greater than zero."))
		self.validate_print_format(self.name_tag_format, raw=False)
		self.validate_print_format(self.zpl_format, raw=True)

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
		"""Jinja source of the print format the current printing method needs."""
		name = self.zpl_format if self.is_zpl else self.name_tag_format
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
		template = self.template
		context = {"settings": self}
		labels = [frappe.render_template(template, {**context, "doc": doc}) for doc in check_ins]
		for doc, names in self.pickup_groups(check_ins):
			labels.append(frappe.render_template(template, {**context, "doc": doc, "pickup_names": names}))
		if self.is_zpl:
			return "\n".join(labels)
		return (
			'<!doctype html><html><head><meta charset="utf-8"><style>body { margin: 0; }</style></head>'
			f'<body>{"".join(labels)}</body></html>'
		)

	def pickup_groups(self, check_ins):
		"""One (first check-in, first names) pair per security code in the batch."""
		if not self.security_codes:
			return []
		groups = {}
		for doc in check_ins:
			if doc.security_code:
				groups.setdefault(doc.security_code, []).append(doc)
		return [
			(docs[0], [frappe.db.get_value("Person", d.person, "first_name") for d in docs])
			for docs in groups.values()
		]

	def send_to_network_printer(self, zpl):
		host, port = self.printer_host, self.printer_port or 9100
		try:
			with socket.create_connection((host, port), timeout=5) as connection:
				connection.sendall(zpl.encode("utf-8"))
		except OSError as error:
			frappe.throw(_("Could not reach printer {0}:{1} ({2}).").format(host, port, error))
