# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's own people spreadsheet: one row per person, in the columns of the People Import DocType.

It suits a list kept by hand, and a system with no import source of its own. Imported From names that
system (Spreadsheet when blank), and with Person ID it finds the person again on the next import. People
with one Household ID share a Family.
"""

from churchit.church_people.imports.provider import SourceProvider
from churchit.church_people.imports.record import Household, ImportedPerson, clean

SPREADSHEET = "Spreadsheet"


class PeopleImportProvider(SourceProvider):
	system = SPREADSHEET

	def to_record(self, row: dict) -> ImportedPerson:
		household = None
		if household_id := clean(row.get("household_id")):
			household = Household(
				legacy_id=household_id,
				name=clean(row.get("household_name")),
				role=row.get("household_role") or None,
				is_primary_contact=bool(row.get("is_primary_contact")),
			)
		system = clean(row.get("legacy_system")) or self.system
		return ImportedPerson.from_row(system, row, row.get("gender") or None, household)
