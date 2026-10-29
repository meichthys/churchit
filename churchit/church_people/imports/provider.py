# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What every people import source shares: its Data Import provider and its virtual DocType."""

import frappe
from frappe import _
from frappe.core.doctype.data_import.import_provider import ImportProvider
from frappe.core.doctype.data_import.importer import ACTION_INSERT, ACTION_UPDATE, INSERT, UPDATE
from frappe.model.document import Document
from frappe.utils import escape_html, validate_email_address, validate_phone_number

from churchit.church_people.imports.record import ImportedPerson, get_imported_people


class SourceProvider(ImportProvider):
	"""A Data Import provider that reads one source's rows into people.

	The virtual DocType's own fields are the import columns, so Data Import matches, maps and downloads
	them from its meta. A subclass names its `system` and reads a row in `to_record`.

	Insert New Records adds people and refuses a row imported before. Update Existing Records only updates
	people imported before. Insert or Update Records does whichever the row needs.
	"""

	system: str = ""

	def to_record(self, row: dict) -> ImportedPerson:
		raise NotImplementedError

	def import_row(self, importer, doc):
		record = self.to_record(doc)
		if record.household:
			record.household.address = self.get_household_addresses(importer.import_file).get(
				record.household.legacy_id
			)
		person = get_imported_people({record.key}).get(record.key) if record.legacy_id else None
		if message := get_mode_refusal(person, importer.import_type):
			frappe.throw(message)
		if person:
			return record.update_person(person, importer.data_import.name), ACTION_UPDATE
		return record.insert_person(importer.data_import.name), ACTION_INSERT

	def get_records(self, import_file) -> list[tuple[int, ImportedPerson]]:
		"""(row number, record) for each row of *import_file* that is not blank."""
		return [
			(row.row_number, self.to_record(doc))
			for row in import_file.data
			if (doc := row.parse_doc(self.doctype))
		]

	def get_household_addresses(self, import_file) -> dict[str, dict]:
		"""{household ID: its address}: its primary contact's in the file, else its first member's, so the
		order of the rows does not matter. Worked out once per import."""
		if "household_addresses" not in self.__dict__:
			members = {}
			for _row, record in self.get_records(import_file):
				if record.household and record.address:
					members.setdefault(record.household.legacy_id, []).append(record)
			self.household_addresses = {
				household: next((m for m in records if m.household.may_lead), records[0]).address
				for household, records in members.items()
			}
		return self.household_addresses

	def validate(self, import_file) -> list[dict]:
		records = self.get_records(import_file)
		imported = get_imported_people({record.key for _row, record in records if record.legacy_id})
		first_rows = {}
		warnings = []
		for row, record in records:
			if record.legacy_id and record.key in first_rows:
				warnings.append(
					{
						"row": row,
						"message": _("This person is also on row {0}.").format(first_rows[record.key]),
					}
				)
				continue
			first_rows[record.key] = row
			warnings += get_row_warnings(row, record, imported.get(record.key), import_file.import_type)
		return warnings


def get_row_warnings(row: int, record: ImportedPerson, person: str | None, import_type: str) -> list[dict]:
	"""What the preview says about one row: a warning that blocks it when it cannot be imported, else notes."""
	if not record.values.get("first_name"):
		return [{"row": row, "message": _("This row has no first name.")}]
	if message := get_mode_refusal(person, import_type):
		return [{"row": row, "message": message}]
	if record.address and not record.address.get("country"):
		return [
			{
				"row": row,
				"message": _(
					"The address has no country that Churchit knows. Correct the country, or set the site's country in System Settings."
				),
			}
		]
	notes = [_("Updates {0}.").format(person)] if person else []
	notes += [
		_("{0} is not a valid email address. It is left out.").format(escape_html(email))
		for email, _kind in record.emails
		if not validate_email_address(email)
	]
	notes += [
		_("{0} is not a valid phone number. It is left out.").format(escape_html(phone))
		for phone, _kind in record.phones
		if not validate_phone_number(phone)
	]
	return [{"row": row, "message": note, "type": "info"} for note in notes]


def get_mode_refusal(person: str | None, import_type: str) -> str | None:
	"""Why the import type refuses a row that matches *person*, or one that matches no one."""
	if person and import_type == INSERT:
		return _(
			"Already imported as {0}. Choose Insert or Update Records to update the people imported before, or skip this row."
		).format(person)
	if not person and import_type == UPDATE:
		return _("No one was imported with this ID, so there is no one to update.")
	return None


class ImportTarget(Document):
	"""A virtual DocType that names an import source for Data Import. It stores nothing.

	Data Import's log links each imported row to this DocType under the Person's name, so a Person's name
	loads as an empty record that the form script forwards to the Person.
	"""

	@staticmethod
	def get_list(**kwargs) -> list:
		return []

	@staticmethod
	def get_count(**kwargs) -> int:
		return 0

	@staticmethod
	def get_stats(**kwargs) -> dict:
		return {}

	def load_from_db(self):
		if not frappe.db.exists("Person", self.name):
			raise frappe.DoesNotExistError(self.not_stored_message)
		super(Document, self).__init__({"doctype": self.doctype, "name": self.name})

	def db_insert(self, *args, **kwargs):
		frappe.throw(self.not_stored_message)

	def db_update(self, *args, **kwargs):
		frappe.throw(self.not_stored_message)

	def delete(self, *args, **kwargs):
		frappe.throw(self.not_stored_message)

	@property
	def not_stored_message(self) -> str:
		return _("{0} keeps no records. Import people with Data Import.").format(_(self.doctype))
