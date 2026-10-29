# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A Planning Center People export, in the columns of the Planning Center Import DocType.

A church exports from People, Import & Export CSV (every person), or with the download button of a list.
Each row is one person and carries their household: Planning Center has no household export. Person ID
and Household ID are Planning Center's own, so a later export finds the same people and families.
Household Primary Contact names the primary contact, and Child makes a member a Child of the household;
everyone else in it is an Adult. A birth year of 1885 means Planning Center does not know the year.

Sources:
- Export: https://help.planningcenter.com/en/138570-export-data.html
- Columns and values (Person ID always exported, Gender M/F or Male/Female, Child as yes/no or true/false,
  1885 as no birth year, several emails or phones split by ";"):
  https://help.planningcenter.com/en/138557-prepare-a-csv-file-for-import.html
- Person ID in every list export: https://www.planningcenter.com/changelog/people/improved-new-list-columns-conditions-and-export-data
- The export's header row (Household Name, Household Primary Contact) as read by migration tools:
  https://github.com/ChurchApps/B1Transfer/blob/HEAD/src/helpers/ImportHelpers/ImportPlanningCenterZipHelper.ts
- Person and Household attributes: https://api.planningcenteronline.com/docs/apps/people/versions/2026-10-05/vertices/person
"""

from churchit.church_people.doctype.inactive_reason.inactive_reason import DECEASED
from churchit.church_people.household import ADULT, CHILD
from churchit.church_people.imports.provider import SourceProvider
from churchit.church_people.imports.record import Household, ImportedPerson, clean

PLANNING_CENTER = "Planning Center"
UNKNOWN_BIRTH_YEAR = 1885
GENDERS = {"M": "Male", "Male": "Male", "F": "Female", "Female": "Female"}
CHILD_VALUES = ("child", "true", "yes", "y", "1")


class PlanningCenterImportProvider(SourceProvider):
	system = PLANNING_CENTER

	def to_record(self, row: dict) -> ImportedPerson:
		household = None
		if household_id := clean(row.get("household_id")):
			household = Household(
				legacy_id=household_id,
				name=clean(row.get("household_name")),
				role=CHILD if (clean(row.get("is_child")) or "").lower() in CHILD_VALUES else ADULT,
				is_primary_contact=bool(row.get("is_primary_contact")),
			)
		birth_year = getattr(row.get("birth_date"), "year", None)
		return ImportedPerson.from_row(
			self.system,
			row,
			GENDERS.get(row.get("gender")),
			household,
			birth_year_unknown=birth_year == UNKNOWN_BIRTH_YEAR,
			is_deceased=row.get("inactive_reason") == DECEASED,
		)
