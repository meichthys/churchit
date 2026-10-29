# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A Rock RMS person report exported to Excel, in the columns of the Rock RMS Import DocType.

Rock exports no whole people list. A church builds a Report on Person with the fields below and uses
its Export to Excel; each report field's Column Header names the column. The columns are the names of
Rock's own CSV Import (Id, Family Id, Family Role, Nick Name, Connection Status, Record Status and so
on), so a report set up once maps as it is. Id and Family Id (the person's Primary Family Id) are
numbered by each Rock server, so they find the same people again only in the church that imported them.

Rock has no head of household: the first Adult of a family in the file becomes its Primary Contact.
Rock's genders (Male, Female, Unknown) and family roles (Adult, Child) are Churchit's own.

Sources:
- Export a Report to Excel, the only whole-list export: https://community.rockrms.com/ask/using/917
- Column headers of a report field: https://github.com/SparkDevNetwork/Rock/blob/develop/Rock/Reporting/ReportingHelper.cs
- Rock's CSV Import column names: https://github.com/SparkDevNetwork/Rock/blob/develop/Rock.Slingshot/Constant/CSVHeaders.cs
- Values of Family Role, Gender, Marital Status and Record Status:
  https://github.com/SparkDevNetwork/Rock/blob/develop/Rock.Slingshot/CSVMapper/PersonCsvMapper.cs
- Connection Status and Record Status values: https://github.com/SparkDevNetwork/Rock/blob/develop/Rock/SystemGuid/DefinedValue.cs
- No head of household, Primary Family Id: https://community.rockrms.com/documentation/bookcontent/5/175
"""

from churchit.church_people.household import ADULT, CHILD
from churchit.church_people.imports.provider import SourceProvider
from churchit.church_people.imports.record import Household, ImportedPerson, clean

ROCK_RMS = "Rock RMS"
FAMILY_ROLES = {"Adult": ADULT, "Child": CHILD}


class RockRMSImportProvider(SourceProvider):
	system = ROCK_RMS

	def to_record(self, row: dict) -> ImportedPerson:
		household = None
		if household_id := clean(row.get("household_id")):
			role = FAMILY_ROLES.get(row.get("household_role"))
			household = Household(
				legacy_id=household_id,
				name=clean(row.get("household_name")),
				role=role,
				may_be_primary_contact=role == ADULT,
			)
		return ImportedPerson.from_row(
			self.system, row, row.get("gender") or None, household, is_deceased=bool(row.get("is_deceased"))
		)
