# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""AI Sends: the Access Log rows of churchit's own AI features, for System Managers only."""

import frappe
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.utils import now_datetime

from churchit.ai.test_runner import set_ai, staff_user
from churchit.church_people.ai import get_person_briefing
from churchit.church_setup.number_card.ai_sends_this_month.ai_sends_this_month import get_value
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

REPORT = "AI Sends"
STAFF = "_test_ai_sends_staff@example.com"
MANAGER = "_test_ai_sends_manager@example.com"
SYSTEM_MANAGER = "_test_ai_sends_system_manager@example.com"
ALL_ROWS = 100_000


def get_report_rows() -> list[dict]:
	"""The rows of the saved list, read as the desk reads them, with the reader's permissions."""
	saved = frappe.parse_json(frappe.db.get_value("Report", REPORT, "json"))
	fields = [field for field, _doctype in saved["fields"]]
	# Frappe 17 reads a limit of 0 as its default page of 20 rows, and keeps the rows of earlier runs.
	return frappe.get_list(
		"Access Log", filters=saved["filters"], fields=fields, order_by=saved["order_by"], limit=ALL_ROWS
	)


class TestAISends(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, church, _other = make_two_churches()
		staff_user(STAFF, church, roles=("Church Staff",))
		staff_user(MANAGER, church, roles=("Church Manager",))
		ensure_user(SYSTEM_MANAGER, "AI Sends", roles=("System Manager",))
		cls.person = make_person("_Test AI Sends", church=church).name

	def setUp(self):
		super().setUp()
		set_ai(1)

	def test_a_briefing_appears_and_other_access_does_not(self):
		started = now_datetime()
		frappe.set_user(STAFF)
		get_person_briefing(self.person)
		make_access_log(doctype="Person", document=self.person, method="Export")

		frappe.set_user(SYSTEM_MANAGER)
		# Frappe 17 writes logs to a log database that the test rollback does not reach.
		rows = [
			row
			for row in get_report_rows()
			if row.reference_document == self.person and row.creation >= started
		]
		self.assertEqual(
			[(row.user, row.method, row.export_from) for row in rows],
			[(STAFF, "AI: Person briefing", "Person")],
		)

	def test_the_card_counts_the_list_for_a_system_manager_only(self):
		frappe.set_user(STAFF)
		get_person_briefing(self.person)

		frappe.set_user(SYSTEM_MANAGER)
		total = get_value()
		self.assertEqual(total["value"], len(get_report_rows()))
		self.assertGreaterEqual(total["value"], 1)
		self.assertEqual(total["route"], ["List", "Access Log", "Report", REPORT])

		frappe.set_user(MANAGER)
		self.assertRaises(frappe.PermissionError, get_value)
