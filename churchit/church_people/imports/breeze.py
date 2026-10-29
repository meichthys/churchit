# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A Tithely ChMS (Breeze) people export, in the columns of the Breeze Import DocType.

A church exports from Account Settings, Export, People, as a spreadsheet. Each row is one person. Breeze ID
and Family are Breeze's own IDs, so a later export finds the same people and families. Family Role is one
of Breeze's family roles: Head of Household is the primary contact, Child is a Child of the household, and
Spouse and Adult are Adults. Unassigned sets no role, so the family's own rule decides it from the
relationship and the age. A family with no Head of Household takes its first Adult as primary contact.
The export has no family name, so a Family is named after its primary contact in the file.
Breeze's Status is a church's own list, so the import maps each value to a Membership.

Sources:
- The export's header row (Breeze ID, Family, Family Role, Street Address, Zip and so on) as read by
  migration tools: https://github.com/ChurchApps/B1Transfer/blob/HEAD/src/helpers/ImportHelpers/ImportBreezeZipHelper.ts
- Export steps: https://www.churchtrac.com/support/getting_started/breeze-import
- Family roles (Unassigned, Child, Adult, Head of Household, Spouse): https://app.breezechms.com/api#update_person
"""

from churchit.church_people.household import ADULT, CHILD
from churchit.church_people.imports.provider import SourceProvider
from churchit.church_people.imports.record import Household, ImportedPerson, clean

BREEZE = "Breeze"
HEAD_OF_HOUSEHOLD = "head of household"
FAMILY_ROLES = {"head of household": ADULT, "spouse": ADULT, "adult": ADULT, "child": CHILD}


class BreezeImportProvider(SourceProvider):
	system = BREEZE

	def import_row(self, importer, doc):
		family_name = self.get_family_names(importer.import_file).get(clean(doc.get("household_id")))
		return super().import_row(importer, {**doc, "household_name": family_name})

	def to_record(self, row: dict) -> ImportedPerson:
		household = None
		if household_id := clean(row.get("household_id")):
			family_role = (clean(row.get("household_role")) or "").lower()
			role = FAMILY_ROLES.get(family_role)
			household = Household(
				legacy_id=household_id,
				name=row.get("household_name"),
				role=role,
				is_primary_contact=family_role == HEAD_OF_HOUSEHOLD,
				may_be_primary_contact=role == ADULT,
			)
		return ImportedPerson.from_row(self.system, row, row.get("gender") or None, household)

	def get_family_names(self, import_file) -> dict[str, str]:
		"""{Family ID: "Last - First" of its Head of Household in the file, else of its first Adult}, so the
		order of the rows does not matter. Worked out once per import."""
		if "family_names" not in self.__dict__:
			self.family_names = {}
			for _row, record in self.get_records(import_file):
				household = record.household
				if not household or not household.may_lead:
					continue
				if household.is_primary_contact or household.legacy_id not in self.family_names:
					names = (record.values["last_name"], record.values["first_name"])
					self.family_names[household.legacy_id] = " - ".join(filter(None, names))
		return self.family_names
